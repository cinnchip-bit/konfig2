import argparse
from dependency_graph import *


def main():
    ap = argparse.ArgumentParser(description='Rust Cargo dependency graph visualizer')
    ap.add_argument('config')
    ap.add_argument('--reverse')
    ap.add_argument('--tree', action='store_true')

    args = ap.parse_args()
    cfg = load_config(args.config)

    print('\n'.join(f'{k}={v}' for k, v in vars(cfg).items()))

    if cfg.test_mode:
        repo = load_test_repository(cfg.repository)
        getter = lambda n: repo.get(n, [])
    else:
        getter = lambda n: cargo_dependencies(
            cfg.repository,
            n,
            cfg.version if n == cfg.package else None
        )

    graph = bfs_recursive(
        cfg.package,
        getter,
        cfg.max_depth,
        cfg.exclude
    )

    if args.reverse:
        print('Reverse dependencies:', ', '.join(
            reverse_dependencies(graph, args.reverse)
        ))

    if args.tree:
        print(ascii_tree(graph, cfg.package))

    Path(cfg.output).write_text(
        graphviz_svg(graph),
        encoding='utf-8'
    )

    print(f'Graph nodes: {len(graph)}')
    print(f'SVG written: {cfg.output}')


if __name__ == '__main__':
    main()

