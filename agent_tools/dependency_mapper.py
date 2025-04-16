import os
import ast
import json
from datetime import datetime, UTC

PROJECT_DIR = os.getcwd()
LOG_DIR = os.path.join("logs", "dependency_graph")
os.makedirs(LOG_DIR, exist_ok=True)

def find_py_files(base_path):
    py_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_path)
                py_files.append(rel_path)
    return py_files

def extract_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        node = ast.parse(f.read(), filename=file_path)
    imports = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for alias in n.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                imports.add(n.module.split('.')[0])
    return sorted(imports)

def build_dependency_graph(py_files):
    graph = {}
    for file in py_files:
        path = os.path.join(PROJECT_DIR, file)
        imports = extract_imports(path)
        internal_imports = [imp for imp in imports if any(imp in f for f in py_files)]
        graph[file] = internal_imports
    return graph

def save_dependency_graph(graph):
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(LOG_DIR, f"module_graph_{timestamp}.json")
    md_path = os.path.join(LOG_DIR, f"module_graph_{timestamp}.md")

    with open(json_path, "w") as f:
        json.dump(graph, f, indent=2)

    with open(md_path, "w") as f:
        f.write("# 🧩 Module Dependency Graph\n\n")
        for module, deps in graph.items():
            f.write(f"## {module}\n")
            if deps:
                for d in deps:
                    f.write(f"- {d}\n")
            else:
                f.write("- (no imports)\n")
            f.write("\n")

    return {
        "success": True,
        "message": "Dependency graph generated",
        "json_path": json_path,
        "md_path": md_path,
        "graph": graph
    }

def run_dependency_mapper():
    py_files = find_py_files(PROJECT_DIR)
    graph = build_dependency_graph(py_files)
    return save_dependency_graph(graph)
