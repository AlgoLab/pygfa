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
    from pygfa.graph_element import node, edge as ge

__all__ = ["BGFAWriter", "ReaderBGFA", "to_bgfa", "write_bgfa", "read_bgfa"]

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None

import gzip
import lzma

from pygfa.encoding import (
    compress_integer_list_varint,
    compress_string_list,
)

import struct
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


import io
import struct


class ReaderBGFA:
    def __init__(self):
        pass

    def read_bgfa(self, file_path: str) -> GFA:
        """Read a BGFA file and create the corresponding GFA graph.

        :param file_path: Path to the BGFA file
        :return: GFA graph object
        """
        from pygfa.gfa import GFA
        from pygfa.graph_element import node, edge as ge

        with open(file_path, "rb") as f:
            bgfa_data = f.read()

        gfa = GFA()

        # Parse header
        header = self._parse_header(bgfa_data)
        # Store header information in the GFA object
        gfa._header_info = header.copy()
        logger.info(f"Header parsed: {header}")
        # Parse segment names
        offset = 36 + len(header["header"])
        segment_names = []
        for _ in range(ceiling(header["S_len"] / header["block_size"])):
            segment_names_block, read_bytes = self._parse_segment_names_block(
                bgfa_data, header, offset
            )
            offset += read_bytes
            for name in segment_names_block:
                segment_names.append(segment_names_block)
        logger.info(f"Segment names: {segment_names}")

        # Parse segments
        segments, offset_after_segments = self._parse_segments(
            bgfa_data, header, segment_names, offset_after_names
        )
        logger.info(f"Segments: {segments}")

        # Add nodes to GFA graph with segment IDs
        for segment_name, segment_data in segments.items():
            n = node.Node(
                segment_name,
                segment_data["sequence"],
                segment_data["length"],
                opt_fields={},
            )
            gfa.add_node(n)
            # Store segment ID (0-based) in the graph
            # The GFA class has a _segment_map attribute
            gfa._segment_map[segment_name] = segment_data.get("segment_id", None)

        # Parse links
        links, offset_after_links = self._parse_links(
            bgfa_data, header, segment_names, offset_after_segments
        )
        logger.info(f"Links: {links}")

        # Add edges to GFA graph
        for link in links:
            gfa.add_edge(
                ge.Edge(
                    None,  # eid
                    link["from_node"],
                    link["from_orn"],
                    link["to_node"],
                    link["to_orn"],
                    (None, None),  # from_positions
                    (None, None),  # to_positions
                    link["alignment"],
                    None,  # distance
                    None,  # variance
                    opt_fields={},
                    is_dovetail=True,
                )
            )

        # TODO: Parse paths
        # TODO: Parse walks

        return gfa

    def _parse_header(self, bgfa_data: bytes) -> dict:
        """Parse the BGFA file header.

        :param bgfa_data: Binary BGFA data
        :return: Dictionary containing header information
        """
        offset = 0

        # Read version (uint16)
        version = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="big", signed=False
        )
        offset += 2

        # Read counts
        s_len = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="big", signed=False
        )
        offset += 8
        l_len = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="big", signed=False
        )
        offset += 8
        p_len = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="big", signed=False
        )
        offset += 8
        w_len = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="big", signed=False
        )
        offset += 8

        # Read block_size (uint16)
        block_size = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="big", signed=False
        )
        offset += 2

        # Read header text (C string)
        header_text = ""
        while offset < len(bgfa_data) and bgfa_data[offset] != 0:
            header_text += chr(bgfa_data[offset])
            offset += 1
        offset += 1  # Skip null terminator

        return {
            "version": version,
            "s_len": s_len,
            "l_len": l_len,
            "p_len": p_len,
            "w_len": w_len,
            "block_size": block_size,
            "header_text": header_text,
            "header_size": offset,
        }

    def _parse_segment_names_block(
        self, bgfa_data: bytes, header: dict, offset: int
    ) -> (list[str], int):
        """Parse segment names from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param offset: number of bytes to skip
        :return: (List of segment names, number of bytes read)
        """

        segment_names = []
        initial_offset = offset
        # Read block header
        record_num = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="big", signed=False
        )
        offset += 2
        compressed_len = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="big", signed=False
        )
        offset += 8
        uncompressed_len = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="big", signed=False
        )
        offset += 8
        compression_names = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="big", signed=False
        )
        offset += 2

        # Read payload
        payload = bgfa_data[offset : offset + compressed_len]
        offset += compressed_len

        # Decode payload according to compression_names
        # For now, assume identity (0x0000): payload is concatenated null-terminated strings
        if compression_names != 0x0000:
            raise ValueError(f"Unsupported compression_names: {compression_names:#06x}")

        pos = 0
        for _ in range(record_num):
            name_bytes = bytearray()
            while pos < len(payload) and payload[pos] != 0:
                name_bytes.append(payload[pos])
                pos += 1
                pos += 1  # skip null terminator
                name = name_bytes.decode("ascii")
                segment_names.append(name)

        # if the total length of the decoded segment names is more than
        # uncompressed_len, then throw an exception
        return segment_names, offset - initial_offset

    def _parse_segments(
        self, bgfa_data: bytes, header: dict, segment_names: list, start_offset: int
    ) -> tuple[dict, int]:
        """Parse segments from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where segments blocks start
        :return: (Dictionary mapping segment names to segment data, offset after reading all segments blocks)
        """
        if header["s_len"] == 0:
            return {}, start_offset

        offset = start_offset
        segments = {}

        # Read segments blocks
        segments_read = 0
        while segments_read < header["s_len"] and offset < len(bgfa_data):
            # Read block header
            record_num = int.from_bytes(
                bgfa_data[offset : offset + 2], byteorder="big", signed=False
            )
            offset += 2
            compressed_len = int.from_bytes(
                bgfa_data[offset : offset + 8], byteorder="big", signed=False
            )
            offset += 8
            uncompressed_len = int.from_bytes(
                bgfa_data[offset : offset + 8], byteorder="big", signed=False
            )
            offset += 8
            compression_str = int.from_bytes(
                bgfa_data[offset : offset + 2], byteorder="big", signed=False
            )
            offset += 2

            # Read segment data
            segment_data = bgfa_data[offset : offset + compressed_len]
            offset += compressed_len

            # For now, assume simple format without compression
            # In a real implementation, we would decompress based on compression_str
            pos = 0
            for _ in range(record_num):
                # Read segment ID (uint64) - this is the index in the segment_names list
                segment_id = int.from_bytes(
                    segment_data[pos : pos + 8], byteorder="big", signed=False
                )
                pos += 8
                # Read sequence length (uint64)
                sequence_length = int.from_bytes(
                    segment_data[pos : pos + 8], byteorder="big", signed=False
                )
                pos += 8
                # Read sequence (null-terminated string)
                sequence = ""
                while pos < len(segment_data) and segment_data[pos] != 0:
                    sequence += chr(segment_data[pos])
                    pos += 1
                pos += 1  # Skip null terminator

                # Get segment name from segment_names list using 1-based indexing
                if 0 < segment_id <= len(segment_names):
                    segment_name = segment_names[segment_id - 1]
                else:
                    segment_name = f"segment_{segment_id}"

                segments[segment_name] = {
                    "segment_id": segment_id - 1,  # Convert to 0-based
                    "sequence": sequence,
                    "length": sequence_length,
                }
                segments_read += 1

        return segments, offset

    def _parse_links(
        self, bgfa_data: bytes, header: dict, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse links from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where links blocks start
        :return: (List of link dictionaries, offset after reading all links blocks)
        """
        if header["l_len"] == 0:
            return [], start_offset

        offset = start_offset
        links = []

        # Read links blocks
        links_read = 0
        while links_read < header["l_len"] and offset < len(bgfa_data):
            # Read block header
            record_num = int.from_bytes(
                bgfa_data[offset : offset + 2], byteorder="big", signed=False
            )
            offset += 2
            compressed_len = int.from_bytes(
                bgfa_data[offset : offset + 8], byteorder="big", signed=False
            )
            offset += 8
            uncompressed_len = int.from_bytes(
                bgfa_data[offset : offset + 8], byteorder="big", signed=False
            )
            offset += 8
            compression_fromto = int.from_bytes(
                bgfa_data[offset : offset + 2], byteorder="big", signed=False
            )
            offset += 2
            compression_cigars = int.from_bytes(
                bgfa_data[offset : offset + 4], byteorder="big", signed=False
            )
            offset += 4

            # Read link data
            link_data = bgfa_data[offset : offset + compressed_len]
            offset += compressed_len

            # For now, assume simple format without compression
            pos = 0
            for _ in range(record_num):
                # Read from node (uint64) - this is the index in the segment_names list
                from_node_id = int.from_bytes(
                    link_data[pos : pos + 8], byteorder="big", signed=False
                )
                pos += 8
                # Read to node (uint64) - this is the index in the segment_names list
                to_node_id = int.from_bytes(
                    link_data[pos : pos + 8], byteorder="big", signed=False
                )
                pos += 8
                # Read cigar string (null-terminated string)
                cigar = ""
                while pos < len(link_data) and link_data[pos] != 0:
                    cigar += chr(link_data[pos])
                    pos += 1
                pos += 1  # Skip null terminator

                # Convert node IDs to names using segment_names list
                from_name = (
                    segment_names[from_node_id - 1]
                    if 0 < from_node_id <= len(segment_names)
                    else f"node_{from_node_id}"
                )
                to_name = (
                    segment_names[to_node_id - 1]
                    if 0 < to_node_id <= len(segment_names)
                    else f"node_{to_node_id}"
                )
                orientation_from = "+"
                orientation_to = "+"

                links.append(
                    {
                        "from_node": from_name,
                        "from_orn": orientation_from,
                        "to_node": to_name,
                        "to_orn": orientation_to,
                        "alignment": cigar,
                    }
                )
                links_read += 1

        return links, offset


class BGFAWriter:
    def __init__(self, gfa_graph: GFA):
        self._gfa = gfa_graph

    def to_bgfa(
        self,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> bytes:
        # Create a BytesIO buffer
        buffer = io.BytesIO()

        # Compute counts
        s_len = len(self._gfa.nodes())
        l_len = len(self._gfa.edges())
        p_len = len(self._gfa.paths())
        w_len = len(self._gfa.walks())

        # Write placeholder header
        placeholder_header = self.header(block_size)
        buffer.write(placeholder_header)

        # Write the blocks
        names_blocks = self.names_blocks(block_size)
        segments_blocks = self.segments_blocks(
            block_size, compression_method, compression_level
        )
        links_blocks = self.links_blocks(block_size)
        paths_blocks = self.paths_blocks(block_size)
        walks_blocks = self.walks_blocks(block_size)

        buffer.write(names_blocks)
        buffer.write(segments_blocks)
        buffer.write(links_blocks)
        buffer.write(paths_blocks)
        buffer.write(walks_blocks)

        # Seek back and write real header
        buffer.seek(0)
        self._write_header(
            buffer,
            s_len,
            l_len,
            p_len,
            w_len,
            block_size,
        )

        # Get the entire buffer as bytes
        return buffer.getvalue()

    def write_bgfa(
        self,
        file,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> None:
        with open(file, "wb") as f:
            f.write(self.to_bgfa(block_size, compression_method, compression_level))

    def _write_header(
        self,
        buffer,
        s_len,
        l_len,
        p_len,
        w_len,
        block_size,
    ):
        """Write BGFA header in binary format."""
        # Write version (uint16)
        buffer.write(struct.pack(">H", 1))  # big-endian, unsigned short

        # Write counts
        buffer.write(struct.pack(">Q", s_len))  # uint64
        buffer.write(struct.pack(">Q", l_len))
        buffer.write(struct.pack(">Q", p_len))
        buffer.write(struct.pack(">Q", w_len))

        # Write block_size (uint16)
        buffer.write(struct.pack(">H", block_size))

        # Write header text (C string)
        header_text = "H\tVN:Z:1.0"
        buffer.write(header_text.encode("ascii"))
        buffer.write(b"\x00")  # null terminator

    def header(self, block_size: int = 1024) -> bytes:
        """Create placeholder header with zeros."""
        buffer = io.BytesIO()
        self._write_header(buffer, 0, 0, 0, 0, block_size)
        return buffer.getvalue()

    def names_blocks(self, block_size: int = 1024) -> bytes:
        # Get all nodes sorted by segment ID (which should be stored in _segment_map)
        segment_map = getattr(self._gfa, "_segment_map", {})
        if not segment_map:
            nodes_list = list(self._gfa.nodes())
            segment_map = {name: idx for idx, name in enumerate(sorted(nodes_list))}
            self._gfa._segment_map = segment_map

        # Sort names by segment ID
        names_by_id = sorted(segment_map.items(), key=lambda x: x[1])
        segment_names = [
            name for name, seg_id in names_by_id
        ]  # only segment names, not paths

        # Split into blocks of size block_size
        all_blocks = []
        total_segments = len(segment_names)
        for start in range(0, total_segments, block_size):
            chunk = segment_names[start : start + block_size]
            record_num = len(chunk)

            # Payload: each name as null-terminated ASCII string
            payload = b"".join([name.encode("ascii") + b"\x00" for name in chunk])
            compressed_len = len(payload)
            uncompressed_len = compressed_len  # identity compression
            compression_names = 0x0000  # identity for both lengths and strings

            # Write block header
            header = (
                record_num.to_bytes(2, byteorder="big", signed=False)
                + compressed_len.to_bytes(8, byteorder="big", signed=False)
                + uncompressed_len.to_bytes(8, byteorder="big", signed=False)
                + compression_names.to_bytes(2, byteorder="big", signed=False)
            )
            all_blocks.append(header + payload)

        # Concatenate all blocks
        result = b"".join(all_blocks)
        # No additional padding needed because blocks are already formed
        return result

    def segments_blocks(
        self,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> bytes:
        # Get segment map
        segment_map = getattr(self._gfa, "_segment_map", {})
        if not segment_map:
            nodes_list = list(self._gfa.nodes())
            segment_map = {name: idx for idx, name in enumerate(sorted(nodes_list))}
            self._gfa._segment_map = segment_map

        # Sort nodes by segment ID
        sorted_items = sorted(segment_map.items(), key=lambda x: x[1])

        # Prepare data for each segment
        segments_data = []
        for node_id, seg_id in sorted_items:
            node_data = dict(self._gfa.nodes(data=True))[node_id]
            sequence = node_data.get("sequence", "*")
            seq_len = len(sequence) if sequence != "*" else 0
            # Each segment entry: segment_id (uint64), sequence_length (uint64), sequence (null-terminated string)
            entry = (
                seg_id.to_bytes(8, byteorder="big", signed=False)
                + seq_len.to_bytes(8, byteorder="big", signed=False)
                + sequence.encode("ascii")
                + b"\x00"
            )
            segments_data.append(entry)

        # Split into blocks
        all_blocks = []
        total_segments = len(segments_data)
        for start in range(0, total_segments, block_size):
            chunk = segments_data[start : start + block_size]
            record_num = len(chunk)
            payload = b"".join(chunk)
            compressed_len = len(payload)
            uncompressed_len = compressed_len  # identity compression
            compression_str = 0x0000  # identity for sequences (and for IDs/lengths)

            # Write block header
            header = (
                record_num.to_bytes(2, byteorder="big", signed=False)
                + compressed_len.to_bytes(8, byteorder="big", signed=False)
                + uncompressed_len.to_bytes(8, byteorder="big", signed=False)
                + compression_str.to_bytes(2, byteorder="big", signed=False)
            )
            all_blocks.append(header + payload)

        # Concatenate all blocks
        result = b"".join(all_blocks)
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


def read_bgfa(file_path: str) -> GFA:
    """Read a BGFA file and create the corresponding GFA graph.

    :param file_path: Path to the BGFA file
    :return: GFA graph object
    """
    reader = ReaderBGFA()
    return reader.read_bgfa(file_path)


def write_bgfa(
    gfa_graph: GFA,
    file,
    block_size: int = 1024,
    compression_method: str = "zstd",
    compression_level: int = 19,
) -> None:
    writer = BGFAWriter(gfa_graph)
    writer.write_bgfa(file, block_size, compression_method, compression_level)
