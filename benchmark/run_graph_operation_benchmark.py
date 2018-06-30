import sys
import subprocess
import run_profiler

def main(result_file, number_source, max_distance, type_compression='nodes'):
    file_handler = open(result_file, "w")

    for i in range(0, number_source):
        for grade in (0, max_distance + 1):
            path = "benchmark_graphs/graph{}_g{}".format(i, grade)
            result = run_profiler.run_profiler_graph_operation(path, i, grade, "\n", type_compression)
            file_handler.write(result)
        file_handler.write("\n")
    
    file_handler.close()

if __name__ == "__main__":
    result_file = sys.argv[1]
    type_compression = sys.argv[2]
    number_source = sys.argv[3]
    max_distance = sys.argv[4]
    main(result_file, number_source, max_distance, type_compression)
