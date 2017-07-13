# :TODO:
This file try to collect general TODOs.

* Networkx should already provide a way to get weakly connected
  components, PyGFA should use it instead of the doing as
  actual implementation.

* Find all the connected components (weakly or not) in the graph.

* Should ids be validated?
  The graph now accept any graph element
  without check for ids clashing. This makes the graph very flexible
  to extend (for example fragment external references are inserted in the
  graph too, making possible to further add any type of useful
  information to external sequences).

* Check for graphs equality.
  This is not so easy to deal with, since
  virtual_ids could make the same information to have different ids
  between different graphs.

* PyGFA should be at a par with GFAPy, eventhough they work in very
  different ways.  
  GFAPy allows to:  
  1. find paths without branches
  2. merge linear paths
  3. find connected components
  4. split connected components
  5. remove pbubbles(**?**)
  6. remove dead-ends
  7. remove small components
  8. multiply segments

* Perform benchmarks
  * write a random graph generator such as the one used by GFAPy (maybe
    it could be reused)
  * ... or just take lots of gfa files from somewhere

* Benchmarks:
  1. Overall parsing time
  2. specific (single information) search operation time
  3. general information search time. A search operation that
     must collect lots of data
  4. dump processing time (to file)