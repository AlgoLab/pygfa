"""
Binary GFA (BGFA) serialization module.

This module provides functionality to convert GFA graphs to a binary format
for efficient storage and compression.

Functions:
    to_bgfa: Convert a GFA graph to BGFA binary format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygfa.gfa import GFA
    from pygfa.graph_element import node, edge as ge

__all__ = ["BGFAWriter", "ReaderBGFA", "to_bgfa", "read_bgfa"]

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

# GFA and graph_element imports are moved inside methods to avoid circular imports

import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


import io
import math


class ReaderBGFA:
    def __init__(self):
        pass

    def read_bgfa(
        self,
        file_path: str,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
    ) -> "GFA":
        """Read a BGFA file and create the corresponding GFA graph.

        :param file_path: Path to the BGFA file
        :param verbose: If True, log detailed information
        :param debug: If True, log debug information
        :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
        :return: GFA graph object
        """
        from pygfa.gfa import GFA
        from pygfa.graph_element import node, edge as ge

        # Determine log level based on verbosity
        if debug:
            log_level = logging.DEBUG
        elif verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARNING

        # Only create log file if we're actually logging something
        if log_level <= logging.INFO:
            if logfile is None:
                # Create a temporary log file
                temp_log = tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".log"
                )
                logfile = temp_log.name
                temp_log.close()
                print(f"Logging to temporary file: {logfile}")
        else:
            # If we're not logging, use a dummy logfile
            import os
            if os.name == 'nt':  # Windows
                logfile = "NUL"
            else:  # Unix-like
                logfile = "/dev/null"

        # Clear any existing handlers
        logging.getLogger().handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        handlers = []

        # Only add file handler if we're actually logging to a file
        import os
        if logfile != "/dev/null" and logfile != "NUL":
            file_handler = logging.FileHandler(logfile)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

        # Always add stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

        # Configure root logger
        logging.basicConfig(level=log_level, handlers=handlers)

        # Get logger for this module
        logger = logging.getLogger(__name__)

        logger.info(f"Reading BGFA file: {file_path}")
        if debug:
            logger.debug(f"Debug mode enabled, logfile: {logfile}")

        with open(file_path, "rb") as f:
            bgfa_data = f.read()

        gfa = GFA()

        # Parse header
        header = self._parse_header(bgfa_data)
        # Store header information in the GFA object
        gfa._header_info = header.copy()
        logger.info(
            f"Header parsed: version={header['version']}, s_len={header['s_len']}, "
            f"l_len={header['l_len']}, p_len={header['p_len']}, w_len={header['w_len']}"
        )
        logger.debug(f"Full header: {header}")
        # Parse segment names
        offset = header["header_size"]
        segment_names = []
        num_blocks = math.ceil(header["s_len"] / header["block_size"])
        logger.info(f"Parsing {num_blocks} segment name blocks")
        for i in range(num_blocks):
            segment_names_block, read_bytes = self._parse_segment_names_block(
                bgfa_data, offset
            )
            offset += read_bytes
            segment_names.extend(segment_names_block)
            logger.info(
                f"Parsed segment names block {i+1}: {len(segment_names_block)} names"
            )
        logger.info(f"Total segment names: {len(segment_names)}")
        logger.debug(f"First 5 segment names: {segment_names[:5]}")

        # Parse segments
        num_blocks = math.ceil(header["s_len"] / header["block_size"])
        logger.info(f"Parsing {num_blocks} segment blocks")
        for i in range(num_blocks):
            segment_block, read_bytes = self._parse_segments_block(bgfa_data, offset)
            offset += read_bytes
            logger.info(f"Parsed segments block {i+1}: {len(segment_block)} segments")
            # Add nodes to GFA graph with segment IDs
            for segment_id, segment_data in segment_block.items():
                # Get node name from segment_names list (0-based index)
                if 0 <= segment_id < len(segment_names):
                    node_name = segment_names[segment_id]
                else:
                    node_name = f"segment_{segment_id}"

                n = node.Node(
                    node_name,
                    segment_data["sequence"],
                    segment_data["length"],
                    opt_fields={},
                )
                gfa.add_node(n)
                # The GFA class has a _segment_map attribute
                gfa._segment_map[node_name] = segment_id
                if i == 0 and segment_id < 5:  # Log first few segments
                    logger.debug(
                        f"Added segment {segment_id}: {node_name}, length={segment_data['length']}"
                    )
                elif i == 0 and segment_id == 5:
                    logger.debug("... (remaining segments logged at debug level)")

        # Parse links
        num_blocks = math.ceil(header["l_len"] / header["block_size"])
        logger.info(f"Parsing {num_blocks} link blocks")
        for i in range(num_blocks):
            links, read_bytes = self._parse_links_block(
                bgfa_data, segment_names, offset
            )
            offset += read_bytes
            logger.info(f"Parsed links block {i+1}: {len(links)} links")

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
            if verbose:
                logger.info(f"Added {len(links)} links from block {i+1}")
                if i == 0 and links:
                    logger.debug(f"First link: {links[0]}")

        # TODO: Parse paths
        # TODO: Parse walks

        logger.info(
            f"BGFA reading complete. Graph has {len(gfa.nodes())} nodes and {len(gfa.edges())} edges"
        )
        return gfa

    def _parse_header(self, bgfa_data: bytes) -> dict:
        """Parse the BGFA file header.

        :param bgfa_data: Binary BGFA data
        :return: Dictionary containing header information
        """
        offset = 0

        # Read version (uint16)
        version = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        # Read block_size (uint16)
        block_size = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2

        # Read counts (uint64)
        s_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        l_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        p_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        w_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

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
        self, bgfa_data: bytes, offset: int
    ) -> tuple[list[str], int]:
        """Parse segment names from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param offset: number of bytes to skip
        :return: (List of segment names, number of bytes read)
        """

        segment_names = []
        initial_offset = offset
        # Read block header - new order: uint16 fields first
        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_names = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

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
            if pos >= len(payload):
                raise ValueError("Missing null terminator in segment name")
            pos += 1  # skip null terminator
            name = name_bytes.decode("ascii")
            segment_names.append(name)

        # Verify that the total length of the decoded segment names (including null terminators) matches uncompressed_len
        if pos != uncompressed_len:
            raise ValueError(
                f"Segment names length mismatch: expected {uncompressed_len} bytes, got {pos}"
            )
        return segment_names, offset - initial_offset

    def _parse_segments_block(
        self, bgfa_data: bytes, start_offset: int
    ) -> tuple[dict, int]:
        """Parse segments from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where segments blocks start
        :return: (Dictionary mapping segment names to segment data, offset after reading all segments blocks)
        """
        offset = start_offset
        segments = {}

        # Read block header - new order: uint16 fields first
        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_str = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

        # Read segment data
        segment_data = bgfa_data[offset : offset + compressed_len]
        offset += compressed_len

        # For now, assume simple format without compression
        # In a real implementation, we would decompress based on compression_str
        pos = 0
        for _ in range(record_num):
            # Read segment ID (uint64) - this is the index in the segment_names list
            segment_id = struct.unpack_from("<Q", segment_data, pos)[0]
            pos += 8
            # Read sequence length (uint64)
            sequence_length = struct.unpack_from("<Q", segment_data, pos)[0]
            pos += 8
            # Read sequence (null-terminated string)
            sequence_bytes = bytearray()
            while pos < len(segment_data) and segment_data[pos] != 0:
                sequence_bytes.append(segment_data[pos])
                pos += 1
            pos += 1  # Skip null terminator
            sequence = sequence_bytes.decode("ascii")

            segments[segment_id] = {
                "sequence": sequence,
                "length": sequence_length,
            }

        return segments, offset

    def _parse_links_block(
        self, bgfa_data: bytes, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse links from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where links blocks start
        :return: (List of link dictionaries, offset after reading all links blocks)
        """

        offset = start_offset
        links = []

        # Read block header - new order: uint16 fields first
        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_fromto = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_cigars = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

        # Read link data
        link_data = bgfa_data[offset : offset + compressed_len]
        offset += compressed_len

        # For now, assume simple format without compression
        pos = 0
        for _ in range(record_num):
            # Read from node (uint64) - this is the index in the segment_names list
            from_node_id = struct.unpack_from("<Q", link_data, pos)[0]
            pos += 8
            # Read to node (uint64) - this is the index in the segment_names list
            to_node_id = struct.unpack_from("<Q", link_data, pos)[0]
            pos += 8
            # Read cigar string (null-terminated string)
            cigar_bytes = bytearray()
            while pos < len(link_data) and link_data[pos] != 0:
                cigar_bytes.append(link_data[pos])
                pos += 1
            pos += 1  # Skip null terminator
            cigar = cigar_bytes.decode("ascii")

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

        return links, offset

    def _parse_paths_blocks(
        self, bgfa_data: bytes, header: dict, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse a paths block from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param start_offset: Offset where the paths block start
        :return: (List of paths dictionaries, number of bytes read)
        """
        offset = start_offset

        # Read block header
        record_num = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="little", signed=False
        )
        offset += 2
        compressed_len_cigar = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        uncompressed_len_cigar = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        compressed_len_name = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        uncompressed_len_name = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        compression_path_names = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="little", signed=False
        )
        offset += 2
        compression_paths = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="little", signed=False
        )
        offset += 2
        compression_cigars = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2

        # Skip the payload for now
        total_payload_len = compressed_len_name + compressed_len_cigar
        offset += total_payload_len

        # Return empty list for paths
        paths = []
        return paths, offset - start_offset


class BGFAWriter:
    def __init__(
        self, gfa_graph: GFA, block_size: int = 1024, compression_options: dict = None
    ):
        self._gfa = gfa_graph
        self._compression_options = compression_options
        self._block_size = block_size

    def to_bgfa(
        self,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
    ) -> bytes:
        block_size = self._block_size
        # Create a BytesIO buffer
        buffer = io.BytesIO()

        # Configure logging
        import logging
        import tempfile

        # Determine log level based on verbosity
        if debug:
            log_level = logging.DEBUG
        elif verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARNING

        # Only create log file if we're actually logging something
        if log_level <= logging.INFO:
            if logfile is None:
                # Create a temporary log file
                temp_log = tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".log"
                )
                logfile = temp_log.name
                temp_log.close()
                print(f"Logging to temporary file: {logfile}")
        else:
            # If we're not logging, use a dummy logfile
            import os
            if os.name == 'nt':  # Windows
                logfile = "NUL"
            else:  # Unix-like
                logfile = "/dev/null"

        # Clear any existing handlers
        logging.getLogger().handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        handlers = []

        # Only add file handler if we're actually logging to a file
        import os
        if logfile != "/dev/null" and logfile != "NUL":
            file_handler = logging.FileHandler(logfile)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

        # Always add stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

        # Configure root logger
        logging.basicConfig(level=log_level, handlers=handlers)

        # Get logger for this module
        logger = logging.getLogger(__name__)

        logger.info(f"Starting BGFA conversion with block_size={block_size}")
        if debug:
            logger.debug(f"Debug mode enabled, logfile: {logfile}")
            logger.debug(f"Compression options: {self._compression_options}")

        # Compute counts
        s_len = len(self._gfa.nodes())
        l_len = len(self._gfa.edges())
        p_len = len(self._gfa.paths())
        w_len = len(self._gfa.walks())

        # Write the header
        logger.info(
            f"Writing header: S_len={s_len}, L_len={l_len}, P_len={p_len}, W_len={w_len}"
        )
        self._write_header(
            buffer,
            s_len,
            l_len,
            p_len,
            w_len,
            self._block_size,
        )

        # Get segment names sorted by segment ID
        segment_names = list(self._gfa.nodes())
        segment_map = {name: idx for idx, name in enumerate(segment_names)}

        # Write segment names in blocks
        offset = 0
        total_names = len(segment_names)
        logger.info(
            f"Writing {total_names} segment names in blocks of size {block_size}"
        )
        logger.debug(
            f"Segment names: {segment_names[:5] if len(segment_names) > 5 else segment_names}"
        )
        while offset < total_names:
            chunk = segment_names[offset : min(offset + block_size, total_names)]
            block_num = offset // block_size + 1
            logger.info(f"Writing segment names block {block_num}: {len(chunk)} names")
            logger.debug(
                f"Block {block_num} contains: {chunk[:3] if len(chunk) > 3 else chunk}"
            )
            self._write_segment_names_block(buffer, chunk)
            offset += len(chunk)

        # Write segments blocks
        logger.debug(f"Writing segment blocks")
        offset = 0
        # Get all nodes in order of segment_names
        segment_map = getattr(self._gfa, "_segment_map", {})
        # Ensure segment_names are in order of segment_id
        sorted_items = sorted(segment_map.items(), key=lambda x: x[1])
        total_segments = len(sorted_items)
        logger.info(f"Writing {total_segments} segments in blocks of size {block_size}")
        while offset < total_segments:
            chunk = sorted_items[offset : min(offset + block_size, total_segments)]
            block_num = offset // block_size + 1
            logger.info(f"Writing segments block {block_num}: {len(chunk)} segments")
            if len(chunk) > 0:
                name, seg_id = chunk[0]
                logger.debug(
                    f"First segment in block {block_num}: name={name}, id={seg_id}"
                )
            self._write_segments_block(buffer, chunk)
            offset += len(chunk)

        # Write links blocks
        edges = list(self._gfa.edges(data=True, keys=True))
        offset = 0
        total_links = len(edges)
        logger.info(f"Writing {total_links} links in blocks of size {block_size}")
        while offset < total_links:
            chunk = edges[offset : offset + block_size]
            block_num = offset // block_size + 1
            logger.info(f"Writing links block {block_num}: {len(chunk)} links")
            if len(chunk) > 0:
                # chunk[0] is (u, v, key, data)
                u, v, key, data = chunk[0]
                from_node = data.get("from_node", u)
                to_node = data.get("to_node", v)
                logger.debug(
                    f"First link in block {block_num}: from={from_node}, to={to_node}"
                )
            self._write_links_block(buffer, chunk)
            offset += block_size

        # Write paths blocks
        paths = list(self._gfa.paths_iter(data=True))
        offset = 0
        total_paths = len(paths)
        logger.info(f"Writing {total_paths} paths in blocks of size {block_size}")
        while offset < total_paths:
            chunk = paths[offset : offset + block_size]
            block_num = offset // block_size + 1
            logger.info(f"Writing paths block {block_num}: {len(chunk)} paths")
            self._write_paths_block(buffer, chunk)
            offset += block_size

        # Write walks blocks
        walks = list(self._gfa.walks_iter(data=True))
        offset = 0
        total_walks = len(walks)
        logger.info(f"Writing {total_walks} walks in blocks of size {block_size}")
        while offset < total_walks:
            chunk = walks[offset : offset + block_size]
            block_num = offset // block_size + 1
            logger.info(f"Writing walks block {block_num}: {len(chunk)} walks")
            self._write_walks_block(buffer, chunk)
            offset += block_size

        # Get the entire buffer as bytes
        result = buffer.getvalue()
        logger.info(f"BGFA conversion complete. Total size: {len(result)} bytes")
        logger.debug(
            f"Result breakdown: header={self._compute_header_size()}, "
            f"segments={self._compute_segments_size()}, links={self._compute_links_size()}"
        )
        return result

    def _compute_header_size(self):
        """Estimate header size."""
        # Version (2) + block_size (2) + counts (4*8) + header text (variable)
        return 2 + 2 + 32  # Base size, actual text will add more

    def _compute_segments_size(self):
        """Estimate segments data size."""
        total = 0
        for node_id in self._gfa.nodes():
            node_data = dict(self._gfa.nodes(data=True))[node_id]
            sequence = node_data.get("sequence", "*")
            total += 8 + 8 + len(sequence) + 1  # segment_id + seq_len + sequence + null
        return total

    def _compute_links_size(self):
        """Estimate links data size."""
        total = 0
        for u, v, key, data in self._gfa.edges(data=True, keys=True):
            if data.get("is_dovetail", False):
                alignment = data.get("alignment", "*")
                total += 8 + 8 + len(alignment) + 1  # from_id + to_id + cigar + null
        return total

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
        buffer.write(struct.pack("<H", 1))
        # Write block_size (uint16)
        buffer.write(struct.pack("<H", block_size))
        # Write counts (uint64)
        buffer.write(struct.pack("<Q", s_len))
        buffer.write(struct.pack("<Q", l_len))
        buffer.write(struct.pack("<Q", p_len))
        buffer.write(struct.pack("<Q", w_len))

        # Write header text (C string)
        header_text = "H\tVN:Z:1.0"
        buffer.write(header_text.encode("ascii"))
        buffer.write(b"\x00")  # null terminator

    def header(self, block_size: int = 1024) -> bytes:
        """Create placeholder header with zeros."""
        buffer = io.BytesIO()
        self._write_header(buffer, 0, 0, 0, 0, block_size)
        return buffer.getvalue()

    def _write_segment_names_block(self, buffer, to_write) -> int:
        """Write a segment names block to the buffer.

        :param buffer: BytesIO buffer to write to
        :param to_write: List of segment names to write
        :return: Number of bytes written
        """
        # Get compression method for segment names from options
        segment_names_header = self._compression_options.get("segment_names_header", "")
        segment_names_payload_lengths = self._compression_options.get(
            "segment_names_payload_lengths", ""
        )
        segment_names_payload_names = self._compression_options.get(
            "segment_names_payload_names", ""
        )

        payload = b"".join([name.encode("ascii") + b"\x00" for name in to_write])
        record_num = len(to_write)
        compressed_len = len(payload)
        uncompressed_len = compressed_len  # identity compression
        # TODO: Actually implement compression based on the options
        compression_names = 0x0000  # identity for both lengths and strings

        # Write block header according to spec: uint16, uint16, uint64, uint64
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_names))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(payload)

        return 2 + 2 + 8 + 8 + len(payload)

    def _write_segments_block(self, buffer, chunk) -> None:
        """Write a segments block to buffer."""
        record_num = len(chunk)

        # Prepare payload
        payload_parts = []
        for name, seg_id in chunk:
            node_data = dict(self._gfa.nodes(data=True))[name]
            sequence = node_data.get("sequence", "*")
            seq_len = len(sequence) if sequence != "*" else 0

            # Write segment_id (uint64), sequence_length (uint64), sequence (null-terminated)
            payload_parts.append(struct.pack("<Q", seg_id))
            payload_parts.append(struct.pack("<Q", seq_len))
            payload_parts.append(sequence.encode("ascii") + b"\x00")

        payload = b"".join(payload_parts)
        compressed_len = len(payload)
        uncompressed_len = compressed_len
        compression_str = 0x0000  # identity

        # Write header
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_str))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(payload)

    def _write_links_block(self, buffer, chunk) -> None:
        record_num = len(chunk)

        payload_parts = []
        for u, v, key, data in chunk:
            # Get from and to IDs from segment_names
            from_name = data.get("from_node", u)
            to_name = data.get("to_node", v)
            alignment = data.get("alignment", "*")

            # Find segment IDs (assume they exist in segment_map)
            segment_map = getattr(self._gfa, "_segment_map", {})
            from_id = segment_map.get(from_name, 0)
            to_id = segment_map.get(to_name, 0)

            # Write from_id, to_id, cigar
            payload_parts.append(struct.pack("<Q", from_id))
            payload_parts.append(struct.pack("<Q", to_id))
            payload_parts.append(alignment.encode("ascii") + b"\x00")

        payload = b"".join(payload_parts)
        compressed_len = len(payload)
        uncompressed_len = compressed_len
        compression_fromto = 0x0000
        compression_cigars = 0x0000

        # Write header
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_fromto))
        buffer.write(struct.pack("<H", compression_cigars))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(payload)

    def _write_paths_block(self, buffer, chunk) -> None:
        """Write a paths block to buffer."""
        # For now, write empty blocks
        pass

    def _write_walks_block(self, buffer, chunk) -> None:
        """Write a walks block to buffer."""
        # For now, write empty blocks
        pass

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
                seg_id.to_bytes(8, byteorder="little", signed=False)
                + seq_len.to_bytes(8, byteorder="little", signed=False)
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

            # Write block header according to spec: uint16, uint16, uint64, uint64
            header = (
                record_num.to_bytes(2, byteorder="little", signed=False)
                + compression_str.to_bytes(2, byteorder="little", signed=False)
                + compressed_len.to_bytes(8, byteorder="little", signed=False)
                + uncompressed_len.to_bytes(8, byteorder="little", signed=False)
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
    gfa_graph: "GFA",
    file=None,
    block_size: int = 1024,
    segment_names_header_compression_strategy=None,
    segment_names_payload_lengths_compression_strategy=None,
    segment_names_payload_names_compression_strategy=None,
    segments_header_compression_strategy=None,
    segments_payload_lengths_compression_strategy=None,
    segments_payload_strings_compression_strategy=None,
    links_header_compression_strategy=None,
    links_payload_from_compression_strategy=None,
    links_payload_to_compression_strategy=None,
    links_payload_cigar_lengths_compression_strategy=None,
    links_payload_cigar_compression_strategy=None,
    paths_header_compression_strategy=None,
    paths_payload_names_compression_strategy=None,
    paths_payload_segment_lengths_compression_strategy=None,
    paths_payload_path_ids_compression_strategy=None,
    paths_payload_cigar_lengths_compression_strategy=None,
    paths_payload_cigar_compression_strategy=None,
    walks_header_compression_strategy=None,
    walks_payload_sample_ids_compression_strategy=None,
    walks_payload_hep_indices_compression_strategy=None,
    walks_payload_sequence_ids_compression_strategy=None,
    walks_payload_start_compression_strategy=None,
    walks_payload_end_compression_strategy=None,
    walks_payload_walks_compression_strategy=None,
    verbose: bool = False,
    debug: bool = False,
    logfile: str = None,
) -> bytes:
    """Computes a BGFA representing the GFA graph. If a file is given, then write the BGFA to the file.

    :param gfa_graph: The GFA graph to convert to BGFA format
    :param file: Optional file path to write the BGFA data to
    :param block_size: Block size for BGFA format (default: 1024)
    :param segment_names_header_compression_strategy: Compression strategy for segment names block header
    :param segment_names_payload_lengths_compression_strategy: Compression strategy for segment names payload lengths
    :param segment_names_payload_names_compression_strategy: Compression strategy for segment names payload names
    :param segments_header_compression_strategy: Compression strategy for segments block header
    :param segments_payload_lengths_compression_strategy: Compression strategy for segments payload lengths
    :param segments_payload_strings_compression_strategy: Compression strategy for segments payload strings
    :param links_header_compression_strategy: Compression strategy for links block header
    :param links_payload_from_compression_strategy: Compression strategy for links payload 'from' field
    :param links_payload_to_compression_strategy: Compression strategy for links payload 'to' field
    :param links_payload_cigar_lengths_compression_strategy: Compression strategy for links payload cigar lengths
    :param links_payload_cigar_compression_strategy: Compression strategy for links payload cigar strings
    :param paths_header_compression_strategy: Compression strategy for paths block header
    :param paths_payload_names_compression_strategy: Compression strategy for paths payload names
    :param paths_payload_segment_lengths_compression_strategy: Compression strategy for paths payload segment lengths
    :param paths_payload_path_ids_compression_strategy: Compression strategy for paths payload path IDs
    :param paths_payload_cigar_lengths_compression_strategy: Compression strategy for paths payload cigar lengths
    :param paths_payload_cigar_compression_strategy: Compression strategy for paths payload cigar strings
    :param walks_header_compression_strategy: Compression strategy for walks block header
    :param walks_payload_sample_ids_compression_strategy: Compression strategy for walks payload sample IDs
    :param walks_payload_hep_indices_compression_strategy: Compression strategy for walks payload haplotype indices
    :param walks_payload_sequence_ids_compression_strategy: Compression strategy for walks payload sequence IDs
    :param walks_payload_start_compression_strategy: Compression strategy for walks payload start positions
    :param walks_payload_end_compression_strategy: Compression strategy for walks payload end positions
    :param walks_payload_walks_compression_strategy: Compression strategy for walks payload walks
    :param verbose: If True, log detailed information
    :param debug: If True, log debug information
    :param logfile: Path to log file (if None and verbose=True, uses a temporary file)

    :return: The BGFA representation of the input GFA graph as bytes, or empty bytes if file is provided
    """
    compression_options = {
        "segment_names_header_compression_strategy": segment_names_header_compression_strategy,
        "segment_names_payload_lengths_compression_strategy": segment_names_payload_lengths_compression_strategy,
        "segment_names_payload_names_compression_strategy": segment_names_payload_names_compression_strategy,
        "segments_header_compression_strategy": segments_header_compression_strategy,
        "segments_payload_lengths_compression_strategy": segments_payload_lengths_compression_strategy,
        "segments_payload_strings_compression_strategy": segments_payload_strings_compression_strategy,
        "links_header_compression_strategy": links_header_compression_strategy,
        "links_payload_from_compression_strategy": links_payload_from_compression_strategy,
        "links_payload_to_compression_strategy": links_payload_to_compression_strategy,
        "links_payload_cigar_lengths_compression_strategy": links_payload_cigar_lengths_compression_strategy,
        "links_payload_cigar_compression_strategy": links_payload_cigar_compression_strategy,
        "paths_header_compression_strategy": paths_header_compression_strategy,
        "paths_payload_names_compression_strategy": paths_payload_names_compression_strategy,
        "paths_payload_segment_lengths_compression_strategy": paths_payload_segment_lengths_compression_strategy,
        "paths_payload_path_ids_compression_strategy": paths_payload_path_ids_compression_strategy,
        "paths_payload_cigar_lengths_compression_strategy": paths_payload_cigar_lengths_compression_strategy,
        "paths_payload_cigar_compression_strategy": paths_payload_cigar_compression_strategy,
        "walks_header_compression_strategy": walks_header_compression_strategy,
        "walks_payload_sample_ids_compression_strategy": walks_payload_sample_ids_compression_strategy,
        "walks_payload_hep_indices_compression_strategy": walks_payload_hep_indices_compression_strategy,
        "walks_payload_sequence_ids_compression_strategy": walks_payload_sequence_ids_compression_strategy,
        "walks_payload_start_compression_strategy": walks_payload_start_compression_strategy,
        "walks_payload_end_compression_strategy": walks_payload_end_compression_strategy,
        "walks_payload_walks_compression_strategy": walks_payload_walks_compression_strategy,
    }
    bgfa = BGFAWriter(gfa_graph, block_size, compression_options)
    # If file is given, write the BGFA to the file
    if file != None:
        with open(file, "wb") as f:
            f.write(bgfa.to_bgfa(verbose=verbose, debug=debug, logfile=logfile))
    return bgfa.to_bgfa(verbose=verbose, debug=debug, logfile=logfile)


def read_bgfa(
    file_path: str, verbose: bool = False, debug: bool = False, logfile: str = None
) -> "GFA":
    """Read a BGFA file and create the corresponding GFA graph.

    :param file_path: Path to the BGFA file
    :param verbose: If True, log detailed information
    :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
    :return: GFA graph object
    """
    reader = ReaderBGFA()
    return reader.read_bgfa(file_path, verbose=verbose, debug=debug, logfile=logfile)
