# Binary GFA format

## Binary GFA file: overall structure

We divide the file into the following parts.
The first part is the file header, which contains some metadata.
All other parts are a list of blocks. There can be several blocks of the same type.

*  File Header
*  List of Blocks (segments, links, paths, walks)

Each block contains a `section_id` field that identifies its type, allowing blocks
to appear in any order in the file. 

### Section IDs Reference

| ID   | Block Type | Description                                          |
|------|------------|------------------------------------------------------|
| 1    | Reserved   | Formerly Segment Names; merged into Segments block   |
| 2    | Segments   | Segment names and sequences                          |
| 3    | Links      | Link connections and CIGAR alignments                |
| 4    | Paths      | Paths with oriented segment IDs and CIGAR strings    |
| 5    | Walks      | Walks with sample/haplotype metadata and orientations|

Each block has a header and a payload.
The payloads begin with all integer metadata required for the strategy, followed by the compressed data blob.

**Block ordering constraints:**

- Blocks of the same type are not required to be contiguous
- Different section types can appear in any order relative to each other.

**Endianness:** All multi-byte integer fields (`uint16`, `uint32`, `uint64`) are encoded in little-endian format.

**Alignment:** All fields begin at the next byte boundary after the previous field. No inter-field padding is applied. Fields are packed contiguously without gaps.

All bytes data and all data that are encoded with a variable number of bits are packed into bytes. Any remaining bits in
the final byte of the bitstream are set to 0 (when writing) and MUST be ignored (when reading).

## Conventions

**C strings:** The reference to C strings (ASCII terminated by `\0`) is for context only. 
Input strings to the `strings` type do NOT include null terminators. Strings are stored as raw ASCII bytes without termination.

**Type definitions:**

- `uints`: A list of unsigned integers encoded according to the specified integer encoding strategy (see "Integer Encoding Algorithms" section, lines 337-428).
- `strings`: A list of strings encoded according to the string encoding strategy (see "Strings Encoding strategies" section, lines 302-353).
- `bits`: A list of bits packed into uint64 words (see "Bits" section, lines 481-510).
- `walks`: A list of walks, where each walk is a sequence of oriented segment IDs (see "Walks Type Format" section, lines 257-290).
- `bytes`: A raw byte sequence.

### Strategy Code Format Summary

The BGFA format uses strategy codes to specify encoding methods. The code size depends on what is being encoded.

**Byte ordering:** All strategy codes are stored as consecutive bytes in file order (not as multi-byte integers). The first byte listed is written first to the file.

| Type         | Code Size | Byte Layout (in file order)      | Example      | Used For           |
|--------------|-----------|----------------------------------|--------------|--------------------|
| Integer-only | 1 byte    | `[method]`                       | `0x01`       | Pure integer lists |
| Strings      | 2 bytes   | `[int_method][str_method]`       | `0x0102`     | String lists       |
| CIGAR        | 4 bytes   | `[decomp][int1][int2][str]`      | `0x01020304` | CIGAR strings only |
| Walks/Paths  | 4 bytes   | `[decomp][reserved][int][str]`   | `0x02010000` | Walks and Paths    |

**Key distinction:**
- **2-byte codes** (0x0000-0x0BFF): Used for simple string/integer lists where the first byte specifies integer encoding and the second byte specifies string encoding
- **4-byte codes** (0x010000-0x02FFFF): Used for structured data requiring decomposition where:
  - Byte 1: Decomposition strategy (how to split the data)
  - Byte 2: Reserved (must be 0x00) or first integer encoding strategy
  - Byte 3: Second integer encoding strategy or string encoding strategy
  - Byte 4: String encoding strategy (when applicable)
  
**Example interpretation:**
- For 2-byte string code `0x0102`:
  - First byte in file: `0x01` (varint encoding for lengths/positions)
  - Second byte in file: `0x02` (fixed16 encoding for the string blob)
  
- For 4-byte walks code `0x02010000`:
  - First byte: `0x02` (orientation + numid decomposition)
  - Second byte: `0x01` (reserved, must be 0x00 for walks/paths)
  - Third byte: `0x00` (varint encoding for segment IDs)
  - Fourth byte: `0x00` (no encoding for string data)

Readers MUST skip unknown section IDs without error.

### Terminology

- **Record:** A single entry within a block (e.g., one segment, one link, one walk).
- **Block:** A contiguous section of the file containing a header and a payload of a single type.
- **Section:** Synonym for block type, identified by `section_id`.
- **Payload:** The encoded data portion of a block, following the header.
- **Metadata:** The integer lists (lengths, positions) prepended to the compressed blob within a payload, used to decode the blob.

**Example interpretation:** For a 2-byte string code `0x0102`:
- First byte in file: `0x01` (varint encoding for lengths/positions)
- Second byte in file: `0x02` (fixed16 encoding for the string blob)

### File Header Section

| Field          | Description                                             | Type                      |
|----------------|---------------------------------------------------------|---------------------------|
| `magic_number` | Magic number for bgfa files = "BGFA" (0x41464742)       | `uint32`                  |
| `version`      | Format version (progressive number, starts at 0)        | `uint16`                  |
| `header_len`   | length of the header string (excluding null terminator) | `uint16`                  |
| `header`       | GFA header text                                         | `bytes` + null terminator |

**Clarification:** The header is stored as `header_len` bytes of ASCII text followed by a single null terminator byte (`\0`). The `header_len` field specifies the length of the text portion only. Total bytes consumed = 8 (`magic` + `version` + `header_len`) + `header_len` + 1 (null terminator).

**Note:** The magic number 0x41464742 corresponds to ASCII "BGFA" when read as little-endian bytes: 0x42='B', 0x47='G', 0x46='F', 0x41='A'.

**Version:** The version field is a progressive integer starting at 0. It has no semantic meaning (no major/minor interpretation).

### Segments Block

Each block consists of a header and a payload.

We associate an internal segment ID to each segment name, where the segment ID is an
incrementing integer starting at 0. Segment IDs are assigned in the order segment names appear in the file.

#### Header

| Field                    | Description                                                 | Type     |
|--------------------------|-------------------------------------------------------------|----------|
| `section_id`             | Section type (2 = segments)                                 | `uint8`  |
| `record_num`             | number of records in the block                              | `uint16` |
| `compression_segment_names`| Encoding strategy for the segment names (2 bytes)           | `uint16` |
| `compressed_segment_names_len`| length of compressed segment names field                  | `uint64` |
| `uncompressed_segment_names_len`| sum of the lengths of the uncompressed segment names    | `uint64` |
| `compression_str`        | Encoding strategy for the segment sequences (2 bytes)       | `uint16` |
| `compressed_str_len`     | length of compressed segment_sequences field                | `uint64` |
| `uncompressed_str_len`   | sum of the lengths of uncompressed segment_sequences fields | `uint64` |

The length of the uncompressed segment names does not include any terminator character.

#### Payload

| Field             | Description       | Type      |
|-------------------|-------------------|-----------|
| `segment_names`   | Segment names     | `strings` |
| `sequences`       | Segment sequences | `strings` |

**Layout:** The payload consists of encoded segment names followed by encoded sequences. 
We have two distinct encoding strategies.

### Links Block

Each block consists of a header and a payload.

#### Header

The following is the sequence of fields making up the header.

| Field                     | Description                                            | Type     |
|---------------------------|--------------------------------------------------------|----------|
| `section_id`              | Section type (3 = links)                               | `uint8`  |
| `record_num`              | number of records in the block                         | `uint16` |
| **From/To field**         |                                                        |          |
| `compression_fromto`      | Encoding strategy for the from and to fields (2 bytes) | `uint16` |
| `compressed_fromto_len`   | length of compressed from/to payload (metadata + blob) | `uint64` |
| **CIGAR field**           |                                                        |          |
| `compression_cigars`      | Encoding strategy for the cigar strings (4 bytes)      | `uint32` |
| `compressed_cigars_len`   | length of compressed cigars payload (metadata + blob)  | `uint64` |
| `uncompressed_cigars_len` | sum of the lengths of uncompressed cigars              | `uint64` |

#### Payload

The following is the sequence of fields making up the payload layout.
Each field is padded so that it is aligned with a byte.
For example, if the list of `from_ids` requires 155 bits, it is padded with 5 additional zero bits, so that the overall
length is 20 bytes.

| Field              | Description                                       | Type            |
|--------------------|---------------------------------------------------|-----------------|
| `from_ids`         | Tail segment IDs (1-based; 0 = no connection)       | `uints`         |
| `to_ids`           | Head segment IDs (1-based; 0 = no connection)       | `uints`         |
| `from_orientation` | Orientations of all from segments. 0 is +, 1 is - | `bits` (length = record_num) |
| `to_orientation`   | Orientations of all to segments. 0 is +, 1 is -   | `bits` (length = record_num) |
| `cigar_strings`    | CIGAR strings                                     | `strings`       |

**Segment ID encoding:** Segment IDs in the links payload are stored as 1-based indices into the segment list (value = internal_segment_id + 1, where internal IDs start at 0). The value 0 is reserved to indicate "no connection". The reader converts back to 0-based by subtracting 1.

**Orientation mapping:** The i-th bit in `from_orientation` corresponds to the i-th segment ID in `from_ids`. Similarly, the i-th bit in `to_orientation` corresponds to the i-th segment ID in `to_ids`.
Therefore there are exactly `record_num` segment IDs in both the `from_ids` and in the `to_ids` lists and there are exactly
`record_num` bits in both the `from_orientation` and in the `to_orientations` lists.

Orientation bits are stored with a least significant bit (LSB-first) strategy within each `uint64` word. See the "Bits" section for details.

### Paths Block

Each block consists of a header and a payload.

#### Header

The following is the sequence of fields making up the header.

| Field                         | Description                                                      | Type     |
|-------------------------------|------------------------------------------------------------------|----------|
| `section_id`                  | Section type (4 = paths)                                         | `uint8`  |
| `record_num`                  | number of records in the block                                   | `uint16` |
| `compression_path_names`      | Encoding strategy for the path names (2 bytes)                   | `uint16` |
| `compressed_path_names_len`   | length of compressed concatenated path names                     | `uint64` |
| `uncompressed_path_names_len` | length of uncompressed concatenated path names                   | `uint64` |
| `compression_paths`           | Encoding strategy for the paths as list of segment IDs (4 bytes) | `uint32` |
| `compressed_paths_len`        | length of compressed paths                                       | `uint64` |
| `uncompressed_paths_len`      | sum of the lengths of uncompressed paths (as segment ID strings) | `uint64` |
| `compression_cigars`          | Encoding strategy for the cigar strings (4 bytes)                | `uint32` |
| `compressed_len_cigar`        | length of compressed concatenated cigars                         | `uint64` |
| `uncompressed_len_cigar`      | sum of the lengths of uncompressed concatenated cigars strings   | `uint64` |

#### Payload

The following is the sequence of fields making up the payload layout.

| Field           | Description                                            | Type            |
|-----------------|--------------------------------------------------------|-----------------|
| `path_names`    | Path names                                             | `strings`       |
| `paths`         | Paths, each path is a sequence of oriented segment IDs | `walks`         |
| `cigar_strings` | The list of CIGAR strings                              | `strings`       |

### Walks Block

Each block consists of a header and a payload.

#### Header

The following is the sequence of fields making up the header.

| Field                        | Description                                                             | Type     |
|------------------------------|-------------------------------------------------------------------------|----------|
| `section_id`                 | Section type (5 = walks)                                                | `uint8`  |
| `record_num`                 | number of records in the block                                          | `uint16` |
| **Compression strategies**   |                                                                         |          |
| `compression_sample_ids`     | Encoding strategy for the sample IDs (2 bytes)                          | `uint16` |
| `compression_hep`            | Encoding strategy for the haplotype indices (2 bytes)                   | `uint16` |
| `compression_sequence`       | Encoding strategy for the sequence IDs (2 bytes)                        | `uint16` |
| `compression_positions`      | Encoding strategy for the start and end positions (2 bytes)             | `uint16` |
| `compression_walks`          | Encoding strategy for the walks (4 bytes)                               | `uint32` |
| **Samples field**            |                                                                         |          |
| `compressed_sample_ids_len`  | length of compressed sample IDs payload (metadata + blob)               | `uint64` |
| `uncompressed_sample_ids_len`| sum of the lengths of uncompressed sample IDs                           | `uint64` |
| **Haplotype indices field**  |                                                                         |          |
| `compressed_hep_len`         | length of compressed haplotype indices payload (metadata + blob)        | `uint64` |
| `uncompressed_hep_len`       | sum of the lengths of uncompressed haplotype indices                    | `uint64` |
| **Sequence IDs field**       |                                                                         |          |
| `compressed_sequence_len`    | length of compressed sequence IDs payload (metadata + blob)             | `uint64` |
| `uncompressed_sequence_len`  | sum of the lengths of uncompressed sequence IDs                         | `uint64` |
| **Positions field**          |                                                                         |          |
| `compressed_positions_len`   | length of compressed positions payload (metadata + blob)                | `uint64` |
| `uncompressed_positions_len` | sum of the lengths of uncompressed positions                            | `uint64` |
| **Walks field**              |                                                                         |          |
| `compressed_walk_len`        | length of compressed walks payload (metadata + blob)                    | `uint64` |
| `uncompressed_walk_len`      | sum of the lengths of uncompressed walks (total segment occurrences)    | `uint64` |

#### Payload

The following is the sequence of fields making up the payload layout.

| Field               | Description                                            | Type      |
|---------------------|--------------------------------------------------------|-----------|
| `sample_ids`        | Sample IDs                                             | `strings` |
| `haplotype_indices` | Haplotype indices                                      | `uints`   |
| `sequence_ids`      | Sequence IDs                                           | `strings` |
| `start_positions`   | Start positions                                        | `uints`   |
| `end_positions`     | End positions                                          | `uints`   |
| `walks`             | Walks, each walk is a sequence of oriented segment IDs | `walks`   |

Since there are `record_num` records in the block, the block contains `record_num` sample IDs, followed by  `record_num`
haplotype indices, followed by  `record_num` sequence IDs, followed by  `record_num` start positions, followed by
`record_num` end positions, followed by  `record_num` walks.

## Walks Type Format

The `walks` type encodes a list of walks, where each walk is a sequence of oriented segment IDs. This type is used in the Paths and Walks blocks.
Since we know that there are  `record_num` walks in the block, we do not have to store that information again.
The `walks` layout is made by the following sequence of fields.


| Field                | Description                   | Type    |
|----------------------|-------------------------------|---------|
| `walks_lengths`      | The lengths of the walks      | `uints` |
| `walks_segments`     | The segment IDs of the walks  | `uints` |
| `walks_orientations` | The orientations of the walks | `bits`  |
|                      |                               |         |

-  All lengths of the walks are followed by all segment IDs of the walks, followed by all walks orientations.
-  The `walks_lengths` field contains exactly `record_num` integers. The i-th integer L(i) is the length of the i-th walk of the block. The sum of all L(i) equals `uncompressed_walk_len` from the containing block header.
-  The `walks_segments` field contains a sequence of `uncompressed_walk_len` integers. The first L(1) integers form the sequence of segment IDs of the first walk, then the subsequent L(2) integers form the sequence of the segment IDs of the second walk, etc.
-  The `walks_orientations` field contains a sequence of `uncompressed_walk_len` bits. The first L(1) bits form the sequence of segment orientations of the first walk, then the subsequent L(2) bits form the sequence of the segment orientations of the second walk. Orientation `+` or `>` is encoded as `0`, while `-` or `<` is encoded as 1.
-  **Encoding strategy:** Both `walks_lengths` and `walks_segments` are encoded using the integer encoding strategy specified in bytes 3-4 of the `compression_walks` field in the containing block header. The `walks_orientations` field is always encoded as raw bits (no compression).

**Example:** Consider a walks block with 2 walks:
- Walk 1: "0+1-" (length 2, segments 0 and 1 with orientations + and -)
- Walk 2: "2+" (length 1, segment 2 with orientation +)

This would be encoded as:
- `walks_lengths`: [2, 1] (encoded per the integer strategy in bytes 3-4)
- `walks_segments`: [0, 1, 2] (segment IDs for both walks concatenated)
- `walks_orientations`: [0, 1, 0] (0=+, 1=- for each segment, packed as bits)


## Strings Encoding strategies

When we have to encode a list of strings (the `strings` type), we choose the encoding strategy with a code consisting of
two bytes.

The first byte (high byte) encodes the strategy for a sequence of uints, which are usually the lengths of the strings to encode
and/or the starting and ending position of the strings within a superstring (which might be the concatenation of all
strings, without the terminator character `\0`).

The start and end positions are 0-based, the final position is excluded from the substring, following Python slice conventions.

The second byte (low byte) represents the strategy for encoding the superstring/concatenation.

What numbers are actually stored depends on the encoding used for the string:
- **Concatenation**: requires storing the lengths of the strings
- **Superstring**: requires storing the initial and final position of each string within the superstring

For example, the code 0x0102 is used for method 0x01 (varint) for the lengths and method 0x02 (fixed16) for the strings.

We use question marks `??` to represent that all values of the byte can be used.

| Code     | Strategy                    | Type     |
|----------|-----------------------------|----------|
| `0x00??` | none (identity)             | `uints`  |
| `0x??00` | Concatenation + none        | `string` |
| `0x01??` | varint                      | `uints`  |
| `0x02??` | fixed16                     | `uints`  |
| `0x03??` | delta                       | `uints`  |
| `0x04??` | elias gamma                 | `uints`  |
| `0x05??` | elias omega                 | `uints`  |
| `0x06??` | golomb                      | `uints`  |
| `0x07??` | rice                        | `uints`  |
| `0x08??` | streamvbyte                 | `uints`  |
| `0x09??` | vbyte                       | `uints`  |
| `0x0A??` | fixed32                     | `uints`  |
| `0x0B??` | fixed64                     | `uints`  |
| `0x??01` | Concatenation + zstd        | `string` |
| `0x??02` | Concatenation + gzip        | `string` |
| `0x??03` | Concatenation + lzma        | `string` |
| `0x??04` | Concatenation + Huffman     | `string` |
| `0x??05` | Concatenation + 2-bit       | `string` |
| `0x??06` | Concatenation + Arithmetic  | `string` |
| `0x??07` | Concatenation + BWT+Huffman | `string` |
| `0x??08` | Concatenation + RLE         | `string` |
| `0x??09` | Concatenation + CIGAR       | `string` |
| `0x??0A` | Concatenation + Dictionary  | `string` |
| `0x??0B` | Reserved                    |          |
| `0x??0C` | Concatenation + LZ4         | `string` |
| `0x??0D` | Concatenation + Brotli      | `string` |
| `0x??0E` | Concatenation + PPM         | `string` |
| `0x??F0` | Superstring + none          | `string` |
| `0x??F4` | Superstring + Huffman       | `string` |
| `0x??F5` | Superstring + 2-bit DNA     | `string` |

*  **Concatenation** means that the strings are concatenated after removing the `\0` character that ends them, then they are
   concatenated. What follows the `+` sign is an encoding/compression method applied on the concatenation.
*  **Superstring** means that we compute a superstring with a heuristic method of the input strings after removing the `\0`
   character that ends them. What follows the `+` sign is an encoding/compression method applied on the superstring.

## Integer Encoding Algorithms

This section defines the algorithms for integer encoding strategies referenced in the Strings Encoding strategies section (lines 302-353).

### Delta (0x03??)

The delta encoding stores differences between consecutive values. This is particularly effective for sorted or monotonically increasing sequences.

**Format:**
- First value stored as-is using the base encoding
- Subsequent values stored as: value[i] - value[i-1]
- The decoder adds each delta to the previous reconstructed value

**Example:** Sequence [100, 105, 108, 110] encoded as delta:
- Stored: [100, 5, 3, 2]
- Decoded: [100, 100+5=105, 105+3=108, 108+2=110]

**Error handling:** A reader encountering a non-monotonic (decreasing) delta value during decoding MUST treat it as a fatal error.

### Elias Gamma (0x04??)

Elias gamma encoding represents a number n using two parts:
1. Unary representation of floor(log2(n)) + 1
2. Binary representation of n - 2^floor(log2(n))

**Format:**
- For value n:
  - Write floor(log2(n)) + 1 in unary (that many 1 bits, followed by 0)
  - Write n - 2^floor(log2(n)) in binary (floor(log2(n)) bits)

**Example:** n = 5
- floor(log2(5)) + 1 = 3
- Unary: 1110
- n - 2^2 = 5 - 4 = 1 = 01 (2 bits)
- Complete: 111001

### Elias Omega (0x05??)

Elias omega starts with 0 and builds up, using the previous code length.

**Format:**
- For n = 1: output "0"
- For n > 1:
  1. Write n in binary
  2. Remove leading 1
  3. Recursively encode length of remaining bits using omega
  4. Append original bits

### Golomb (0x06??)

Golomb encoding uses a parameter b (default b=128).

**Format:**
- For value n:
  - quotient q = n // b, remainder r = n % b
  - Write q in unary (q ones, then zero)
  - Write r in binary using ceil(log2(b)) bits

**Default parameter:** b = 128

### Rice (0x07??)

Rice coding is Golomb with b as a power of 2: b = 2^k.

**Format:**
- Parameter k (0-31) stored as the first byte of the integer payload (before the encoded values)
- For value n:
  - quotient q = n >> k
  - remainder r = n & (2^k - 1)
  - Write q in unary
  - Write r in binary using k bits

**Example:** For k=3 and sequence [5, 12, 7]:
- Parameter byte: 0x03
- Encoded values follow the parameter byte

### StreamVByte (0x08??)

StreamVByte encodes multiple varints in parallel using SIMD-like packing.

**Format:**
- Control bytes indicate which varints use 1, 2, 3, or 4 bytes
- Data bytes contain the varints packed together

### VByte (0x09??)

Variable Byte encoding uses 7 bits per byte for data, with high bit as continuation flag.

**Format:**
- Each byte: 7 data bits + 1 continuation bit (1 = more bytes follow, 0 = last byte)
- Little-endian ordering (least significant byte first)

### Payload for encoded `strings`

The payload of the encoded `strings` consists of:

1.  **Metadata**: A list of numbers, encoded according to the first-byte strategy (varint, fixed16, etc).
    - For **Concatenation**: This list contains the lengths of each string.
    - For **Superstring**: This list contains first all start positions, then all end positions of the strings.

    The first-byte strategy determines how this list of numbers is encoded. For superstring encoding, start and end positions are encoded independently using the same strategy.

2.  **Blob**: The superstring or the concatenated string, encoded according to the second-byte strategy.

**Layout for Concatenation encoding:**
```
[length_0][length_1]...[length_n-1][blob]
```

**Layout for Superstring encoding:**
```
[start_0][start_1]...[start_n-1][end_0][end_1]...[end_n-1][blob]
```

All start positions are encoded first (as a contiguous list), followed by all end positions (as a contiguous list). Both lists use the same integer encoding strategy specified in the first byte of the compression code.

The `compressed_*_len` fields in block headers represent the total number of bytes for the encoded payload of that field, including both the integer metadata list and the compressed blob. To determine the total payload size for a block, a reader sums all `compressed_*_len` values in the block header.

The `uncompressed_len` field is the sum of the lengths of the original strings (before any encoding).

## Bits

A `bits` field represents a list of bits packed into `uint64` words in little-endian format.

**Packing strategy:**
- Bits are packed LSB-first within each `uint64` word
- Bit at index `i` is stored at position `i % 64` within word `i // 64`
- The number of `uint64` words is `ceil(n / 64)` where `n` is the number of bits
- Unused bits in the final word (if any) are set to 0 when writing and MUST be ignored when reading

**Determining the number of bits (n):** The value of `n` depends on the context:
- **Links block orientations** (`from_orientation`, `to_orientation`): `n = record_num` from the block header
- **Walks type orientations** (`walks_orientations`): `n = uncompressed_walk_len` from the containing block header
- **Walks/Paths block strategy codes** (orientation + strid/numid): `n` equals the total number of segment occurrences across all walks/paths
- **Huffman encoded data**: `n` is determined by decoding exactly the required number of symbols (e.g., `2 * L` nibbles for a string of length `L`)

**Size calculation:** Number of uint64 words = `ceil(n / 64)`. Total bytes for bits field = `8 * ceil(n / 64)`.

**Example:** For orientations `[1, 0, 1, 1, 0, ...]` (64 bits):
- Word 0 = `0b...01101` (bit 0 = 1, bit 1 = 0, bit 2 = 1, bit 3 = 1, bit 4 = 0, ...)

## Arithmetic Coding (0x??06)

**Format:**
- `uint32`: frequency table size (number of symbol-frequency pairs), little-endian
- `bytes`: frequency table (symbol:count pairs)
- `bytes`: arithmetic encoded data

The frequency table contains ONLY symbols with non-zero frequency. Each entry is a pair of:
- `symbol`: 1 byte (ASCII value)
- `frequency`: `uint32` little-endian (count of symbol occurrences)

The `frequency table size` field indicates the number of pairs in the table. Total frequency table size = `frequency_table_size * 5` bytes (1 byte symbol + 4 bytes frequency per entry).

## Huffman Coding (0x??04, 0x??F4)

The Huffman encoding of a string (be it the concatenation or a superstring) consists of:

| Name              | Description                             | Type     |
|-------------------|-----------------------------------------|----------|
| `codebook_len`    | Length of the encoded codebook in bytes | `uint16` |
| `codebook`        | 16 little-endian uint16 bit-lengths     | `bytes`  |
| `huffman_encoded` | The encoded string                      | `bits`   |

**Codebook format:**
The codebook is exactly 32 bytes containing 16 little-endian uint16 values representing the bit-length for each nibble (0x0 through 0xF). Even entries with zero bit-length have a placeholder value of 0 in the codebook.

```python
# Codebook structure (32 bytes total)
codebook = struct.unpack('<16H', codebook_bytes)
# codebook[0] = bit-length for nibble 0x0
# codebook[1] = bit-length for nibble 0x1
# ...
# codebook[15] = bit-length for nibble 0xF
```

**Reconstruction:**
The decoder MUST reconstruct the Huffman codes from the 16 bit-lengths using canonical Huffman code assignment:

1. Collect all (symbol, bit-length) pairs where bit-length > 0
2. Sort primarily by bit-length (ascending) and secondarily by symbol value (ascending)
3. Assign codes sequentially using the following algorithm:
   ```python
   # Initialize
   code = 0
   prev_len = 0
   huffman_codes = {}  # symbol -> (code, bit_length)
   
   for symbol, bit_len in sorted_pairs:
       # Left-shift to account for increased bit length
       code = (code + 1) << (bit_len - prev_len) if prev_len > 0 else 0
       # Store code in MSB-first format (most significant bit first in stream)
       huffman_codes[symbol] = (code, bit_len)
       prev_len = bit_len
   ```
4. Zero bit-length symbols are not in the alphabet and will not appear in the encoded data

**Example:** Given bit-lengths: `{0x41: 2, 0x42: 3, 0x43: 3}` (symbols 'A', 'B', 'C'):
- Sorted by (bit-length, symbol): `[(0x41, 2), (0x42, 3), (0x43, 3)]`
- Code assignment:
  - 'A' (0x41): bit-length=2, code=0b00 (first, shortest)
  - 'B' (0x42): bit-length=3, code=(0b00+1)<<1 = 0b010
  - 'C' (0x43): bit-length=3, code=(0b010+1)<<0 = 0b011

**Encoding process:**
1. Convert each input byte to two nibbles (high nibble, low nibble)
2. Look up each nibble's code in the reconstructed codebook
3. Concatenate all codes into a bitstream
4. Pad to byte boundary with zeros

**Decoding:**
The byte-length of the `huffman_encoded` data is the total `compressed_len` of the field minus:
- bytes consumed by the string metadata
- 2-byte `codebook_len`
- 32 bytes for the codebook

The decoder MUST decode exactly `2 * L` symbols, where `L` is the number of characters in the string being reconstructed.

### Nibble-Level Processing

1. **Symbol Extraction**: Each byte of the target string (the concatenated string or the superstring) is treated as two 4-bit symbols:
   - Symbol A: High nibble (bits 4-7)
   - Symbol B: Low nibble (bits 0-3)

2. **Encoding Order**: For every byte, Symbol A is encoded first, followed immediately by Symbol B.

3. **Alphabet Size**: The codebook always contains 16 entries (representing nibbles 0x0 through 0xF). A bit-length of 0 indicates the nibble is not present.

## BWT + Huffman encoding (0x??07)

Burrows-Wheeler Transform + Huffman coding provides excellent compression for repetitive sequences like DNA. The pipeline is:

1. Apply Burrows-Wheeler Transform in fixed 64KB blocks
2. Apply Move-to-Front transform
3. Encode with Huffman coding

The block size is fixed at 65536 bytes (64KB).

**Format:**
- `uint32`: number of BWT blocks
- For each block:
  - `uint32`: primary index
  - `uint32`: block size
  - `bytes`: BWT-transformed data (MTF-encoded, then Huffman-encoded)

## 2-bit DNA Encoding (0x??05)

2-bit DNA encoding provides optimal compression for DNA/RNA sequences by encoding each nucleotide in 2 bits instead of 8 bits (75% size reduction). This is the most impactful encoding for pangenome data where sequences typically comprise 70-80% of file content.

**Nucleotide Mapping:**
- A (or a) = 00
- C (or c) = 01
- G (or g) = 10
- T (or t) = 11
- U (or u) = 11 (RNA uracil treated as thymine)

**Bit packing:** Nucleotides are packed MSB-first. The first nucleotide is stored in bits 7-6 of the first byte, the second in bits 5-4, the third in bits 3-2, the fourth in bits 1-0. Subsequent nucleotides continue in subsequent bytes.

**Example:** Sequence "ACGT" (4 nucleotides):
- A=00, C=01, G=10, T=11
- Packed: `0b00011011` = 0x1B (1 byte)

**Example:** Sequence "ACGTA" (5 nucleotides):
- A=00, C=01, G=10, T=11, A=00
- Packed: `0b00011011` `0b00000000` = 0x1B 0x00 (2 bytes, last 6 bits are padding)

**Note:** Unused bits in the final byte MUST be set to 0 when writing and MUST be ignored when reading.

**Format:**
- 1 byte: flags
  - bit 0: `has_exceptions` (1 if exception table present, 0 otherwise)
  - bits 1-7: reserved (set to 0)
- `packed_bases`: 4 nucleotides per byte (2 bits each), padded with 0s if needed
- If the `has_exception` flag is set:
  - `varint`: exception count
  - `varint` list: exception positions (0-based indices in original sequence)
  - `bytes`: exception characters (one byte per exception, in ASCII)

**Exception Handling:**
Ambiguity codes (N, R, Y, K, M, S, W, B, D, H, V, -) and unknown characters are stored in the exception table with their original ASCII values, allowing perfect reconstruction while maintaining compression on standard ACGT sequences.

**Expected Compression:** 75% reduction on pure DNA/RNA sequences, slightly less with ambiguity codes.

**Primary Use Case:** Segment sequences, which are typically the largest data component in BGFA files.

## Run-Length Encoding - RLE (0x??08)

Run-Length Encoding efficiently compresses sequences with repeated characters (homopolymers in DNA, repeated operations in other contexts). The implementation uses a hybrid mode that switches between raw and RLE encoding to prevent expansion on non-repetitive data.

**Format:**
- `varint`: run count (number of runs)
- For each run:
  - 1 byte: mode (0x00=raw, 0x01=RLE)
  - `varint`: run data length
  - run data:
    - If raw mode: raw bytes
    - If RLE mode: sequence of `[char: 1 byte][count: varint]` pairs

**Algorithm:**
- Minimum run length: 3 characters (shorter runs use raw encoding)
- Automatically switches between raw and RLE modes within a string to prevent expansion on non-repetitive data
- Run counts encoded as varint for efficiency

**Mode selection:** A run of 3 or more identical consecutive characters uses RLE mode. Shorter sequences use raw mode.

**Expected Compression:** 30-50% reduction on sequences with homopolymers or repetitive patterns.

**Primary Use Cases:**
- DNA sequences with homopolymer runs (AAAAAAA, GGGGGG, TTTTTT)
- Can be combined with 2-bit DNA encoding for additional compression
- General string data with repeated characters

## Dictionary Encoding (0x??0A)

Dictionary encoding is optimized for repetitive string data by replacing repeated strings with short references to a dictionary.

**Format (Concatenation mode):**
- `uint32`: dictionary size (number of unique strings), little-endian
- `uints` list: dictionary entry offsets (N+1 values, where N = dictionary size)
  - Offsets are cumulative from the start of the dictionary blob
  - The (N+1)-th offset equals the total blob length
  - Offsets are encoded using the integer encoding strategy specified in the first byte (high byte) of the 2-byte compression code `0x??0A`
- `bytes`: concatenated dictionary entries (each entry is a unique string, no terminators)
- `uints` list: indices into dictionary for each input string, encoded using the same integer strategy as offsets

**Maximum dictionary size:** 65536 entries (configurable)

**Expected Compression:** 60-90% reduction on highly repetitive data (e.g., sample IDs repeated across thousands of walks).

**Primary Use Cases:**
- Sample identifiers in walk blocks
- Segment names with common prefixes
- Path names with structural patterns
- Any string list with high repetition

## CIGAR-Specific Encoding (0x??09)

CIGAR strings represent sequence alignments with alternating numbers and operation letters. This encoding exploits the structure of CIGAR strings to achieve better compression than general-purpose methods.

**CIGAR Operations:**
```
M = 0x0 (match/mismatch)
I = 0x1 (insertion)
D = 0x2 (deletion)
N = 0x3 (skipped region)
S = 0x4 (soft clipping)
H = 0x5 (hard clipping)
P = 0x6 (padding)
= = 0x7 (sequence match)
X = 0x8 (sequence mismatch)
```

**Format:**
- `varint`: number of operations
- `packed_ops`: 2 operations per byte (4 bits each)
  - High nibble: operation n
  - Low nibble: operation n+1
  - If odd number of operations, low nibble of last byte = 0xF (padding marker)
- `varint` list: operation lengths

**Special case:** The CIGAR value `*` (indicating no alignment) is encoded as a single byte `0xFF`. This allows efficient representation of unaligned segments.

**Example:**
CIGAR string "10M2I5D" is encoded as:
- `num_ops`: 3 (varint)
- `packed_ops`: 0x01, 0x2F (operations M=0, I=1, D=2 with padding 0xF)
- `lengths`: 10, 2, 5 (varints)

**Expected Compression:** 40-60% reduction compared to ASCII CIGAR strings.

**Primary Use Cases:**
- Link overlaps (L lines in GFA)
- Path CIGAR strings (P lines in GFA)
- Any alignment representation using CIGAR format

## CIGAR 4-byte Strategy Codes

For CIGAR strings, we use 4 bytes to encode the strategy. The first byte represents how we decompose the CIGAR strings, the other three bytes specify how we encode each component.

| Code         | Strategy                             |
|--------------|--------------------------------------|
| `0x00??????` | none (identity)                      |
| `0x01??????` | numOperations + lengths + operations |
| `0x02??????` | string (treat as plain string)       |

### numOperations + lengths + operations (0x01??????)

We encode three components:

1. The list of the number of operations in each CIGAR string (`uints`) - encoded with strategy in byte 2
2. The list of lengths of the operations (`uints`) - encoded with strategy in byte 3
3. The operations as a packed string - encoded with strategy in byte 4

**Format:**
- Byte 1 (0x01): Use numOperations+lengths+operations decomposition
- Byte 2: Integer encoding strategy for operation counts (e.g., 0x01 for varint, 0x02 for fixed16)
- Byte 3: Integer encoding strategy for operation lengths (e.g., 0x01 for varint, 0x03 for LZMA)
- Byte 4: String encoding strategy for packed operations (e.g., 0x00 for none, 0x04 for Huffman)

**Example:** `0x01020304` means:
- Byte 1 (0x01): Use numOperations+lengths+operations decomposition
- Byte 2 (0x02): Use fixed16 to encode the list of operation counts
- Byte 3 (0x03): Use lzma to encode the operation lengths
- Byte 4 (0x04): Use Huffman to encode the packed operations string

### string (0x02??????)

We compress the CIGAR strings separated by newlines with the method specified in the second byte.

**Example:** `0x02030000` means:
- Byte 1 (0x02): Use string decomposition
- Byte 2 (0x03): Use lzma to compress the newline-separated CIGAR strings
- Bytes 3-4: Reserved (set to 0)

## Walks and Paths 4-byte Strategy Codes

For walks and paths, we use 4 bytes to encode the strategy. The first byte represents how we decompose the walk (or the path), the other three bytes specify how we encode each component.

| Code         | Strategy            |
|--------------|---------------------|
| `0x00??????` | none (identity)     |
| `0x01??????` | orientation + strid |
| `0x02??????` | orientation + numid |

### orientation + strid (0x01??????)

We encode two components:

1. The list of orientations in binary form (0 corresponds to `>` or `+`, 1 corresponds to `<` or `-`) - encoded as `bits`
2. The list of segment IDs encoded as strings - encoded with strategy specified in bytes 3-4

**Format:**
- Byte 1 (0x01): Use orientation + strid decomposition
- Byte 2: Reserved (MUST be set to 0x00, ignored on read)
- Bytes 3-4: String encoding strategy for segment IDs (e.g., 0x0100 for varint lengths + none)

### orientation + numid (0x02??????)

We encode two components:

1. The list of orientations in binary form (0 corresponds to `>` or `+`, 1 corresponds to `<` or `-`) - encoded as `bits`
2. The list of segment IDs as integers - encoded with strategy specified in bytes 3-4

**Format:**
- Byte 1 (0x02): Use orientation + numid decomposition
- Byte 2: Reserved (MUST be set to 0x00, ignored on read)
- Bytes 3-4: Integer encoding strategy for segment IDs (e.g., 0x0100 for varint)

**Layout:** `[orientation_bits][segment_ids_encoded]`

## Conformance Requirements

**Minimum reader requirements:** A compliant BGFA reader MUST support all encodings:

**Writer requirements:** A compliant BGFA writer:
- MUST produce valid BGFA files that can be read by any compliant reader
- MUST set reserved fields to 0
- MUST NOT write empty blocks (blocks with `record_num = 0`). If a block type has no records, omit the block entirely.
- MUST use encodings only within their valid ranges (e.g., delta encoding only for monotonically non-decreasing sequences)

**Error handling:**
- A reader encountering an unknown `section_id` MUST skip the block (using the block header to determine its size) without error.
- A reader encountering an unknown strategy code MUST treat it as a fatal error.
- A reader encountering truncated or corrupted data MUST treat it as a fatal error.

---

## Appendix A: Example BGFA Files

This appendix shows complete BGFA files encoding example graphs.

### Appendix A.1: Minimal BGFA File

This appendix shows a complete minimal BGFA file encoding a simple graph with 3 segments and 2 links.

### Source GFA1 text

```gfa
H	VN:Z:1.0
S	A	ACGT
S	B	GCCA
S	C	TAAC
L	A	+	B	+	4M
L	B	-	C	+	3M
```

### Binary encoding (hex dump)

**File Header (17 bytes):**
```
42 47 46 41    # magic_number: "BGFA" (little-endian 0x41464742)
00 00          # version: 0
09 00          # header_len: 9 bytes
56 4E 3A 5A 3A 31 2E 30 00  # header: "VN:Z:1.0" + null terminator
```

**Segments Block (section_id = 2):**

Header:
```
02             # section_id: 2 (segments)
03 00          # record_num: 3
01 00          # compression_names: 0x0001 (varint lengths, none for blob)
0C 00 00 00    # compressed_names_len: 12 bytes
03 00 00 00    # uncompressed_names_len: 3 bytes
01 00          # compression_str: 0x0001 (varint lengths, none for blob)
0C 00 00 00    # compressed_str_len: 12 bytes
0C 00 00 00    # uncompressed_str_len: 12 bytes
```

Payload - Names (concatenation with varint lengths):
```
01 01 01       # lengths: 1, 1, 1 (varint)
41 42 43       # blob: "ABC"
```

Payload - Sequences (concatenation with varint lengths):
```
04 04 04       # lengths: 4, 4, 4 (varint)
41 43 47 54    # blob: "ACGT"
47 43 43 41    # blob: "GCCA"
54 41 41 43    # blob: "TAAC"
```

**Links Block (section_id = 3):**

Header:
```
03             # section_id: 3 (links)
02 00          # record_num: 2
01 00          # compression_fromto: 0x0001 (varint)
04 00 00 00    # compressed_fromto_len: 4 bytes
01 00 00 00    # compression_cigars: 0x00000001 (varint, 4 bytes)
06 00 00 00    # compressed_cigars_len: 6 bytes
06 00 00 00    # uncompressed_cigars_len: 6 bytes
```

Payload:
```
01 02          # from_ids: 1, 2 (1-based: A=1, B=2)
02 03          # to_ids: 2, 3 (1-based: B=2, C=3)
00             # from_orientation: bits [0, 0] = 0x00 (both +)
02             # to_orientation: bits [0, 1] = 0x02 (first +, second -)
04 03          # cigar lengths: 4, 3 (varint)
34 4D 34 4D    # cigar blob: "4M4M" (first 3 bytes used, last is padding)
33 4D 00       # cigar blob continued: "3M" + padding
```

**Total file size:** ~100 bytes

### Decoding notes

1. Segment IDs are assigned in order of appearance: A=0, B=1, C=2 (0-based internal IDs)
2. In the links payload, IDs are stored as 1-based: A=1, B=2, C=3. The reader converts back to 0-based by subtracting 1.
3. Link 1: from segment 0 (A), orientation + (bit 0), to segment 1 (B), orientation + (bit 0)
4. Link 2: from segment 1 (B), orientation + (bit 0), to segment 2 (C), orientation - (bit 1)
5. Orientation bits are LSB-first: for to_orientation, bit 0 = first link (+), bit 1 = second link (-), giving 0b10 = 0x02

## Appendix A.2: Complex BGFA File with Paths and Walks

This appendix shows a more complex BGFA file encoding a graph with segments, links, a path, and a walk to demonstrate additional features.

### Source GFA1 text

```gfa
H	VN:Z:1.0
S	S1	AAAA
S	S2	TTTT
S	S3	CCCC
L	S1	+	S2	+	4M
L	S2	-	S3	+	3M
P	path1	S1+,S2-,S3+	4M3M
W	walk1	0	S1	0	*	S1+S2-S3+
```

### Binary encoding (hex dump)

**File Header (17 bytes):**
```
42 47 46 41    # magic_number: "BGFA" (little-endian 0x41464742)
00 00          # version: 0
09 00          # header_len: 9 bytes
56 4E 3A 5A 3A 31 2E 30 00  # header: "VN:Z:1.0" + null terminator
```

**Segments Block (section_id = 2):**

Header:
```
02             # section_id: 2 (segments)
03 00          # record_num: 3
01 00          # compression_segment_names: 0x0001 (varint lengths, none for blob)
06 00 00 00    # compressed_segment_names_len: 6 bytes
03 00 00 00    # uncompressed_segment_names_len: 3 bytes
01 00          # compression_sequences: 0x0001 (varint lengths, none for blob)
0C 00 00 00    # compressed_sequences_len: 12 bytes
0C 00 00 00    # uncompressed_sequences_len: 12 bytes
```

Payload - Segment Names (concatenation with varint lengths):
```
02 02 02       # lengths: 2, 2, 2 (varint)
53 31 53 32 53 33  # blob: "S1S2S3"
```

Payload - Sequences (concatenation with varint lengths):
```
04 04 04       # lengths: 4, 4, 4 (varint)
41 41 41 41    # blob: "AAAA"
54 54 54 54    # blob: "TTTT"
43 43 43 43    # blob: "CCCC"
```

**Links Block (section_id = 3):**

Header:
```
03             # section_id: 3 (links)
02 00          # record_num: 2
01 00          # compression_fromto: 0x0001 (varint)
04 00 00 00    # compressed_fromto_len: 4 bytes
01 00 00 00    # compression_cigars: 0x00000001 (varint, 4 bytes)
06 00 00 00    # compressed_cigars_len: 6 bytes
06 00 00 00    # uncompressed_cigars_len: 6 bytes
```

Payload:
```
01 02          # from_ids: 1, 2 (1-based: S1=1, S2=2)
02 03          # to_ids: 2, 3 (1-based: S2=2, S3=3)
00             # from_orientation: bits [0, 0] = 0x00 (both +)
02             # to_orientation: bits [0, 1] = 0x02 (first +, second -)
04 03          # cigar lengths: 4, 3 (varint)
34 4D 34 4D    # cigar blob: "4M4M" (first 3 bytes used, last is padding)
33 4D 00       # cigar blob continued: "3M" + padding
```

**Paths Block (section_id = 4):**

Header:
```
04             # section_id: 4 (paths)
01 00          # record_num: 1
01 00          # compression_path_names: 0x0001 (varint lengths, none for blob)
06 00 00 00    # compressed_path_names_len: 6 bytes
06 00 00 00    # uncompressed_path_names_len: 6 bytes
00 00 00 00    # compression_paths: 0x00000000 (orientation + numid, varint for segment IDs, none for string)
00 00 00 00    # compressed_paths_len: 0 bytes
00 00 00 00    # uncompressed_paths_len: 0 bytes
01 00 00 00    # compression_cigars: 0x00000001 (varint, 4 bytes)
06 00 00 00    # compressed_len_cigar: 6 bytes
06 00 00 00    # uncompressed_len_cigar: 6 bytes
```

Payload - Path Names (concatenation with varint lengths):
```
06 00          # length: 6 (varint)
70 61 74 68 31 31  # blob: "path1"
```

Payload - Paths (walks type with orientation + numid):
```
04             # walks_lengths: [4] (varint)
01 02 03       # walks_segments: [1, 2, 3] (segment IDs as varint)
00             # walks_orientations: bits [0, 1, 0] = 0x00 (+,-,+)
```

Payload - Cigar Strings (concatenation with varint lengths):
```
02 02          # lengths: 2, 2 (varint)
34 4D 33 4D    # blob: "4M3M"
```

**Walks Block (section_id = 5):**

Header:
```
05             # section_id: 5 (walks)
01 00          # record_num: 1
01 00          # compression_sample_ids: 0x0001 (varint lengths, none for blob)
02 00 00 00    # compressed_sample_ids_len: 2 bytes
02 00 00 00    # uncompressed_sample_ids_len: 2 bytes
01 00          # compression_haplotype_indices: 0x0001 (varint)
04 00 00 00    # compressed_haplotype_indices_len: 4 bytes
04 00 00 00    # uncompressed_haplotype_indices_len: 4 bytes
01 00          # compression_sequence_ids: 0x0001 (varint lengths, none for blob)
02 00 00 00    # compressed_sequence_ids_len: 2 bytes
02 00 00 00    # uncompressed_sequence_ids_len: 2 bytes
01 00          # compression_start_positions: 0x0001 (varint)
04 00 00 00    # compressed_start_positions_len: 4 bytes
04 00 00 00    # uncompressed_start_positions_len: 4 bytes
01 00          # compression_end_positions: 0x0001 (varint)
04 00 00 00    # compressed_end_positions_len: 4 bytes
04 00 00 00    # uncompressed_end_positions_len: 4 bytes
00 00 00 00    # compression_walks: 0x00000000 (orientation + numid, varint for segment IDs, none for string)
00 00 00 00    # compressed_walk_len: 0 bytes
00 00 00 00    # uncompressed_walk_len: 0 bytes
```

Payload - Sample IDs (concatenation with varint lengths):
```
01 01          # lengths: 1, 1 (varint)
30             # blob: "0"
```

Payload - Haplotype Indices (varint):
```
00             # value: 0 (varint)
```

Payload - Sequence IDs (concatenation with varint lengths):
```
02 02          # lengths: 2, 2 (varint)
53 31 53 33    # blob: "S1S3"
```

Payload - Start Positions (varint):
```
00             # value: 0 (varint)
```

Payload - End Positions (varint):
```
2A             # value: 42 (varint, "*" in GFA means unrestricted, encoded as max value)
```

Payload - Walks (walks type with orientation + numid):
```
07             # walks_lengths: [7] (varint)
01 02 03 02 01 02 03  # walks_segments: [1, 2, 3, 2, 1, 2, 3] (segment IDs as varint)
00             # walks_orientations: bits [0, 1, 0, 1, 0, 1, 0] = 0xAA (+,-,+,-,+,-,+)
```

**Total file size:** ~200 bytes

### Decoding notes

1. Segment IDs are assigned in order of appearance: S1=0, S2=1, S3=2 (0-based internal IDs)
2. In the links and paths payloads, IDs are stored as 1-based: S1=1, S2=2, S3=3. The reader converts back to 0-based by subtracting 1.
3. Link 1: from segment 0 (S1), orientation + (bit 0), to segment 1 (S2), orientation + (bit 0)
4. Link 2: from segment 1 (S2), orientation + (bit 0), to segment 2 (S3), orientation - (bit 1)
5. Path "path1": contains segments [S1+, S2-, S3+] with CIGAR "4M3M"
6. Walk "walk1": sample_id="0", haplotype_index=0, sequence_id="S3", start=0, end=42 (*), walk string="S1+S2-S3+S2-S1+S2-S3+"
7. Orientation bits are LSB-first: for walks_orientations, bit 0 = first segment (+), bit 1 = second segment (-), etc.
