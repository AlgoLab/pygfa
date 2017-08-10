import sys
sys.path.insert(1, '../')
import time

from pympler import asizeof
import pygfa

def timeit(function):
    def timed(*args, **kwargs):
        kw = kwargs.copy()
        if "log_data" in kwargs:
            kw.pop("log_data")
        ts = time.time()
        result = function(*args, **kw)
        te = time.time()
        time_ = "{0:f}".format(te-ts)
        if "log_data" in kwargs:
            kwargs["log_data"].append(time_)
        else:
            print(time_)
        return result
    return timed

@timeit
def load_graph(file_path):
    gfa_ = pygfa.gfa.GFA.from_file(file_path)
    return gfa_

@timeit
def compute_elements(gfa_):
    nodes = gfa_.nodes()
    edges = gfa_.edges()
    x = [x for x in range(1, 2**10)]
    return len(nodes), len(edges)

@timeit
def compute_connected_components(gfa_):
    conn_components = list(pygfa.nodes_connected_components(gfa_))
    dov_conn_components = list(pygfa.dovetails_nodes_connected_components(gfa_))
    return len(conn_components), len(dov_conn_components)

@timeit
def compute_linear_paths(gfa_):
    linear_paths = list(pygfa.dovetails_linear_paths(gfa_))
    return len(linear_paths)

def run_profiler(file_, end=""):
    data = []
    gfa_ = load_graph(file_, log_data=data)
    nodes, edges = compute_elements(gfa_, log_data=data)
    cc, dov_cc = compute_connected_components(gfa_, log_data=data)
    lin_paths = compute_linear_paths(gfa_, log_data=data)
    data.extend([nodes, edges, cc, dov_cc, lin_paths, asizeof.asizeof(gfa_)])
    return str.join("\t", [str(x) for x in data]) + end

if __name__ == "__main__":
    print(run_profiler(sys.argv[1]))
