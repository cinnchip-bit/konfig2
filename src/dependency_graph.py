"""Dependency graph collection and traversal for Rust Cargo packages."""
from __future__ import annotations
import csv
import html
import json
import urllib.request
from dataclasses import dataclass
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


CONFIG_ROW_FIELDS = 2
MIN_DEPTH = 0
TRUE_VALUES = {'1', 'true', 'yes'}
BOOLEAN_VALUES = TRUE_VALUES | {'0', 'false', 'no'}
REQUIRED_KEYS = (
    'package', 'repository', 'test_mode', 'version', 'output',
    'max_depth', 'exclude',
)


def _config_values(path: str) -> dict[str, str]:
    values = {}
    with open(path, newline='', encoding='utf-8') as source:
        for row in csv.reader(source):
            if not row or row[0].strip().startswith('#'):
                continue
            if len(row) != CONFIG_ROW_FIELDS:
                raise ValueError('CSV config rows must have key,value')
            values[row[0].strip()] = row[1].strip()
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise ValueError('Missing config keys: ' + ', '.join(missing))
    if not values['package']:
        raise ValueError('package must not be empty')
    return values


def _parse_depth(value: str) -> int:
    try:
        depth = int(value)
    except ValueError as error:
        raise ValueError('max_depth must be an integer') from error
    if depth < MIN_DEPTH:
        raise ValueError('max_depth must be non-negative')
    return depth


def load_config(path: str) -> Config:
    values = _config_values(path)
    depth = _parse_depth(values['max_depth'])
    mode = values['test_mode'].lower()
    if mode not in BOOLEAN_VALUES:
        raise ValueError('test_mode must be true or false')
    return Config(
        values['package'], values['repository'], mode in TRUE_VALUES,
        values['version'], values['output'], depth, values['exclude'],
    )


def load_test_repository(path: str) -> dict[str, list[str]]:
    graph = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith('#'):
                continue
            name = row[0].strip()
            if not name.isupper():
                raise ValueError('test package names must be uppercase')
            graph[name] = [x.strip() for x in row[1:] if x.strip()]
    return graph


def cargo_dependencies(
    repo: str, package: str, version: str | None,
) -> list[str]:
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


def _included_dependencies(node, depth, get_deps, max_depth, exclude):
    if depth >= max_depth:
        return []
    return [dep for dep in get_deps(node) if not (exclude and exclude in dep)]


def bfs_recursive(
    root: str,
    get_deps: Callable[[str], list[str]],
    max_depth: int,
    exclude: str = '',
) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    visited: set[str] = set()

    def visit(queue: list[tuple[str, int]]) -> None:
        if not queue:
            return
        node, depth = queue.pop(0)
        if node in visited or (exclude and exclude in node):
            visit(queue)
            return
        visited.add(node)
        deps = _included_dependencies(
            node, depth, get_deps, max_depth, exclude,
        )
        graph[node] = deps
        queue.extend((dep, depth + 1) for dep in deps if dep not in visited)
        visit(queue)

    visit([(root, 0)])
    return graph


def reverse_dependencies(graph: dict[str, list[str]], target: str) -> list[str]:
    return sorted(node for node, deps in graph.items() if target in deps)


LAST_ITEM_OFFSET = 1


def ascii_tree(graph: dict[str, list[str]], root: str) -> str:
    lines = [root]

    def walk(node: str, prefix: str, stack: set[str]) -> None:
        for i, dep in enumerate(graph.get(node, [])):
            last = i == len(graph.get(node, [])) - LAST_ITEM_OFFSET
            mark = '└── ' if last else '├── '
            suffix = ' (cycle)' if dep in stack else ''
            lines.append(prefix + mark + dep + suffix)
            if dep not in stack:
                padding = '    ' if last else '│   '
                walk(dep, prefix + padding, stack | {dep})
    walk(root, '', {root})
    return '\n'.join(lines)


def _svg_roots(graph):
    nodes = set(graph)
    for deps in graph.values():
        nodes.update(deps)
    dependencies = {dep for deps in graph.values() for dep in deps}
    roots = [node for node in nodes if node not in dependencies]
    if not roots:
        roots = [next(iter(nodes))] if nodes else []
    return nodes, roots


def _svg_levels(graph):
    nodes, roots = _svg_roots(graph)
    children = {node: graph.get(node, []) for node in nodes}
    levels = {}
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

    return levels, grouped


def _svg_positions(levels, grouped):
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

    return positions, width, height


def _svg_header(width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" role="img">',
        '<style>text{font:14px '
        'sans-serif}.n{fill:#e8f1fb;stroke:#246;stroke-width:1.5}</style>',
        '<defs><marker id="a" markerWidth="8" markerHeight="8" '
        'refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 '
        'z" fill="#777"/></marker></defs>'
    ]


def _svg_edges(graph, positions):
    lines = []
    for src, deps in graph.items():
        for dst in deps:
            if src in positions and dst in positions:
                x1, y1 = positions[src]
                x2, y2 = positions[dst]
                lines.append(
                    f'<line x1="{x1}" y1="{y1+22}" x2="{x2}" y2="{y2-22}" '
                    f'stroke="#777" marker-end="url(#a)"/>'
                )

    return lines


def _svg_nodes(positions):
    lines = []
    for node, (x, y) in positions.items():
        label = html.escape(node[:22])
        lines.append(
            f'<rect class="n" x="{x-75}" y="{y-22}" width="150" '
            f'height="44" rx="8"/>'
            f'<text x="{x}" y="{y+5}" text-anchor="middle">{label}</text>'
        )

    return lines


def graphviz_svg(graph: dict[str, list[str]]) -> str:
    levels, grouped = _svg_levels(graph)
    positions, width, height = _svg_positions(levels, grouped)
    lines = _svg_header(width, height)
    lines.extend(_svg_edges(graph, positions))
    lines.extend(_svg_nodes(positions))
    lines.append('</svg>')
    return '\n'.join(lines)
