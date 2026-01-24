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

        with open(file_path, "rb") as f:
            bgfa_data = f.read()

        return self._parse_bgfa_data(bgfa_data)

    def _parse_bgfa_data(self, bgfa_data: bytes) -> GFA:
        """Parse BGFA binary data and create a GFA graph.

        :param bgfa_data: Binary BGFA data
        :return: GFA graph object
        """
        from pygfa.gfa import GFA
        from pygfa.graph_element import node, edge as ge

        gfa = GFA()

        # Parse header
        header = self._parse_header(bgfa_data)
        logger.info(f"Header parsed: {header}")

        # Parse segment names
        segment_names = self._parse_segment_names(bgfa_data, header)
        logger.info(f"Segment names: {segment_names}")

        # Parse segments
        segments = self._parse_segments(bgfa_data, header, segment_names)
        logger.info(f"Segments: {segments}")

        # Add nodes to GFA graph
        for segment_name, segment_data in segments.items():
            gfa.add_node(
                node.Node(
                    segment_name,
                    segment_data["sequence"],
                    segment_data["length"],
                    opt_fields={}
                )
            )

        # Parse links
        links = self._parse_links(bgfa_data, header, segment_names)
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
                    is_dovetail=True
                )
            )

        return gfa

    def _parse_header(self, bgfa_data: bytes) -> dict:
        """Parse the BGFA file header.

        :param bgfa_data: Binary BGFA data
        :return: Dictionary containing header information
        """
        offset = 0

        # Read version (uint16)
        version = int.from_bytes(bgfa_data[offset:offset+2], byteorder="big", signed=False)
        offset += 2

        # Read counts
        s_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8
        l_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8
        p_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8
        w_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8

        # Read offsets
        s_offset = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8
        l_offset = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8
        p_offset = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8
        w_offset = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
        offset += 8

        # Read block_size (uint16)
        block_size = int.from_bytes(bgfa_data[offset:offset+2], byteorder="big", signed=False)
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
            "s_offset": s_offset,
            "l_offset": l_offset,
            "p_offset": p_offset,
            "w_offset": w_offset,
            "block_size": block_size,
            "header_text": header_text,
            "header_size": offset
        }

    def _parse_segment_names(self, bgfa_data: bytes, header: dict) -> list:
        """Parse segment names from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :return: List of segment names
        """
        if header["s_len"] == 0:
            return []

        offset = header["header_size"]
        segment_names = []

        # Read segment names (null-terminated strings)
        while len(segment_names) < header["s_len"] and offset < len(bgfa_data):
            name = ""
            while offset < len(bgfa_data) and bgfa_data[offset] != 0:
                name += chr(bgfa_data[offset])
                offset += 1
            offset += 1  # Skip null terminator
            if name:  # Only add non-empty names
                segment_names.append(name)

        return segment_names

    def _parse_segments(self, bgfa_data: bytes, header: dict, segment_names: list) -> dict:
        """Parse segments from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :return: Dictionary mapping segment names to segment data
        """
        if header["s_len"] == 0:
            return {}

        # The segments block comes after the names block
        offset = header["s_offset"]
        segments = {}

        # Read segments blocks
        segments_read = 0
        while segments_read < header["s_len"] and offset < len(bgfa_data):
            # Read block header
            record_num = int.from_bytes(bgfa_data[offset:offset+2], byteorder="big", signed=False)
            offset += 2
            compressed_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
            offset += 8
            uncompressed_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
            offset += 8
            compression_str = int.from_bytes(bgfa_data[offset:offset+2], byteorder="big", signed=False)
            offset += 2

            # Read segment data
            segment_data = bgfa_data[offset:offset+compressed_len]
            offset += compressed_len

            # For now, assume simple format without compression
            # In a real implementation, we would decompress based on compression_str
            pos = 0
            for _ in range(record_num):
                # Read segment ID (uint64) - this is the index in the segment_names list
                segment_id = int.from_bytes(segment_data[pos:pos+8], byteorder="big", signed=False)
                pos += 8
                # Read sequence length (uint64)
                sequence_length = int.from_bytes(segment_data[pos:pos+8], byteorder="big", signed=False)
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
                    "sequence": sequence,
                    "length": sequence_length
                }
                segments_read += 1

        return segments

    def _parse_links(self, bgfa_data: bytes, header: dict, segment_names: list) -> list:
        """Parse links from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :return: List of link dictionaries
        """
        if header["l_len"] == 0:
            return []

        offset = header["l_offset"]
        links = []

        # Read links blocks
        links_read = 0
        while links_read < header["l_len"] and offset < len(bgfa_data):
            # Read block header
            record_num = int.from_bytes(bgfa_data[offset:offset+2], byteorder="big", signed=False)
            offset += 2
            compressed_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
            offset += 8
            uncompressed_len = int.from_bytes(bgfa_data[offset:offset+8], byteorder="big", signed=False)
            offset += 8
            compression_fromto = int.from_bytes(bgfa_data[offset:offset+2], byteorder="big", signed=False)
            offset += 2
            compression_cigars = int.from_bytes(bgfa_data[offset:offset+4], byteorder="big", signed=False)
            offset += 4

            # Read link data
            link_data = bgfa_data[offset:offset+compressed_len]
            offset += compressed_len

            # For now, assume simple format without compression
            pos = 0
            for _ in range(record_num):
                # Read from node (uint64) - this is the index in the segment_names list
                from_node_id = int.from_bytes(link_data[pos:pos+8], byteorder="big", signed=False)
                pos += 8
                # Read to node (uint64) - this is the index in the segment_names list
                to_node_id = int.from_bytes(link_data[pos:pos+8], byteorder="big", signed=False)
                pos += 8
                # Read cigar string (null-terminated string)
                cigar = ""
                while pos < len(link_data) and link_data[pos] != 0:
                    cigar += chr(link_data[pos])
                    pos += 1
                pos += 1  # Skip null terminator

                # Convert node IDs to names using segment_names list
                from_name = segment_names[from_node_id - 1] if 0 < from_node_id <= len(segment_names) else f"node_{from_node_id}"
                to_name = segment_names[to_node_id - 1] if 0 < to_node_id <= len(segment_names) else f"node_{to_node_id}"
                orientation_from = "+"
                orientation_to = "+"

                links.append({
                    "from_node": from_name,
                    "from_orn": orientation_from,
                    "to_node": to_name,
                    "to_orn": orientation_to,
                    "alignment": cigar
                })
                links_read += 1

        return links


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
        segments_blocks = self.segments_blocks(block_size, compression_method, compression_level)
        links_blocks = self.links_blocks(block_size)
        paths_blocks = self.paths_blocks(block_size)
        walks_blocks = self.walks_blocks(block_size)

        buffer.write(names_blocks)
        buffer.write(segments_blocks)
        buffer.write(links_blocks)
        buffer.write(paths_blocks)
        buffer.write(walks_blocks)

        # Compute actual offsets
        header_size = len(placeholder_header)
        s_offset = header_size + len(names_blocks)
        l_offset = header_size + len(names_blocks) + len(segments_blocks)
        p_offset = header_size + len(names_blocks) + len(segments_blocks) + len(links_blocks)
        w_offset = header_size + len(names_blocks) + len(segments_blocks) + len(links_blocks) + len(paths_blocks)

        # Seek back and write real header
        buffer.seek(0)
        self._write_header(buffer, s_len, l_len, p_len, w_len, s_offset, l_offset, p_offset, w_offset, block_size)

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

    def _write_header(self, buffer, s_len, l_len, p_len, w_len, s_offset, l_offset, p_offset, w_offset, block_size):
        """Write BGFA header in binary format."""
        # Write version (uint16)
        buffer.write(struct.pack('>H', 1))  # big-endian, unsigned short

        # Write counts
        buffer.write(struct.pack('>Q', s_len))  # uint64
        buffer.write(struct.pack('>Q', l_len))
        buffer.write(struct.pack('>Q', p_len))
        buffer.write(struct.pack('>Q', w_len))

        # Write offsets
        buffer.write(struct.pack('>Q', s_offset))
        buffer.write(struct.pack('>Q', l_offset))
        buffer.write(struct.pack('>Q', p_offset))
        buffer.write(struct.pack('>Q', w_offset))

        # Write block_size (uint16)
        buffer.write(struct.pack('>H', block_size))

        # Write header text (C string)
        header_text = "H\tVN:Z:1.0"
        buffer.write(header_text.encode('ascii'))
        buffer.write(b'\x00')  # null terminator

    def header(self, block_size: int = 1024) -> bytes:
        """Create placeholder header with zeros."""
        buffer = io.BytesIO()
        self._write_header(buffer, 0, 0, 0, 0, 0, 0, 0, 0, block_size)
        return buffer.getvalue()

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



