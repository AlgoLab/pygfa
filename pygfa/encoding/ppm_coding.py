"""PPM (Prediction by Partial Matching) string compression.

PPM is a statistical compression method that builds a context model from the
input data and uses arithmetic coding to encode symbols based on their
predicted probabilities. Higher order models provide better compression for
repetitive data.
"""

from __future__ import annotations

import struct
from collections import defaultdict
from typing import Dict, List, Tuple


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


def compress_string_ppm(string: str, order: int = 3) -> bytes:
    """Compress a string using PPM (Prediction by Partial Matching).

    Format:
    - uint32: original data length
    - uint8: PPM order
    - arithmetic-coded data

    Args:
        string: String to compress
        order: PPM model order (higher = more context, default 3)

    Returns:
        Compressed bytes
    """
    data = string.encode("utf-8")

    if not data:
        return struct.pack("<I", 0) + bytes([order])

    # Build PPM model
    model = PPMModel(order=order)
    model.learn(data)

    # Encode using arithmetic coding
    coder = SimpleArithmeticCoder()
    encoded = coder.encode(data, model)

    # Pack result
    result = bytearray()
    result.extend(struct.pack("<I", len(data)))
    result.append(order)
    result.extend(encoded)

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


__all__ = [
    "compress_string_ppm",
    "compress_string_list_ppm",
    "PPMModel",
    "SimpleArithmeticCoder",
]
