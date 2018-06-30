"""
Python script to create graphs of the benchmark
"""

from collections import OrderedDict
import matplotlib.pyplot as plt

BENCHMARK = OrderedDict()
with open('results/cmp_node.txt') as node_method_file:
    ROWS = node_method_file.readlines()
    i = 0
    for ROW in ROWS:
        i += 1
        ROW = ROW.split('\t')
        BENCHMARK[int(ROW[8])] = {int(ROW[8]) : {'overlap_consistency_n' : float(ROW[2])}}
        BENCHMARK[int(ROW[8])][int(ROW[9])]['node_compression'] = float(ROW[3])
        BENCHMARK[int(ROW[8])][int(ROW[9])]['element_number_n'] = float(ROW[4]) + float(ROW[5])
    node_method_file.close()

with open('results/cmp_edge.txt') as node_method_file:
    ROWS = node_method_file.readlines()
    i = 0
    for ROW in ROWS:
        i += 1
        ROW = ROW.split('\t')
        BENCHMARK[int(ROW[8])] = {int(ROW[8]) : {'overlap_consistency_e' : float(ROW[2])}}
        BENCHMARK[int(ROW[8])][int(ROW[9])]['edge_compression'] = float(ROW[3])
        BENCHMARK[int(ROW[8])][int(ROW[9])]['element_number_e'] = float(ROW[4]) + float(ROW[5])
    node_method_file.close()

print(BENCHMARK)

"""
EDGES = []
N_CHECK = []
E_CHECK = []
CMP_NODE = []
CMP_EDGE = []
MY_N_NODE = []
for e in MY_NORAND:
    EDGES.append(e)
    N_CHECK.append(MY_NORAND.get(e).get('check_n'))
    E_CHECK.append(MY_NORAND.get(e).get('check_e'))
    CMP_NODE.append(MY_NORAND.get(e).get('node_cmp'))
    CMP_EDGE.append(MY_NORAND.get(e).get('edge_cmp'))
    MY_N_NODE.append(MY_NORAND.get(e).get('n_node'))

EDGES = []
N_CHECK_RANDOM = []
E_CHECK_RANDOM = []
CMP_NODE_RANDOM = []
CMP_EDGE_RANDOM = []
MY_N_NODE_RANDOM = []
for e in MY_RAND:
    EDGES.append(e)
    N_CHECK_RANDOM.append(MY_RAND.get(e).get('random_check_n'))
    E_CHECK_RANDOM.append(MY_RAND.get(e).get('random_check_e'))
    CMP_NODE_RANDOM.append(MY_RAND.get(e).get('random_node_cmp'))
    CMP_EDGE_RANDOM.append(MY_RAND.get(e).get('random_edge_cmp'))
    MY_N_NODE_RANDOM.append(MY_RAND.get(e).get('random_n_node'))


plt.plot(EDGES, N_CHECK, label='N_CHECK')
plt.plot(EDGES, E_CHECK, label='E_CHECK')
plt.plot(EDGES, N_CHECK_RANDOM, label='N_CHECK_RANDOM')
plt.plot(EDGES, E_CHECK_RANDOM, label='E_CHECK_RANDOM')
plt.plot(DEF_EDGES, DEF_N_CHECK, label='DEF_N_CHECK')
plt.plot(DEF_EDGES, DEF_E_CHECK, label='DEF_E_CHECK')
plt.plot(DEF_EDGES, DEF_N_CHECK_RANDOM, label='DEF_N_CHECK_RANDOM')
plt.plot(DEF_EDGES, DEF_E_CHECK_RANDOM, label='DEF_E_CHECK_RANDOM')

plt.plot(EDGES, CMP_NODE, label='CMP_NODE')
plt.plot(EDGES, CMP_EDGE, label='CMP_EDGE')
plt.plot(EDGES, CMP_NODE_RANDOM, label='CMP_NODE_RANDOM')
plt.plot(EDGES, CMP_EDGE_RANDOM, label='CMP_EDGE_RANDOM')
plt.plot(DEF_EDGES, DEF_CMP_NODE, label='DEF_CMP_NODE')
plt.plot(DEF_EDGES, DEF_CMP_EDGE, label='DEF_CMP_EDGE')
plt.plot(DEF_EDGES, DEF_CMP_NODE_RANDOM, label='DEF_CMP_NODE_RANDOM')
plt.plot(DEF_EDGES, DEF_CMP_EDGE_RANDOM, label='DEF_CMP_EDGE_RANDOM')

plt.plot(EDGES, MY_N_NODE, label='MY_N_NODE')
plt.plot(EDGES, MY_N_NODE_RANDOM, label='MY_N_NODE_RANDOM')
plt.plot(DEF_EDGES, DEF_N_NODE_RANDOM, label='DEF_N_NODE_RANDOM')



plt.xlabel('number EDGES')
plt.ylabel('sec')
plt.legend()
plt.savefig("prova.png", dpi=500)
plt.show()
"""
