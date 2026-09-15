# BGFA Snapshot References

This directory holds the reference `.bgfa` files for the snapshot test suite in
`test/test_bgfa_snapshots.py`. Each file is the byte-exact BGFA output produced
by encoding one instance from `test/snapshot_instances.py` with
`use_heuristic=False` and `use_numpy=False` (deterministic output).

## Regenerating the snapshots

Run the suite with `--snapshot-update`:

```bash
pixi run python -m pytest test/test_bgfa_snapshots.py --snapshot-update
```

This rewrites every `{id}.bgfa` file and also runs the roundtrip
(`read_bgfa`) and validation (`validate_bgfa`) checks on each instance, so a
regeneration only succeeds if the writer, reader, and validator agree.

## When to regenerate

- After changing the BGFA writer, reader, or any codec in `pygfa/encoding/`.
- After upgrading a compression library (zstd, gzip, lzma, lz4, brotli, ...)
  in the pixi environment — compressed blobs may change bytes while remaining
  valid.

Before committing regenerated snapshots, review the diff with
`xxd`/`bin/bgfatools dump` to confirm the change is intended.

## Adding a new instance

1. Add a dict to `INSTANCES` in `test/snapshot_instances.py` with a unique
   `id`, either `gfa_text` (parsed via `GFA.from_gfa`) or a `build` callable,
   plus optional `comp_options`, `block_size`, and `tags`.
2. Run `pytest test/test_bgfa_snapshots.py --snapshot-update -k <id>` to
   generate the reference file.
3. Run `pytest test/test_bgfa_snapshots.py -k <id>` to confirm the comparison
   passes.

## Coverage

The 122 instances cover: file header, segments (structure, all string codecs,
all integer metadata codecs, 2-bit exception tables, uint16 record counts),
links (orientations, bit-packing at 64-bit word boundaries, all CIGAR
decompositions, all integer endpoint codecs), paths (structure, NUMID/STRID
walk decompositions, CIGAR decompositions), walks (structure, decompositions,
uints-delta positions, string codecs), the opt-fields block (section 6),
multi-block chunking, and combined graphs.

## Known fidelity gaps

The roundtrip comparison in the snapshot test compares the elements the BGFA
format can represent. The following GFA data is intentionally not preserved
by the BGFA writer/reader and is excluded from the comparison:

- **Multiple overlaps per path**: only `overlaps[0]` is stored per path
  (`_write_paths_block`), so a path line `P\tp1\ts1+,s2+,s3+\t10M,5M`
  (`\t` is a literal tab) roundtrips as a single `10M` overlap.
- **`slen` / `sequence_length`**: parsed from the text, but not reconstructed
  by the reader (it is derivable from the sequence).
- **Edge positions and gap fields**: `from_positions`, `to_positions`,
  `distance`, and `variance` are dropped by the writer.