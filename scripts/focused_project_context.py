"""Small, explicit project context: path metadata search, then bounded file reads.

No model call, embeddings, repository commands, or full source-content scan.
Only registered checkouts; no symlink traversal. This is a best-effort
path-based selection and MUST NOT be presented as complete source coverage.
"""
import os
import re
from pathlib import Path
from code_context import EXCLUDE_DIRS, EXCLUDE_NAMES, SENSITIVE
from project_analysis import analyze_local
from project_review_context import SOURCE_EXTENSIONS

MAX_ENTRIES = 3000
MAX_MATCHES = 8
MAX_BYTES = 64 * 1024
MAX_FILE_BYTES = 24 * 1024
EXTRA_EXTENSIONS = {".yaml", ".yml", ".properties"}
CODE_EXTENSIONS = {".java", ".kt", ".py", ".ts", ".tsx", ".js", ".jsx", ".go"}
BUG_REVIEW = re.compile(r"\b(?:bugs?|defects?|errors?|vulnerabilit(?:y|ies)|code\s+review|inspect|scan|review|read|classes|class|list|improve|improvements?|refactor|optimi[sz]e|suggest|propose|recommend)\b|σφάλμ|έλεγξ|ελαττώμ|κ[ώω]δικ|κλ[άα]σ|διάβασ|διαβασ", re.I)
NARROW_TARGET = re.compile(r"\b(?:pom(?:\.xml)?|build\.gradle(?:\.kts)?|readme(?:\.md)?|docs?|documentation|single\s+file)\b", re.I)
FOUNDATIONS = {"README.md", "pom.xml", "build.gradle", "build.gradle.kts",
               "package.json", "pyproject.toml"}
STOP = {"what", "where", "when", "does", "this", "that", "which", "with",
        "have", "from", "the", "and", "are", "for", "how", "about", "project",
        "code", "service", "please", "tell", "show", "does", "application"}
CONCEPTS = {
    "observability": {"observability", "telemetry", "otel", "opentelemetry",
                      "metric", "trace", "span", "log", "monitor", "actuator"},
    "logging": {"logging", "log", "slf4j", "logback", "telemetry"},
    "metrics": {"metric", "prometheus", "micrometer", "actuator", "telemetry"},
    "tracing": {"tracing", "trace", "span", "otel", "opentelemetry"},
    "security": {"security", "auth", "oauth", "jwt", "permission", "filter"},
    "authentication": {"security", "auth", "oauth", "jwt", "login"},
    "kafka": {"kafka", "producer", "consumer", "event", "message"},
    "database": {"db", "repository", "database", "jdbc", "entity", "datasource"},
    "παρατηρησιμ": {"observability", "telemetry", "metric", "trace", "span", "log"},
    "καταγραφ": {"log", "logging", "slf4j", "logback"},
    "μετρικ": {"metric", "metrics", "actuator", "micrometer"},
    "ασφαλ": {"security", "auth", "oauth", "jwt", "permission"},
    "ιχνηλατ": {"tracing", "trace", "span", "otel"},
}


def query_terms(task):
    words = {word for word in re.findall(r"[\w]+", task.casefold())
             if len(word) >= 3 and word not in STOP}
    terms = set(words)
    for signal, synonyms in CONCEPTS.items():
        if signal in task.casefold():
            terms.update(synonyms)
    return {item for item in terms if len(item) >= 3}


def snapshot_focused(root, repository, task):
    if not isinstance(task, str) or not task.strip() or len(task) > 3000:
        raise ValueError("focused context requires a bounded question")
    analyze_local(root, repository)
    base = Path(root).resolve(strict=True) / repository
    terms = query_terms(task)
    # A generic bug review must actually inspect program source, even when no
    # filenames happen to contain terms like 'bug' or 'inspect'. This remains
    # focused (up to eight files); full coverage still requires explicit scope.
    generic_bug_review = bool(BUG_REVIEW.search(task) and not NARROW_TARGET.search(task))
    candidates = []
    entries = 0

    def visit(folder, depth):
        nonlocal entries
        if depth > 12:
            return
        with os.scandir(folder) as listing:
            for entry in listing:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError("Focused context metadata limit reached: narrow your query")
                if entry.is_symlink() or entry.name.startswith("."):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in EXCLUDE_DIRS:
                        visit(entry.path, depth + 1)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                path = Path(entry.path)
                if (path.suffix.lower() not in SOURCE_EXTENSIONS | EXTRA_EXTENSIONS
                        and path.name not in FOUNDATIONS):
                    continue
                if path.name in EXCLUDE_NAMES or SENSITIVE.search(path.name):
                    continue
                rel = path.relative_to(base).as_posix()
                lowered = rel.casefold()
                is_foundation = path.name in FOUNDATIONS and "/" not in rel
                score = (12 if is_foundation and path.name.lower().startswith("readme") else
                         9 if is_foundation else 0)
                score += sum(8 for term in terms if term in lowered)
                if path.name.startswith("application.") and any(
                        term in terms for term in ("observability", "telemetry", "metrics", "kafka", "security")):
                    score += 5
                if generic_bug_review and path.suffix.lower() in CODE_EXTENSIONS:
                    # Prioritize production code over README/pom; don't
                    # claim the first few representative files cover all bugs.
                    score += 32 if '/src/main/' in '/' + lowered else 24
                    if '/src/test/' in '/' + lowered or '.test.' in lowered:
                        score -= 16
                if generic_bug_review and is_foundation:
                    score -= 8
                if score > 0:
                    candidates.append((score, rel, path))

    visit(base, 0)
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[:MAX_MATCHES]
    files, omitted = [], []
    total = 0
    for score, rel, path in selected:
        try:
            size = path.stat(follow_symlinks=False).st_size
            if size > MAX_FILE_BYTES or total + size > MAX_BYTES:
                omitted.append({"path": rel, "reason": "focused context byte budget"})
                continue
            # Recheck symlinks, including parent dirs, before reading selected files.
            if path.resolve(strict=True) != path or not path.is_file():
                omitted.append({"path": rel, "reason": "path changed during selection"})
                continue
            with path.open("rb") as handle:
                raw = handle.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES or b"\0" in raw:
                omitted.append({"path": rel, "reason": "binary or oversized"})
                continue
            lines = raw.decode("utf-8").splitlines(keepends=True)
        except (OSError, UnicodeError):
            omitted.append({"path": rel, "reason": "unreadable source"})
            continue
        body = "".join("[REDACTED]\n" if SENSITIVE.search(line) else line for line in lines)
        files.append({"path": rel, "source": body, "line_count": len(lines)})
        total += len(raw)
    if generic_bug_review and not any(item['path'].lower().endswith(tuple(CODE_EXTENSIONS)) for item in files):
        raise ValueError('Generic bug review selected no eligible source files; specify a source path or explicitly request a full scan')
    if not files:
        raise ValueError("No relevant eligible files matched the focused question. Use a more specific question or explicitly request a full review")
    return {
        "files": files, "omitted": omitted, "excluded": [],
        "bytes_read": total, "scope_type": "focused",
        "scope": (("FOCUSED representative code inspection: production source prioritized; "
                   "up to eight files, NOT all project files. Explicitly request 'full scan of the entire project' for full coverage. ")
                  if generic_bug_review else
                  ("FOCUSED filename-based selection with relevant README/build files. "
                   "Not full source coverage; other files may contain important relationships.")),
        "all_eligible_files_included": False,
        "matching_candidates": len(candidates),
        "max_selected_files": MAX_MATCHES,
    }
