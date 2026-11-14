import argparse
from pathlib import Path

from dependency_graph import (
    ascii_tree,
    bfs_recursive,
    cargo_dependencies,
    graphviz_svg,
    load_config,
    load_test_repository,
    reverse_dependencies,
)


def dependency_getter(cfg):
    if cfg.test_mode:
        repo = load_test_repository(cfg.repository)
        return lambda name: repo.get(name, [])
    return lambda name: cargo_dependencies(
        cfg.repository,
        name,
        cfg.version if name == cfg.package else None,
    )


def main():
    ap = argparse.ArgumentParser(
        description='Rust Cargo dependency graph visualizer',
    )
    ap.add_argument('config')
    ap.add_argument('--reverse')
    ap.add_argument('--tree', action='store_true')
    args = ap.parse_args()
    cfg = load_config(args.config)
    print('\n'.join(f'{k}={v}' for k, v in vars(cfg).items()))
    graph = bfs_recursive(
        cfg.package, dependency_getter(cfg), cfg.max_depth, cfg.exclude,
    )
    if args.reverse:
        print('Reverse dependencies:', ', '.join(
            reverse_dependencies(graph, args.reverse)
        ))
    if args.tree:
        print(ascii_tree(graph, cfg.package))
    Path(cfg.output).write_text(graphviz_svg(graph), encoding='utf-8')
    print(f'Graph nodes: {len(graph)}')
    print(f'SVG written: {cfg.output}')


if __name__ == '__main__':
    main()
