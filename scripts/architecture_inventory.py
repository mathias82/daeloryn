"""Conservative source-derived architecture inventory (not a resolved dependency graph)."""
from collections import Counter
from pathlib import PurePosixPath

MAX_COMPONENTS = 60
MAX_DEPENDENCIES = 80
JAVA_FRAMEWORKS = (
    ("org.springframework", "Spring"),
    ("jakarta.persistence", "Jakarta Persistence"),
    ("javax.persistence", "JPA"),
    ("org.apache.kafka", "Kafka"),
    ("io.grpc", "gRPC"),
    ("reactor.core", "Reactor"),
    ("com.azure", "Azure SDK"),
    ("org.junit", "JUnit"),
)

def inventory(context):
    components = []
    dependencies = Counter()
    for file in context["files"]:
        path = file["path"]
        suffix = PurePosixPath(path).suffix
        if len(components) < MAX_COMPONENTS:
            components.append({"file": path, "language": {
                ".java": "Java", ".kt": "Kotlin", ".py": "Python",
                ".ts": "TypeScript", ".tsx": "TypeScript",
                ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
            }.get(suffix, "unknown"), "symbols": file["symbols"][:20]})
        for imported in file["imports"]:
            for prefix, label in JAVA_FRAMEWORKS:
                if imported == prefix or imported.startswith(prefix + "."):
                    dependencies[label] += 1
                    break
    return {"components": components,
            "framework_hints": [{"name": name, "import_occurrences": count}
                                for name, count in dependencies.most_common(MAX_DEPENDENCIES)],
            "source_files_scanned": context["files_read"],
            "skipped": context["skipped"],
            "limitations": "Import hints are not resolved dependencies; symbols are regex matches. "
                           "No call graph, runtime topology, or build-file dependency parsing."}
