    def __eq__(self, other):
        """
        :TODO:
            * make a lut for subgraphs (try to think for a way to write
              _make_edge_lut in a reusable way...
        """
        try:
            # Nodes must be defined, so there is no reason to
            # create a LUT
            for nid, node_ in self.nodes_iter(data=True):
                if node_ != other.nodes(identifier=nid):
                    return False

            self_edge_table = self._make_edge_table()
            other_edge_table = other._make_edge_table()
            self_lut, self_edge_virtuals = self._make_edge_lut()
            other_lut, other_edge_virtuals = other._make_edge_lut()
            for alias, list_ids in self_lut.items():
                while len(list_ids):
                    id_ = list_ids.pop()
                    found = False
                    index = 0
                    edge_ = self._look_for_edge(id_, self_edge_table)
                    while not found and index < len(other_lut[alias]):
                        other_id = other_lut[alias][index]
                        if edge_ == other._look_for_edge(other_id, other_edge_table):
                            found = True
                        else:
                            index += 1
                    if not found:
                        return False
                    # if is found remove it from list
                    # to speed up next searches.
                    other_lut[alias].pop(index)
                # if other_lut has other ids attached to that alias, then
                # graphs are not equals
                # if not len(other_lut[alias]):
                #    return False

            for edge_ in self_edge_virtuals:
                found, index = _index(edge_, other_edge_virtuals)
                if not found:
                    return False
                other_edge_virtuals.pop(index)

            # I think it's difficult to have lots of subgraphs
            # If I am wrong a subgraphs lut will be made and the comparison
            # should be nearly linear in time
            self_subgraphs = [sub.as_dict() for sub in self.subgraphs().values()]
            other_subgraphs = [sub.as_dict() for sub in other.subgraphs().values()]
            for sub_ in self_subgraphs:
                found, index = _index(sub_, other_subgraphs)
                if not found:
                    return False
                other_subgraphs.pop(index)

        except (AttributeError, KeyError) as e:
            return False
        return True
