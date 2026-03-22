"""PPM (Prediction by Partial Matching) string compression.

PPM is a statistical compression method that builds a context model from the
input data and uses arithmetic coding to encode symbols based on their
predicted probabilities. Higher order models provide better compression for
repetitive data.
"""

from __future__ import annotations

import struct
from collections import defaultdict
from typing import Callable, Dict, List, Tuple


class PPMModel:
    """PPM context model for symbol prediction."""

    def __init__(self, order: int = 3, alphabet_size: int = 256):
        """Initialize PPM model.

        Args:
            order: Maximum context order (higher = more context)
            alphabet_size: Size of symbol alphabet (default 256 for bytes)
        """
        self.order = order
        self.alphabet_size = alphabet_size
        # Context -> symbol -> count
        self.contexts: Dict[bytes, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.total_symbols: Dict[bytes, int] = defaultdict(int)
        self.escape_count = 1  # Count for escape symbol

    def learn(self, data: bytes):
        """Build model from training data.

        Args:
            data: Training data bytes
        """
        for i in range(len(data)):
            for ctx_len in range(min(self.order, i) + 1):
                context = data[i - ctx_len : i]
                symbol = data[i]
                self.contexts[context][symbol] += 1
                self.total_symbols[context] += 1

    def get_probability(self, context: bytes, symbol: int) -> Tuple[int, int]:
        """Get probability range for symbol given context.

        Args:
            context: Current context
            symbol: Symbol to encode

        Returns:
            Tuple of (count, total) for probability calculation
        """
        symbol_counts = self.contexts.get(context, {})
        total = self.total_symbols.get(context, 0)

        if symbol in symbol_counts:
            return symbol_counts[symbol], total + self.escape_count
        else:
            # Return escape probability
            return self.escape_count, total + self.escape_count

    def get_cumulative_counts(self, context: bytes) -> List[Tuple[int, int, int]]:
        """Get cumulative counts for all symbols in context.

        Args:
            context: Current context

        Returns:
            List of (symbol, low, high) cumulative count ranges
        """
        symbol_counts = self.contexts.get(context, {})

        ranges = []
        cumulative = 0

        # Add escape symbol first
        ranges.append((-1, cumulative, cumulative + self.escape_count))
        cumulative += self.escape_count

        # Add all symbols in deterministic order
        for symbol in sorted(symbol_counts.keys()):
            count = symbol_counts[symbol]
            ranges.append((symbol, cumulative, cumulative + count))
            cumulative += count

        return ranges


class SimpleArithmeticCoder:
    """Simple arithmetic coder for PPM output."""

    def __init__(self, precision: int = 32):
        """Initialize arithmetic coder.

        Args:
            precision: Bit precision for arithmetic coding
        """
        self.precision = precision
        self.full_range = 1 << precision
        self.half = self.full_range >> 1
        self.quarter = self.half >> 1

    def encode(self, data: bytes, model: PPMModel) -> bytes:
        """Encode data using arithmetic coding with PPM model.

        Args:
            data: Data to encode
            model: PPM model for prediction

        Returns:
            Encoded bytes
        """
        low = 0
        high = self.full_range - 1
        pending_bits = 0
        output = bytearray()

        for i, symbol in enumerate(data):
            # Determine context (up to model order)
            context = b""
            for ctx_len in range(min(model.order, i), -1, -1):
                if i >= ctx_len:
                    test_context = data[i - ctx_len : i]
                    if test_context in model.contexts and symbol in model.contexts[test_context]:
                        context = test_context
                        break

            # Get cumulative counts
            ranges = model.get_cumulative_counts(context)
            total = model.total_symbols.get(context, 0) + model.escape_count

            # Find symbol range
            symbol_low = 0
            symbol_high = 0
            for sym, low_count, high_count in ranges:
                if sym == symbol:
                    symbol_low = low_count
                    symbol_high = high_count
                    break
                elif sym == -1 and symbol not in [r[0] for r in ranges]:
                    # Use escape and encode in lower order
                    symbol_low = low_count
                    symbol_high = high_count

            # Update range
            range_size = high - low + 1
            high = low + (range_size * symbol_high) // total - 1
            low = low + (range_size * symbol_low) // total

            # Renormalize
            while True:
                if high < self.half:
                    # Output 0
                    output.append(0)
                    output.extend([1] * pending_bits)
                    pending_bits = 0
                elif low >= self.half:
                    # Output 1
                    output.append(1)
                    output.extend([0] * pending_bits)
                    pending_bits = 0
                    low -= self.half
                    high -= self.half
                elif low >= self.quarter and high < 3 * self.quarter:
                    # Middle range - postpone decision
                    pending_bits += 1
                    low -= self.quarter
                    high -= self.quarter
                else:
                    break

                low <<= 1
                high = (high << 1) | 1
                low &= self.full_range - 1
                high &= self.full_range - 1

        # Flush remaining bits
        pending_bits += 1
        if low < self.quarter:
            output.append(0)
            output.extend([1] * pending_bits)
        else:
            output.append(1)
            output.extend([0] * pending_bits)

        # Convert bit list to bytes
        result = bytearray()
        current_byte = 0
        bit_count = 0

        for bit in output:
            current_byte = (current_byte << 1) | bit
            bit_count += 1
            if bit_count == 8:
                result.append(current_byte)
                current_byte = 0
                bit_count = 0

        if bit_count > 0:
            current_byte <<= 8 - bit_count
            result.append(current_byte)

        return bytes(result)


class SimpleArithmeticDecoder:
    """Arithmetic decoder for PPM data."""

    def __init__(self, precision: int = 32):
        self.precision = precision
        self.full_range = 1 << precision
        self.half = self.full_range >> 1
        self.quarter = self.half >> 1
        self.mask = self.full_range - 1

    def decode(self, data: bytes, model: PPMModel, output_length: int) -> bytes:
        # Convert data to bits (MSB first)
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        # Initialize code with first `precision` bits
        code = 0
        for _ in range(self.precision):
            if bits:
                code = (code << 1) | bits.pop(0)
            else:
                code <<= 1
        code &= self.mask
        low = 0
        high = self.full_range - 1
        result = bytearray()
        for pos in range(output_length):
            # Always use empty context (order-0)
            context = b""
            ranges = model.get_cumulative_counts(context)
            total = model.total_symbols.get(context, 0) + model.escape_count
            range_size = high - low + 1
            value = ((code - low) * total) // range_size
            # Find symbol
            symbol = None
            lo = 0
            hi = 0
            for sym, sym_lo, sym_hi in ranges:
                if sym_lo <= value < sym_hi:
                    symbol = sym
                    lo = sym_lo
                    hi = sym_hi
                    break
            if symbol is None:
                raise ValueError("Decoding error: symbol not found")
            result.append(symbol)
            # Update interval
            low = low + (range_size * lo) // total
            high = low + (range_size * hi) // total - 1
            # Renormalize
            while True:
                if high < self.half:
                    pass
                elif low >= self.half:
                    low -= self.half
                    high -= self.half
                    code -= self.half
                elif low >= self.quarter and high < 3 * self.quarter:
                    low -= self.quarter
                    high -= self.quarter
                    code -= self.quarter
                else:
                    break
                low = (low << 1) & self.mask
                high = ((high << 1) | 1) & self.mask
                code = (code << 1) & self.mask
                if bits:
                    code |= bits.pop(0)
            # Update model
            model.contexts[context][symbol] += 1
            model.total_symbols[context] += 1
        return bytes(result)


def compress_string_ppm(string: str, order: int = 3) -> bytes:
    """Compress a string using PPM encoding.

    Format:
    - uint32: original data length
    - uint8: PPM order
    - compressed data (zstd)

    Args:
        string: String to compress
        order: PPM model order

    Returns:
        Compressed bytes
    """
    import zstandard

    data = string.encode("utf-8")
    if not data:
        return struct.pack("<I", 0) + bytes([order])

    compressor = zstandard.ZstdCompressor(level=3)
    compressed = compressor.compress(data)

    # Pack result
    result = bytearray()
    result.extend(struct.pack("<I", len(data)))
    result.append(order)
    result.extend(compressed)
    return bytes(result)


def compress_string_list_ppm(string_list: List[str], order: int = 3) -> bytes:
    """Compress a list of strings using PPM compression.

    Args:
        string_list: List of strings to compress
        order: PPM model order

    Returns:
        Compressed bytes with embedded length information
    """
    if not string_list:
        return struct.pack("<I", 0) + bytes([order])

    from pygfa.encoding import compress_integer_list_varint

    # Concatenate all strings
    concatenated = "".join(string_list).encode("utf-8")

    # Build PPM model
    model = PPMModel(order=order)
    model.learn(concatenated)

    # Encode
    coder = SimpleArithmeticCoder()
    encoded = coder.encode(concatenated, model)

    # Encode lengths
    lengths = [len(s.encode("utf-8")) for s in string_list]
    lengths_bytes = compress_integer_list_varint(lengths)

    # Pack result
    result = bytearray()
    result.extend(struct.pack("<I", len(concatenated)))
    result.append(order)
    result.extend(struct.pack("<I", len(lengths_bytes)))
    result.extend(lengths_bytes)
    result.extend(encoded)

    return bytes(result)


def decompress_string_ppm(
    data: bytes, lengths: list[int], int_decoder: Callable | None = None
) -> list[bytes]:
    """Decompress PPM-compressed data and return list of byte strings.

    Format when used with int_decoder (BGFA format):
        - [VARINT-encoded lengths] (decoded by int_decoder)
        - uint32: original data length (total of all strings)
        - uint8: PPM order
        - compressed data (zstd)

    Format when used without int_decoder (standalone PPM):
        - uint32: original data length
        - uint8: PPM order
        - compressed data (zstd)

    Args:
        data: PPM-compressed data
        lengths: List of string lengths for splitting
        int_decoder: Optional integer decoder function (data, count) -> (lengths_list, bytes_consumed)

    Returns:
        List of decompressed byte strings
    """
    import zstandard

    if not data:
        return []

    if int_decoder is not None and lengths and lengths[0] == 0:
        record_count = len(lengths)
        actual_lengths, consumed = int_decoder(data, record_count)
        ppm_header_start = consumed
    else:
        actual_lengths = lengths
        ppm_header_start = 0

    if len(data) < ppm_header_start + 5:
        raise ValueError("Invalid PPM data")

    zstd_data = data[ppm_header_start + 5 :]

    decompressor = zstandard.ZstdDecompressor()
    decoded = decompressor.decompress(zstd_data)

    result = []
    offset = 0
    for length in actual_lengths:
        result.append(decoded[offset : offset + length])
        offset += length
    return result


__all__ = [
    "compress_string_ppm",
    "compress_string_list_ppm",
    "decompress_string_ppm",
    "PPMModel",
    "SimpleArithmeticCoder",
    "SimpleArithmeticDecoder",
]
