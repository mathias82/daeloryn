"""Docs-only project snapshot, explicitly excluding code and build manifests."""
import os
from pathlib import Path
from code_context import EXCLUDE_DIRS, EXCLUDE_NAMES, SENSITIVE
from project_analysis import analyze_local

MAX_ENTRIES=3000
MAX_FILES=8
MAX_BYTES=65536
MAX_FILE_BYTES=24576
DOCUMENT_SUFFIXES={".md",".markdown",".rst",".adoc"}
DOCUMENT_NAMES={"README","LICENSE","NOTICE","CHANGELOG","CONTRIBUTING"}


def snapshot_docs(root,repository,task):
    if not isinstance(task,str) or not task.strip() or len(task)>3000:
        raise ValueError("docs-only requires a bounded task")
    analyze_local(root,repository)
    base=Path(root).resolve(strict=True)/repository
    words={word.casefold() for word in task.split() if len(word)>3}
    candidates=[]
    entries=0
    def visit(directory,depth):
        nonlocal entries
        if depth>12:
            raise ValueError("Docs inventory exceeds maximum depth")
        with os.scandir(directory) as listing:
            children=sorted(listing,key=lambda entry:entry.name)
        for entry in children:
            entries+=1
            if entries>MAX_ENTRIES:
                raise ValueError("Docs inventory exceeds entry budget")
            if entry.is_symlink() or entry.name.startswith("."):
                continue
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in EXCLUDE_DIRS:
                    visit(entry.path,depth+1)
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            path=Path(entry.path)
            rel=path.relative_to(base).as_posix()
            if path.name in EXCLUDE_NAMES or SENSITIVE.search(path.name):
                continue
            if path.suffix.lower() not in DOCUMENT_SUFFIXES and not (
                path.name.upper() in DOCUMENT_NAMES and path.parent==base):
                continue
            score=20 if path.name.casefold().startswith("readme") else 0
            score+=sum(5 for word in words if word in rel.casefold())
            candidates.append((score,rel,path))
    visit(base,0)
    candidates.sort(key=lambda entry:(-entry[0],entry[1]))
    total=0
    files=[]
    omitted=[]
    for _,rel,path in candidates[:MAX_FILES]:
        try:
            if path.resolve(strict=True)!=path or not path.is_file():
                omitted.append({"path":rel,"reason":"path changed"});continue
            size=path.stat(follow_symlinks=False).st_size
            if size>MAX_FILE_BYTES or size+total>MAX_BYTES:
                omitted.append({"path":rel,"reason":"docs byte budget"});continue
            with path.open("rb") as stream:
                raw=stream.read(MAX_FILE_BYTES+1)
            if len(raw)>MAX_FILE_BYTES or b"\0" in raw:
                omitted.append({"path":rel,"reason":"binary or oversized"});continue
            lines=raw.decode("utf-8").splitlines(keepends=True)
        except (OSError,UnicodeError):
            omitted.append({"path":rel,"reason":"unreadable documentation"});continue
        body="".join("[REDACTED]\n" if SENSITIVE.search(line) else line for line in lines)
        files.append({"path":rel,"source":body,"line_count":len(lines)})
        total+=len(raw)
    if not files:
        raise ValueError("No eligible documentation; choose Smart Review or provide documentation")
    return {"files":files,"omitted":omitted,"excluded":[],
            "bytes_read":total,"scope_type":"docs",
            "scope":"Docs-only: Markdown/reStructuredText/AsciiDoc and conventional root documentation; no source or build manifests",
            "all_eligible_files_included":False,
            "matching_candidates":len(candidates),
            "max_selected_files":MAX_FILES}
