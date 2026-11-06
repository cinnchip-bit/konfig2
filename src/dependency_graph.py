"""Dependency graph collection and traversal for Rust Cargo packages."""
from __future__ import annotations
import csv, json, urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

@dataclass
class Config:
    package: str
    repository: str
    test_mode: bool
    version: str
    output: str
    max_depth: int
    exclude: str

def load_config(path: str) -> Config:
    values = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith('#'): continue
            if len(row) != 2: raise ValueError('CSV config rows must have key,value')
            values[row[0].strip()] = row[1].strip()
    required = ['package','repository','test_mode','version','output','max_depth','exclude']
    missing = [k for k in required if k not in values]
    if missing: raise ValueError('Missing config keys: ' + ', '.join(missing))
    if not values['package']: raise ValueError('package must not be empty')
    try: depth = int(values['max_depth'])
    except ValueError as e: raise ValueError('max_depth must be an integer') from e
    if depth < 0: raise ValueError('max_depth must be non-negative')
    test_mode = values['test_mode'].lower() in {'1','true','yes'}
    if values['test_mode'].lower() not in {'0','1','true','false','yes','no'}: raise ValueError('test_mode must be true or false')
    return Config(values['package'], values['repository'], test_mode, values['version'], values['output'], depth, values['exclude'])

def load_test_repository(path: str) -> dict[str, list[str]]:
    graph = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith('#'): continue
            name = row[0].strip()
            if not name.isupper(): raise ValueError('test package names must be uppercase')
            graph[name] = [x.strip() for x in row[1:] if x.strip()]
    return graph


def cargo_dependencies(repo: str, package: str, version: str | None) -> list[str]:
    base = repo.rstrip('/')

    def get_json(url):
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'variant8-dependency-graph/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)

    if version is None:
        data = get_json(f'{base}/api/v1/crates/{package}')
        crate = data['crate']
        version = crate.get('max_stable_version') or crate.get('max_version')

    url = f'{base}/api/v1/crates/{package}/{version}/dependencies'
    data = get_json(url)

    return [
        d['crate_id']
        for d in data.get('dependencies', [])
        if d.get('kind') != 'dev' and not d.get('optional', False)
    ]


def bfs_recursive(root: str, get_deps: Callable[[str], list[str]], max_depth: int, exclude: str = '') -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    visited: set[str] = set()
    def visit(queue: list[tuple[str,int]]) -> None:
        if not queue: return
        node, depth = queue.pop(0)
        if node in visited or (exclude and exclude in node):
            visit(queue); return
        visited.add(node)
        deps = [] if depth >= max_depth else [d for d in get_deps(node) if not (exclude and exclude in d)]
        graph[node] = deps
        queue.extend((d, depth+1) for d in deps if d not in visited)
        visit(queue)
    visit([(root, 0)])
    return graph

def reverse_dependencies(graph: dict[str,list[str]], target: str) -> list[str]:
    return sorted(node for node, deps in graph.items() if target in deps)

def ascii_tree(graph: dict[str,list[str]], root: str) -> str:
    lines = [root]
    def walk(node: str, prefix: str, stack: set[str]) -> None:
        for i, dep in enumerate(graph.get(node, [])):
            last = i == len(graph.get(node, []))-1
            mark = '└── ' if last else '├── '
            suffix = ' (cycle)' if dep in stack else ''
            lines.append(prefix + mark + dep + suffix)
            if dep not in stack: walk(dep, prefix + ('    ' if last else '│   '), stack | {dep})
    walk(root, '', {root})
    return '\n'.join(lines)


def graphviz_svg(graph: dict[str, list[str]]) -> str:
    import html

    nodes = set(graph)
    for deps in graph.values():
        nodes.update(deps)

    children = {n: graph.get(n, []) for n in nodes}
    levels = {}

    roots = [n for n in nodes if n not in {
        d for deps in graph.values() for d in deps
    }]

    if not roots:
        roots = [next(iter(nodes))] if nodes else []

    queue = [(n, 0) for n in roots]

    while queue:
        node, depth = queue.pop(0)

        if node in levels and levels[node] <= depth:
            continue

        levels[node] = depth

        for dep in children[node]:
            queue.append((dep, depth + 1))

    for node in nodes:
        levels.setdefault(node, 0)

    grouped = {}
    for node, depth in levels.items():
        grouped.setdefault(depth, []).append(node)

    positions = {}
    max_width = max(len(group) for group in grouped.values()) if grouped else 1

    for depth, group in grouped.items():
        group.sort()
        for i, node in enumerate(group):
            x = 130 + i * 220
            y = 80 + depth * 140
            positions[node] = (x, y)

    width = max(360, max_width * 220 + 40)
    height = max(180, (max(levels.values()) + 1) * 140 + 50) if levels else 180

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">',
        '<style>text{font:14px sans-serif}.n{fill:#e8f1fb;stroke:#246;stroke-width:1.5}</style>',
        '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#777"/></marker></defs>'
    ]

    for src, deps in graph.items():
        for dst in deps:
            if src in positions and dst in positions:
                x1, y1 = positions[src]
                x2, y2 = positions[dst]
                lines.append(
                    f'<line x1="{x1}" y1="{y1+22}" x2="{x2}" y2="{y2-22}" stroke="#777" marker-end="url(#a)"/>'
                )

    for node, (x, y) in positions.items():
        label = html.escape(node[:22])
        lines.append(
            f'<rect class="n" x="{x-75}" y="{y-22}" width="150" height="44" rx="8"/>'
            f'<text x="{x}" y="{y+5}" text-anchor="middle">{label}</text>'
        )

    lines.append('</svg>')
    return '\n'.join(lines)

