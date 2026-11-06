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
    p=tmp_path/'c.csv'; p.write_text('package,A\nrepository,r\ntest_mode,true\nversion,1\noutput,x.svg\nmax_depth,2\nexclude,\n')
    assert load_config(str(p)).package=='A'
