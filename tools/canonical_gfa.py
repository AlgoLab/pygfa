# AI! write a python program that receives on the command line the filename of a
# gfa file and writes a canonical version of that file.
# First it reads the input gfa file, obtaining a gfa graph
# Then it calls a to_gfa method (in the file gfa.py) that outputs the sections
# in this order:
# 1. header
# 2. segments
# 3. links
# 4. paths
# 5. walks
# 6. containments
# The headers are in lexicographic order
# The segments are sorted by their Name
# The links are sorted by From and then by To
# The paths are sorted by PathName
# The walks are sorted by SampleID and then by SeqId
# Containments are sorted by Container and Contained
#
# The gfa is printed to standard output. There is an option to write it to a
# file, whose filename is provided on the command line
#
# Include a --verbose option that prints a trace of the operations
