"""
Burrows-Wheeler Transform implementation for BGFA compression.

This module provides BWT encoding and decoding functions with configurable
block sizes, designed for use with DNA sequence compression.
"""

from __future__ import annotations

import struct


def burrows_wheeler_transform(data: bytes, block_size: int = 65536) -> bytes:
    """Apply Burrows-Wheeler Transform to data in blocks.

    The output format is:
    - uint32: number of blocks
    - For each block:
      - uint32: primary index (position of original string in sorted rotations)
      - uint32: block data size
      - bytes: BWT transformed data

    :param data: Input data to transform
    :param block_size: Size of each block (default: 65536 bytes)
    :return: BWT transformed data with metadata
    """
    if not data:
        return struct.pack("<I", 0)

    # Split data into blocks
    blocks = []
    for i in range(0, len(data), block_size):
        block = data[i : i + block_size]
        blocks.append(block)

    # Process each block
    result = bytearray()
    result.extend(struct.pack("<I", len(blocks)))

    for block in blocks:
        # Add end-of-string marker (null byte) if not present
        if b"\x00" not in block:
            block_with_marker = block + b"\x00"
        else:
            # If null byte already exists, use a different marker
            block_with_marker = block + b"\x01"

        # Generate all rotations
        n = len(block_with_marker)
        rotations = []
        for j in range(n):
            rotation = block_with_marker[j:] + block_with_marker[:j]
            rotations.append((rotation, j))

        # Sort rotations
        rotations.sort(key=lambda x: x[0])

        # Find primary index (original string position)
        primary_index = None
        for idx, (rot, orig_idx) in enumerate(rotations):
            if orig_idx == 0:
                primary_index = idx
                break

        if primary_index is None:
            raise ValueError("Could not find primary index")

        # Extract last column (BWT)
        bwt_data = bytes([rot[0][-1] for rot in rotations])

        # Store primary index, size, and BWT data
        result.extend(struct.pack("<I", primary_index))
        result.extend(struct.pack("<I", len(bwt_data)))
        result.extend(bwt_data)

    return bytes(result)


def inverse_bwt(data: bytes) -> bytes:
    """Apply inverse Burrows-Wheeler Transform.

    :param data: BWT transformed data with metadata
    :return: Original data
    """
    if not data:
        return b""

    # Read number of blocks
    pos = 0
    if len(data) < 4:
        raise ValueError("Invalid BWT data: too short")

    num_blocks = struct.unpack_from("<I", data, pos)[0]
    pos += 4

    if num_blocks == 0:
        return b""

    result = bytearray()

    for _ in range(num_blocks):
        if pos + 8 > len(data):
            raise ValueError("Invalid BWT data: missing block header")

        # Read primary index
        primary_index = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        # Read block size
        block_size = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        if pos + block_size > len(data):
            raise ValueError("Invalid BWT data: incomplete block data")

        # Extract BWT data
        bwt_data = data[pos : pos + block_size]
        pos += block_size

        # Reconstruct original using LF mapping
        original = _inverse_bwt_single(bwt_data, primary_index)

        # Remove end-of-string marker
        if original.endswith(b"\x00"):
            original = original[:-1]
        elif original.endswith(b"\x01"):
            original = original[:-1]

        result.extend(original)

    return bytes(result)


def _inverse_bwt_single(bwt_data: bytes, primary_index: int) -> bytes:
    """Inverse BWT for a single block using LF mapping.

    :param bwt_data: BWT transformed data
    :param primary_index: Primary index from original transformation
    :return: Original data
    """
    if not bwt_data:
        return b""

    n = len(bwt_data)

    # Count occurrences of each character
    char_counts = {}
    for char in bwt_data:
        char_counts[char] = char_counts.get(char, 0) + 1

    # Create cumulative count table (starting positions)
    sorted_chars = sorted(char_counts.keys())
    start_pos = {}
    total = 0
    for char in sorted_chars:
        start_pos[char] = total
        total += char_counts[char]

    # Build LF mapping: for each position in BWT, where does it map to in first column?
    # LF[i] = start_pos[BWT[i]] + rank(BWT[i], i)
    # where rank(c, i) = number of occurrences of c in BWT[0..i-1]

    # First, count ranks
    rank = [0] * n
    counts = {}
    for i in range(n):
        char = bwt_data[i]
        rank[i] = counts.get(char, 0)
        counts[char] = rank[i] + 1

    # Build LF mapping
    lf = [0] * n
    for i in range(n):
        char = bwt_data[i]
        lf[i] = start_pos[char] + rank[i]

    # Reconstruct original string by following LF mapping from primary_index
    result = bytearray(n)
    idx = primary_index
    for i in range(n - 1, -1, -1):
        result[i] = bwt_data[idx]
        idx = lf[idx]

    return bytes(result)


def move_to_front_encode(data: bytes) -> bytes:
    """Apply Move-to-Front transform.

    :param data: Input data
    :return: MTF transformed data
    """
    # Initialize symbol list (all possible byte values)
    symbol_list = list(range(256))
    result = bytearray()

    for byte in data:
        # Find symbol in list
        idx = symbol_list.index(byte)
        result.append(idx)

        # Move to front
        symbol_list.pop(idx)
        symbol_list.insert(0, byte)

    return bytes(result)


def move_to_front_decode(data: bytes) -> bytes:
    """Apply inverse Move-to-Front transform.

    :param data: MTF transformed data
    :return: Original data
    """
    # Initialize symbol list (all possible byte values)
    symbol_list = list(range(256))
    result = bytearray()

    for idx in data:
        # Get symbol at index
        byte = symbol_list[idx]
        result.append(byte)

        # Move to front
        symbol_list.pop(idx)
        symbol_list.insert(0, byte)

    return bytes(result)
