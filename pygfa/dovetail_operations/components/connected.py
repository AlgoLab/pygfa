def _plain_bfs_dovetails(gfa_, source):
    if source not in gfa_:
        return ()
    seen = set()
    nextlevel = {source}
    while nextlevel:
        thislevel = nextlevel
        nextlevel = set()
        for v in thislevel:
            if v not in seen:
                yield v
                seen.add(v)
                nextlevel.update(gfa_.right(v))
                nextlevel.update(gfa_.left(v))

def dovetails_nodes_connected_component(gfa_, source):
    return set(_plain_bfs_dovetails(gfa_, source))

def dovetails_nodes_connected_components(gfa_):
    seen = set()
    dovetail_nodes = gfa_.dovetails_nbunch_iter()
    for v in dovetail_nodes:
        if v not in seen:
            c = set(_plain_bfs_dovetails(gfa_, v))
            yield c
            seen.update(c)

