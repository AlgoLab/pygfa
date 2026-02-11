"""Dictionary training API for zstd compression.

This module provides Python API for training zstd dictionaries.
Note: This is a Python API only, not exposed via CLI.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import zstandard as zstd

from pygfa.exceptions import DictionaryTrainingError

logger = logging.getLogger(__name__)


def train_dictionary(samples: list[bytes], dict_size: int = 112640, **kwargs) -> bytes:
    """Train a zstd dictionary from sample data.

    Dictionary training allows zstd to achieve better compression ratios
    on small data by learning patterns from representative samples.

    Args:
        samples: List of sample byte strings to train on.
                Should be representative of the data to be compressed.
        dict_size: Dictionary size in bytes (default: 112640 ~ 110KB).
                  Larger dictionaries can achieve better compression but
                  use more memory. Typical sizes: 10KB-500KB.
        **kwargs: Additional arguments passed to zstd.train_dictionary()

    Returns:
        Trained dictionary as bytes

    Raises:
        DictionaryTrainingError: If training fails
        ValueError: If samples list is empty

    Example:
        >>> samples = [b"ACGTACGT", b"TGCATGCA", b"AAAATTTT"]
        >>> dict_bytes = train_dictionary(samples, dict_size=10240)
        >>> len(dict_bytes)
        10240
    """
    if not samples:
        raise ValueError(" samples list cannot be empty")

    if len(samples) < 10:
        logger.warning("Dictionary training works best with many samples (got %d, recommend 100+)", len(samples))

    try:
        logger.info("Training zstd dictionary with %d samples, size=%d bytes", len(samples), dict_size)

        dict_data = zstd.train_dictionary(dict_size, samples, **kwargs)

        logger.info("Dictionary training complete: %d bytes", len(dict_data))

        return dict_data

    except Exception as e:
        raise DictionaryTrainingError(f"Dictionary training failed: {e}") from e


def save_dictionary(dictionary: Union[bytes, zstd.ZstdCompressionDict], path: Union[str, Path]) -> None:
    """Save trained dictionary to file.

    Args:
        dictionary: Trained dictionary (bytes or ZstdCompressionDict)
        path: Output file path

    Raises:
        IOError: If file cannot be written

    Example:
        >>> dict_bytes = train_dictionary(samples)
        >>> save_dictionary(dict_bytes, "my_dict.zdict")
    """
    path = Path(path)
    if isinstance(dictionary, zstd.ZstdCompressionDict):
        dict_bytes = dictionary.as_bytes()
    else:
        dict_bytes = dictionary
    path.write_bytes(dict_bytes)
    logger.info("Saved dictionary to %s (%d bytes)", path, len(dict_bytes))


def load_dictionary(path: Union[str, Path]) -> bytes:
    """Load trained dictionary from file.

    Args:
        path: Path to dictionary file

    Returns:
        Dictionary bytes

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read

    Example:
        >>> dict_bytes = load_dictionary("my_dict.zdict")
        >>> compressed = compress_with_dict(data, dict_bytes)
    """
    path = Path(path)
    dict_bytes = path.read_bytes()
    logger.debug("Loaded dictionary from %s (%d bytes)", path, len(dict_bytes))
    return dict_bytes


def compress_with_dict(data: bytes, dictionary: Union[bytes, zstd.ZstdCompressionDict], level: int = 3) -> bytes:
    """Compress data using a trained dictionary.

    Args:
        data: Data to compress
        dictionary: Trained dictionary bytes or ZstdCompressionDict object
        level: Compression level (1-22, default: 3)

    Returns:
        Compressed data

    Example:
        >>> dict_bytes = train_dictionary(samples)
        >>> compressed = compress_with_dict(b"ACGT", dict_bytes)
    """
    if isinstance(dictionary, bytes):
        dictionary = zstd.ZstdCompressionDict(dictionary)
    compressor = zstd.ZstdCompressor(dict_data=dictionary, level=level)
    return compressor.compress(data)


def decompress_with_dict(data: bytes, dictionary: Union[bytes, zstd.ZstdCompressionDict]) -> bytes:
    """Decompress data that was compressed with a dictionary.

    Args:
        data: Compressed data
        dictionary: Dictionary used for compression (bytes or ZstdCompressionDict)

    Returns:
        Decompressed data
    """
    if isinstance(dictionary, bytes):
        dictionary = zstd.ZstdCompressionDict(dictionary)
    decompressor = zstd.ZstdDecompressor(dict_data=dictionary)
    return decompressor.decompress(data)


__all__ = [
    "train_dictionary",
    "save_dictionary",
    "load_dictionary",
    "compress_with_dict",
    "decompress_with_dict",
]
