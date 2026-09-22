"""BGFA snapshot tests.

Each instance in snapshot_instances.py is encoded to BGFA and the resulting
bytes are compared against a committed reference file in snapshots/bgfa/.
The reference files are generated with:

    pixi run python -m pytest test/test_bgfa_snapshots.py --snapshot-update

Every instance is also roundtripped through read_bgfa() and validated with
validate_bgfa() so the snapshots double as end-to-end spec checks.
"""

import os
import re
import sys
import tempfile

import pytest  # noqa: E402

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.bgfa import read_bgfa, to_bgfa, validate_bgfa  # noqa: E402
from pygfa.gfa import GFA  # noqa: E402
from snapshot_instances import INSTANCES  # noqa: E402

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots", "bgfa")

# Node attributes stored by add_node() that are not part of the BGFA
# roundtrip: "nid" is the node id (already the dict key), "sequence" is
# compared explicitly, and "slen" is excluded because a programmatically built
# node may omit it. Segment lengths are compared by _assert_segment_lengths,
# which asserts the reader restores them (via LN for a "*" sequence, from the
# sequence otherwise), so a reader that drops the length still fails.
NODE_RESERVED = {"nid", "sequence", "slen"}
# Edge attributes stored by add_edge() that the BGFA writer drops or that
# are compared explicitly: "eid" is the edge key, from/to_node, orientations
# and alignment are compared explicitly, and from_positions/to_positions/
# distance/variance/from_segment_end/to_segment_end are not preserved. That is
# a GFA1 text-format limitation, not a BGFA gap: GFA1 L lines have no columns
# for them and Edge.from_line hard-codes them, so only programmatically
# constructed edges can populate them (see snapshots/bgfa/README.md).
EDGE_RESERVED = {
    "eid",
    "from_node",
    "from_orn",
    "to_node",
    "to_orn",
    "alignment",
    "distance",
    "variance",
    "from_positions",
    "to_positions",
    "from_segment_end",
    "to_segment_end",
}

INSTANCE_IDS = [inst["id"] for inst in INSTANCES]


def _build_gfa(instance):
    """Build the GFA object for an instance (from text or via a builder)."""
    if "build" in instance:
        return instance["build"]()
    fd, path = tempfile.mkstemp(suffix=".gfa")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(instance["gfa_text"])
        return GFA.from_gfa(path)
    finally:
        os.unlink(path)


def _parse_walk_segments(walk_str):
    """Parse a walk string ('>1<2>3' or '1+2-3+') into [(name, orn), ...]."""
    result = []
    i = 0
    n = len(walk_str)
    while i < n:
        c = walk_str[i]
        if c == ">":
            orn = "+"
            i += 1
        elif c == "<":
            orn = "-"
            i += 1
        else:
            orn = None
        start = i
        while i < n and walk_str[i] not in "><":
            if orn is None and walk_str[i] in "+-":
                break
            i += 1
        name = walk_str[start:i]
        if orn is None:
            if i < n and walk_str[i] in "+-":
                orn = "+" if walk_str[i] == "+" else "-"
                i += 1
            else:
                orn = "+"
        if name:
            result.append((name, orn))
    return result


def _canonical_nodes(gfa):
    out = []
    for nid, data in gfa.nodes(data=True):
        opts = {k: v for k, v in data.items() if k not in NODE_RESERVED}
        out.append((nid, data.get("sequence", "*"), opts))
    return sorted(out)


def _assert_segment_lengths(original, readback):
    """Assert every readback segment length matches the reader's contract.

    ``slen`` is excluded from ``_canonical_nodes`` because a programmatically
    built node may legitimately omit it, but the roundtrip must still restore
    it: from ``LN`` for a ``*`` sequence (not derivable) and from the sequence
    itself otherwise.  This is what makes a reader that drops the length fail.
    """
    orig = dict(original.nodes(data=True))
    for nid, data in readback.nodes(data=True):
        seq = data.get("sequence", "*")
        slen = data.get("slen")
        if seq == "*":
            assert slen == orig[nid].get("slen"), (
                f"length of *-sequence {nid} not restored: {slen} != {orig[nid].get('slen')}"
            )
        else:
            assert slen == len(seq), f"length of {nid} ({seq!r}) not restored: {slen} != {len(seq)}"


def _canonical_edges(gfa):
    out = []
    for u, v, _k, data in gfa.edges(data=True, keys=True):
        opts = {k: v for k, v in data.items() if k not in EDGE_RESERVED}
        out.append(
            (
                data.get("from_node", u),
                data.get("from_orn", "+"),
                data.get("to_node", v),
                data.get("to_orn", "+"),
                data.get("alignment", "*"),
                opts,
            )
        )
    return sorted(out)


def _canonical_paths(gfa):
    out = []
    for pid, pdata in gfa.paths().items():
        overlaps = list(pdata.get("overlaps", []))
        # An absent overlaps field is normalized to the GFA1 "*" sentinel.
        out.append((pid, list(pdata.get("segments", [])), tuple(overlaps) if overlaps else ("*",)))
    return sorted(out)


def _canonical_walks(gfa):
    out = []
    for _wid, wdata in gfa.walks().items():
        out.append(
            (
                wdata.get("sample_id", ""),
                int(wdata.get("hapindex", 0)),
                wdata.get("seq_id", ""),
                int(wdata.get("seq_start", 0) or 0),
                int(wdata.get("seq_end", 0) or 0),
                _parse_walk_segments(wdata.get("walk", "")),
            )
        )
    return sorted(out)


def _assert_roundtrip(original, readback):
    assert _canonical_nodes(original) == _canonical_nodes(readback)
    _assert_segment_lengths(original, readback)
    assert _canonical_edges(original) == _canonical_edges(readback)
    assert _canonical_paths(original) == _canonical_paths(readback)
    assert _canonical_walks(original) == _canonical_walks(readback)


def pytest_generate_tests(metafunc):
    """Parametrize snapshot instances, optionally filtered by --snapshot-tags."""
    if "instance" not in metafunc.fixturenames:
        return
    tags = metafunc.config.getoption("--snapshot-tags")
    instances = INSTANCES
    if tags:
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        instances = [i for i in INSTANCES if wanted & set(i.get("tags", []))]
        if not instances:
            raise pytest.UsageError(f"No snapshot instances match tags: {tags}")
    metafunc.parametrize("instance", instances, ids=[i["id"] for i in instances])


def test_bgfa_snapshot(instance, request):
    gfa = _build_gfa(instance)
    comp_options = dict(instance.get("comp_options", {}))
    comp_options.setdefault("use_heuristic", False)
    comp_options.setdefault("use_numpy", False)
    block_size = instance.get("block_size", 1024)

    data = to_bgfa(gfa, block_size=block_size, compression_options=comp_options)

    # Roundtrip + validation always run so --snapshot-update also verifies.
    fd, bgfa_path = tempfile.mkstemp(suffix=".bgfa")
    os.close(fd)
    try:
        with open(bgfa_path, "wb") as f:
            f.write(data)
        readback = read_bgfa(bgfa_path)
        _assert_roundtrip(gfa, readback)
        result = validate_bgfa(bgfa_path)
        assert result["valid"] is True, f"validate_bgfa failed: {result}"
    finally:
        os.unlink(bgfa_path)

    snapshot_path = os.path.join(SNAPSHOT_DIR, f"{instance['id']}.bgfa")
    if request.config.getoption("--snapshot-update"):
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        with open(snapshot_path, "wb") as f:
            f.write(data)
        with open(snapshot_path, "rb") as f:
            assert f.read() == data, f"Failed to write snapshot {snapshot_path}"
        return

    assert os.path.exists(snapshot_path), (
        f"Missing snapshot {snapshot_path}. Run with --snapshot-update to create it."
    )
    with open(snapshot_path, "rb") as f:
        expected = f.read()
    assert data == expected, f"BGFA output for '{instance['id']}' differs from snapshot"


def test_snapshot_instance_count():
    assert len(INSTANCES) >= 100


def test_snapshot_instance_ids_unique():
    assert len(INSTANCE_IDS) == len(set(INSTANCE_IDS))
    for inst_id in INSTANCE_IDS:
        assert re.fullmatch(r"[a-z0-9_]+", inst_id), f"Invalid snapshot id: {inst_id!r}"