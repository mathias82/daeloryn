"""Conservative, metadata-only stack signals for opt-in local checkouts.

Never execute a build or inspect source files. Reads only a bounded set of
standard manifest filenames; no filesystem-wide traversal or symlink follows.
"""
import json
from pathlib import Path

MAX_MANIFEST_BYTES = 64 * 1024
MAX_CHILD_DIRS = 32
SKIP = {".git", "node_modules", "target", "build", "dist", "vendor", ".venv",
        ".next", ".gradle", "coverage", ".idea"}
JAVA_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")
NODE_FILES = ("package.json",)
PLATFORM_FILES = ("Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                  "compose.yaml", "compose.yml", "Chart.yaml", "kustomization.yaml",
                  "kustomization.yml")
CI_FILES = (".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", "azure-pipelines.yml")


def _manifest(path):
    """Limit reads and reject links; ignore manifests that change during read."""
    try:
        if path.is_symlink() or not path.is_file():
            return ""
        size = path.stat().st_size
        if size > MAX_MANIFEST_BYTES:
            return ""
        raw = path.read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES or b"\0" in raw:
            return ""
        return raw.decode("utf-8", errors="replace").casefold()
    except OSError:
        return ""


def _folders(base):
    yield base
    try:
        children = sorted(base.iterdir(), key=lambda p: p.name)
    except OSError:
        return
    # At most 32 immediate component folders; no recursive source walk.
    # A monorepo can expose React/frontend and Spring/backend independently.
    for child in children[:MAX_CHILD_DIRS]:
        if (child.name not in SKIP and not child.name.startswith(".") and
                not child.is_symlink() and child.is_dir()):
            yield child


def detect_technologies(project):
    """Return conservative lower-case technology tags; absence means unknown."""
    base = Path(project)
    tags = set()
    for folder in _folders(base):
        java_manifests = [_manifest(folder / p) for p in JAVA_FILES]
        java_manifests = [m for m in java_manifests if m]
        if java_manifests:
            tags.add("java")
            if (folder / "pom.xml").is_file() and not (folder / "pom.xml").is_symlink():
                tags.add("java-maven")
            if any((folder / p).is_file() and not (folder / p).is_symlink()
                   for p in ("build.gradle", "build.gradle.kts")):
                tags.add("java-gradle")
            if any("spring-boot" in m or "org.springframework" in m or
                   "springframework.boot" in m for m in java_manifests):
                tags.add("spring")
        package = _manifest(folder / "package.json")
        if package:
            tags.add("node")
            try:
                data = json.loads(package)
                deps = {}
                if isinstance(data, dict):
                    for field in ("dependencies", "devdependencies", "peerdependencies"):
                        values = data.get(field)
                        if isinstance(values, dict):
                            deps.update(values)
                if "react" in deps or "react-dom" in deps or "next" in deps:
                    tags.add("react")
                if "typescript" in deps or _manifest(folder / "tsconfig.json"):
                    tags.add("typescript")
            except (ValueError, TypeError):
                pass
        if any((folder / p).is_file() and not (folder / p).is_symlink()
               for p in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                         "compose.yml", "compose.yaml")):
            tags.add("docker")
        if any((folder / p).is_file() and not (folder / p).is_symlink()
               for p in ("Chart.yaml", "kustomization.yml", "kustomization.yaml")):
            tags.add("kubernetes")
        for folder_name in ("charts", "helm", "k8s", "kubernetes"):
            item = folder / folder_name
            if not item.is_symlink() and item.is_dir():
                tags.add("kubernetes")
        if any(not (folder / p).is_symlink() and (folder / p).exists()
               for p in CI_FILES):
            tags.add("ci")
    return sorted(tags)
