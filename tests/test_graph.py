import sys
sys.path.insert(0,'src')
from dependency_graph import *

def test_bfs_cycle_and_depth():
    repo={'A':['B','C'],'B':['D'],'C':['D'],'D':['A']}
    g=bfs_recursive('A',lambda x:repo[x],3)
    assert set(g)=={'A','B','C','D'}

def test_reverse():
    assert reverse_dependencies({'A':['B'],'C':['B']},'B')==['A','C']

def test_config(tmp_path):
    p = tmp_path / 'c.csv'
    p.write_text(
        'package,A\nrepository,r\ntest_mode,true\nversion,1\n'
        'output,x.svg\nmax_depth,2\nexclude,\n'
    )
    assert load_config(str(p)).package=='A'


def test_bfs_order_depth_and_exclusion():
    repo = {'A': ['B', 'C'], 'B': ['D'], 'C': ['E'], 'D': [], 'E': []}
    calls = []

    def getter(name):
        calls.append(name)
        return repo[name]

    graph = bfs_recursive('A', getter, 2, 'C')
    assert list(graph) == ['A', 'B', 'D']
    assert graph == {'A': ['B'], 'B': ['D'], 'D': []}
    assert calls == ['A', 'B']
    assert bfs_recursive('A', getter, 0) == {'A': []}
    assert bfs_recursive('A', getter, 2, 'A') == {}


def test_tree_cycle_and_shared_dependency():
    graph = {'A': ['B', 'C'], 'B': ['A'], 'C': ['B']}
    assert ascii_tree(graph, 'A') == (
        'A\n├── B\n│   └── A (cycle)\n'
        '└── C\n    └── B\n        └── A (cycle)'
    )


def test_svg_empty_cycle_and_escaping():
    from xml.etree import ElementTree

    for graph in ({}, {'A': ['B'], 'B': ['A']}, {'A<&': []}):
        svg = graphviz_svg(graph)
        root = ElementTree.fromstring(svg)
        assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert 'A&lt;&amp;' in graphviz_svg({'A<&': []})


def test_cli_test_mode(tmp_path):
    import subprocess
    from pathlib import Path
    from xml.etree import ElementTree

    root = Path(__file__).resolve().parents[1]
    config = tmp_path / 'config.csv'
    output = tmp_path / 'graph.svg'
    config.write_text(
        f'package,A\nrepository,{root / "examples/repository.csv"}\n'
        f'test_mode,true\nversion,1\noutput,{output}\n'
        'max_depth,3\nexclude,\n'
    )
    result = subprocess.run(
        [sys.executable, str(root / 'src/main.py'), str(config),
         '--tree', '--reverse', 'D'],
        capture_output=True, text=True, check=True,
    )
    assert 'Reverse dependencies: B, C' in result.stdout
    assert '(cycle)' in result.stdout
    assert 'Graph nodes: 5' in result.stdout
    ElementTree.parse(output)
