"""
Binary GFA (BGFA) serialization module.

This module provides functionality to convert GFA graphs to a binary format
for efficient storage and compression.

Functions:
    to_bgfa: Convert a GFA graph to BGFA binary format.
    write_bgfa: Convert a GFA graph to BGFA and save to file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygfa.gfa import GFA

__all__ = ["BGFAWriter", "to_bgfa", "write_bgfa"]

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None

from pygfa.encoding import (
    compress_integer_list_varint,
    compress_string_list,
)


class BGFAWriter:
    def __init__(self, gfa_graph: GFA):
        self._gfa = gfa_graph

    def to_bgfa(
        self,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> bytes:
        return bytes(
            b"".join(
                [
                    self.header(block_size),
                    self.names_blocks(block_size),
                    self.segments_blocks(block_size, compression_method, compression_level),
                    self.links_blocks(block_size),
                    self.paths_blocks(block_size),
                    self.walks_blocks(block_size),
                ]
            )
        )

    def write_bgfa(
        self,
        file,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> None:
        with open(file, "wb") as f:
            f.write(self.to_bgfa(block_size, compression_method, compression_level))

    def header(self, block_size: int = 1024) -> bytes:
        header_content = "H\tVN:Z:1.0\n"
        header_bytes = header_content.encode("ascii")

        padding_needed = block_size - len(header_bytes) % block_size
        if padding_needed < block_size:
            header_bytes += b"\x00" * padding_needed

        return header_bytes

    def names_blocks(self, block_size: int = 1024) -> bytes:
        names = list(self._gfa.nodes())

        for path_id in self._gfa.paths():
            names.append(path_id)

        seen = set()
        unique_names = []
        for name in names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)

        names_bytes = compress_string_list(
            unique_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )

        padding_needed = block_size - len(names_bytes) % block_size
        if padding_needed < block_size:
            names_bytes += b"\x00" * padding_needed

        return names_bytes

    def segments_blocks(
        self,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> bytes:
        sequences = []
        lengths = []
        names = []

        for node_id in sorted(self._gfa.nodes()):
            node_data = dict(self._gfa.nodes(data=True))[node_id]
            sequence = node_data.get("sequence", "*")
            sequences.append(sequence)
            lengths.append(len(sequence) if sequence != "*" else 0)
            names.append(node_id)

        lengths_bytes = compress_integer_list_varint(lengths)

        sequences_bytes = compress_string_list(
            sequences,
            compress_integer_list=compress_integer_list_varint,
            compression_method=compression_method,
            compression_level=compression_level,
        )

        result = lengths_bytes + sequences_bytes

        padding_needed = block_size - len(result) % block_size
        if padding_needed < block_size:
            result += b"\x00" * padding_needed

        return result

    def links_blocks(self, block_size: int = 1024) -> bytes:
        from_names = []
        to_names = []
        cigar_lengths = []
        cigars = []

        for u, v, data in self._gfa.edges(data=True):
            if data.get("is_dovetail", False):
                from_node = data.get("from_node", u)
                to_node = data.get("to_node", v)
                alignment = data.get("alignment", "*")

                from_names.append(from_node)
                to_names.append(to_node)
                cigar_lengths.append(len(alignment))
                cigars.append(alignment)

        from_bytes = compress_string_list(
            from_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )
        to_bytes = compress_string_list(
            to_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )
        cigar_lengths_bytes = compress_integer_list_varint(cigar_lengths)
        cigars_bytes = compress_string_list(
            cigars,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )

        result = from_bytes + to_bytes + cigar_lengths_bytes + cigars_bytes

        padding_needed = block_size - len(result) % block_size
        if padding_needed < block_size:
            result += b"\x00" * padding_needed

        return result

    def paths_blocks(self, block_size: int = 1024) -> bytes:
        path_names = []
        segment_lengths = []
        path_ids = []

        for path_id in sorted(self._gfa.paths()):
            path_data = self._gfa.paths()[path_id]
            path_names.append(path_id)
            segments = path_data.get("segments", [])
            segment_lengths.append(len(segments))
            for seg in segments:
                path_ids.append(seg)

        names_bytes = compress_string_list(
            path_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )
        segment_lengths_bytes = compress_integer_list_varint(segment_lengths)
        path_ids_bytes = compress_string_list(
            path_ids,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )

        result = names_bytes + segment_lengths_bytes + path_ids_bytes

        padding_needed = block_size - len(result) % block_size
        if padding_needed < block_size:
            result += b"\x00" * padding_needed

        return result

    def walks_blocks(self, block_size: int = 1024) -> bytes:
        return b""


def to_bgfa(
    gfa_graph: GFA,
    block_size: int = 1024,
    compression_method: str = "zstd",
    compression_level: int = 19,
) -> bytes:
    writer = BGFAWriter(gfa_graph)
    return writer.to_bgfa(block_size, compression_method, compression_level)


def write_bgfa(
    gfa_graph: GFA,
    file,
    block_size: int = 1024,
    compression_method: str = "zstd",
    compression_level: int = 19,
) -> None:
    writer = BGFAWriter(gfa_graph)
    writer.write_bgfa(file, block_size, compression_method, compression_level)
