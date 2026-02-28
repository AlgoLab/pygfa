"""Heuristic encoding selector.

Automatically selects the best encoding based on data characteristics.
"""

from __future__ import annotations

import logging
from typing import List

from pygfa.encoding.enums import IntegerEncoding, StringEncoding

logger = logging.getLogger(__name__)

# Configuration constants
HEURISTIC_SAMPLE_SIZE = 1000  # Number of records to sample for analysis
HEURISTIC_FALLBACK_INT = IntegerEncoding.NONE  # Default fallback for integers
HEURISTIC_FALLBACK_STR = StringEncoding.NONE  # Default fallback for strings


def is_sequential(data: List[int]) -> bool:
    """Check if data is sequential (sorted with small gaps)."""
    if len(data) < 2:
        return True
    sorted_data = sorted(data)
    gaps = [sorted_data[i + 1] - sorted_data[i] for i in range(len(sorted_data) - 1)]
    return max(gaps) <= len(data) * 2


def has_outliers(data: List[int], threshold: float = 10.0) -> bool:
    """Check if data has significant outliers."""
    if len(data) < 10:
        return False
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    std_dev = variance**0.5
    if std_dev == 0:
        return False
    # Check for values far from mean
    for x in data:
        if abs(x - mean) > threshold * std_dev:
            return True
    return False


def all_small_values(data: List[int], max_bits: int = 16) -> bool:
    """Check if all values fit in specified bits."""
    max_val = max(data) if data else 0
    return max_val < (1 << max_bits)


def is_dna_sequence(data: bytes) -> bool:
    """Check if data looks like DNA sequence."""
    if not data:
        return False
    # Check if mostly ACGTN
    dna_chars = set(b"ACGTNacgtn")
    dna_count = sum(1 for c in data if c in dna_chars)
    return dna_count / len(data) > 0.9


def has_repetition(data: bytes, sample_size: int = 1024) -> bool:
    """Check if data has repetitive patterns."""
    sample = data[:sample_size]
    if len(sample) < 10:
        return False
    # Check for repeated substrings
    for size in [2, 3, 4]:
        substrings = {}
        for i in range(len(sample) - size + 1):
            substr = sample[i : i + size]
            substrings[substr] = substrings.get(substr, 0) + 1
        if substrings:
            max_repeats = max(substrings.values())
            if max_repeats > len(sample) / (size * 4):
                return True
    return False


def is_small_data(data: bytes, threshold: int = 1024) -> bool:
    """Check if data is small enough for dictionary compression."""
    return len(data) < threshold


def select_integer_encoding(sample: List[int]) -> IntegerEncoding:
    """Select best integer encoding based on sample.

    Args:
        sample: List of integers to analyze

    Returns:
        Selected integer encoding
    """
    if not sample:
        return HEURISTIC_FALLBACK_INT

    try:
        # Check for sequential data (good for delta)
        if is_sequential(sample):
            logger.debug("Selected DELTA encoding for sequential data")
            return IntegerEncoding.DELTA

        # Check for outliers (use PFOR-DELTA)
        if has_outliers(sample):
            logger.debug("Selected PFOR_DELTA encoding for data with outliers")
            return IntegerEncoding.PFOR_DELTA

        # Check for small values (use bit packing)
        if all_small_values(sample, max_bits=16):
            logger.debug("Selected BIT_PACKING encoding for small values")
            return IntegerEncoding.BIT_PACKING

        # Default to varint for general data
        logger.debug("Selected VARINT encoding for general integer data")
        return IntegerEncoding.VARINT

    except Exception as e:
        logger.warning(f"Heuristic selection failed: {e}, using fallback")
        return HEURISTIC_FALLBACK_INT


def select_string_encoding(sample: bytes) -> StringEncoding:
    """Select best string encoding based on sample.

    Args:
        sample: Bytes to analyze

    Returns:
        Selected string encoding
    """
    if not sample:
        return HEURISTIC_FALLBACK_STR

    try:
        # Check for DNA sequences
        if is_dna_sequence(sample):
            logger.debug("Selected TWO_BIT_DNA encoding for DNA data")
            return StringEncoding.TWO_BIT_DNA

        # Check for repetitive patterns (good for BWT+Huffman)
        if has_repetition(sample):
            logger.debug("Selected BWT_HUFFMAN encoding for repetitive data")
            return StringEncoding.BWT_HUFFMAN

        # Check for small data (use dictionary)
        if is_small_data(sample):
            logger.debug("Selected ZSTD_DICT encoding for small data")
            return StringEncoding.ZSTD_DICT

        # Default to zstd for general data
        logger.debug("Selected ZSTD encoding for general string data")
        return StringEncoding.ZSTD

    except Exception as e:
        logger.warning(f"Heuristic selection failed: {e}, using fallback")
        return HEURISTIC_FALLBACK_STR


def select_encoding(sample_data: bytes, data_type: str) -> tuple[IntegerEncoding, StringEncoding]:
    """Select best encoding based on sample analysis.

    Args:
        sample_data: Sample bytes to analyze
        data_type: Type of data ("integers" or "strings")

    Returns:
        Tuple of (integer_encoding, string_encoding)
    """
    if data_type == "integers":
        # Parse bytes as integers (assume 32-bit little-endian)
        int_count = len(sample_data) // 4
        int_sample = []
        import struct

        for i in range(min(int_count, HEURISTIC_SAMPLE_SIZE)):
            val = struct.unpack_from("<I", sample_data, i * 4)[0]
            int_sample.append(val)

        int_enc = select_integer_encoding(int_sample)
        return int_enc, StringEncoding.NONE

    elif data_type == "strings":
        str_enc = select_string_encoding(sample_data[: HEURISTIC_SAMPLE_SIZE * 100])
        return IntegerEncoding.NONE, str_enc

    else:
        logger.warning(f"Unknown data type: {data_type}, using fallback")
        return HEURISTIC_FALLBACK_INT, HEURISTIC_FALLBACK_STR


__all__ = [
    "HEURISTIC_SAMPLE_SIZE",
    "HEURISTIC_FALLBACK_INT",
    "HEURISTIC_FALLBACK_STR",
    "select_integer_encoding",
    "select_string_encoding",
    "select_encoding",
    "is_sequential",
    "has_outliers",
    "all_small_values",
    "is_dna_sequence",
    "has_repetition",
    "is_small_data",
]
