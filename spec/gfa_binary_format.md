# Binary GFA format

## Binary GFA file: overall structure

We divide the file into the following parts.
The first part is the file header, which contains some metadata.
All other parts are a list of blocks.

*  File Header
*  List of Blocks (segment names, segments, links, paths, walks)

Each block contains a `section_id` field that identifies its type, allowing blocks
to appear in any order in the file. The writer maintains the original ordering.

Each block has a header and a payload.
The payloads begin with all integer metadata required for the strategy, followed by the compressed data blob.

**Block ordering constraints:**
- Blocks of the same `section_id` might be contiguous, but that is not required.
- Different section types can appear in any order relative to each other.

The `uint16`, `uint32`, and `uint64` types are written as little endian.

All bytes data and all data that are encoded with a variable number of bits are packed into bytes. Any remaining bits in
the final byte of the bitstream are set to 0 (when writing) and MUST be ignored (when reading).

## Conventions

A C string is an ASCII string terminated by `\0`.

When we refer to `uints` as a type, it means a list of unsigned integers encoded according to the specified integer encoding strategy.

When we refer to `strings` as a type, it means a list of strings encoded according to the string encoding strategy (see "Strings Encoding strategies" section).

When we refer to `bits` as a type, see the "Bits" section for the packing format.

### File Header Section

| Field          | Description                          | Type       |
|----------------|--------------------------------------|------------|
| `magic_number` | Magic number for bgfa files = "AFGB" (0x42474641) | `uint32`   |
| `version`      | Format version                       | `uint16`   |
| `header_len`   | length of the header string (excluding null terminator) | `uint16`   |
| `header`       | GFA header text                      | `bytes` + null terminator |

**Clarification:** The header is stored as `header_len` bytes of ASCII text followed by a single null terminator byte (`\0`). The `header_len` field specifies the length of the text portion only. Total bytes consumed = 8 (magic + version + header_len) + header_len + 1 (null terminator).


The file header does not store `block_size`. The reader must know the block size
separately (e.g., via configuration or default value of 1024).

### Segment Names Block

Each block consists of a header and a payload.
Since there are `S_len` segments, there will be exactly `ceiling(S_len / block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                    | Description                                          | Type     |
|--------------------------|------------------------------------------------------|----------|
| `section_id`             | Section type (1 = segment names)                     | `uint8`  |
| `record_num`             | number of records in the block <= block_size         | `uint16` |
| `compression_names`      | Encoding strategy for the names (2 bytes)            | `uint16` |
| `compressed_names_len`   | length of compressed names field                     | `uint64` |
| `uncompressed_names_len` | sum of the lengths of the uncompressed segment names | `uint64` |

#### Payload

| Field   | Description   | Type      |
|---------|---------------|-----------|
| `names` | Segment names | `strings` |

We associate an internal segment ID to each name, where the segment ID is an
incrementing integer starting at 0. Segment IDs are assigned in the order names appear in the file.

### Segments Block

Each block consists of a header and a payload.
Since there are `S_len` segments, there will be exactly `ceiling(S_len / block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                  | Description                                                 | Type     |
|------------------------|-------------------------------------------------------------|----------|
| `section_id`           | Section type (2 = segments)                                 | `uint8`  |
| `record_num`           | number of records in the block <= block_size                | `uint16` |
| `compression_str`      | Encoding strategy for the segment sequences (2 bytes)       | `uint16` |
| `compressed_str_len`   | length of compressed segment_sequences field                | `uint64` |
| `uncompressed_str_len` | sum of the lengths of uncompressed segment_sequences fields | `uint64` |

#### Payload

| Field      | Description | Type      |
|------------|-------------|-----------|
| `segment_ids` | Internal segment IDs (0-based) | `uints` |
| `sequences` | Segment sequences | `strings` |

**Layout:** The payload consists of encoded segment IDs followed by encoded sequences. Both use the same `compression_str` strategy code, but the integer encoding portion applies to `segment_ids` and the string encoding portion applies to `sequences`.

### Links Block

Each block consists of a header and a payload.
Since there are `L_len` links, there will be exactly `ceiling(L_len / block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                     | Description                                            | Type     |
|---------------------------|--------------------------------------------------------|----------|
| `section_id`              | Section type (3 = links)                               | `uint8`  |
| `record_num`              | number of records in the block <= block_size           | `uint16` |
| `compression_fromto`      | Encoding strategy for the from and to fields (2 bytes) | `uint16` |
| `compressed_fromto_len`   | length of compressed from and to fields                | `uint64` |
| `compression_cigars`      | Encoding strategy for the cigar strings (2 bytes)      | `uint16` |
| `compressed_cigars_len`   | length of compressed concatenated cigars               | `uint64` |
| `uncompressed_cigars_len` | sum of the lengths of uncompressed concatenated cigars | `uint64` |

#### Payload

| Field              | Description                                       | Type            |
|--------------------|---------------------------------------------------|-----------------|
| `from_ids`         | Tail segment IDs (0-based)                        | `uints`         |
| `to_ids`           | Head segment IDs (0-based)                        | `uints`         |
| `from_orientation` | Orientations of all from segments. 0 is +, 1 is - | `bits`          |
| `to_orientation`   | Orientations of all to segments. 0 is +, 1 is -   | `bits`          |
| `cigar_strings`    | CIGAR strings                                     | `strings`       |

**Layout:** The `fromto` payload is structured as: `[from_ids encoded][to_ids encoded][from_orientation bits][to_orientation bits]`.

Orientation bits are stored with a least significant bit (LSB-first) strategy within each `uint64` word. See the "Bits" section for details.

### Paths Block

Each block consists of a header and a payload.
Since there are `P_len` paths, there will be exactly `ceiling(P_len / block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                         | Description                                                       | Type     |
|-------------------------------|-------------------------------------------------------------------|----------|
| `section_id`                  | Section type (4 = paths)                                          | `uint8`  |
| `record_num`                  | number of records in the block <= block_size                      | `uint16` |
| `compression_path_names`      | Encoding strategy for the path names (2 bytes)                    | `uint16` |
| `compressed_path_names_len`   | length of compressed concatenated path names                      | `uint64` |
| `uncompressed_path_names_len` | length of uncompressed concatenated path names                    | `uint64` |
| `compression_paths`           | Encoding strategy for the paths as list of segment IDs (4 bytes)  | `uint32` |
| `compressed_paths_len`        | length of compressed paths                                        | `uint64` |
| `uncompressed_paths_len`      | sum of the lengths of uncompressed paths (as segment ID strings)  | `uint64` |
| `compression_cigars`          | Encoding strategy for the cigar strings (2 bytes)                 | `uint16` |
| `compressed_len_cigar`        | length of compressed concatenated cigars                          | `uint64` |
| `uncompressed_len_cigar`      | sum of the lengths of uncompressed concatenated cigars strings    | `uint64` |

#### Payload

| Field           | Description                                            | Type            |
|-----------------|--------------------------------------------------------|-----------------|
| `path_names`    | Path names                                             | `strings`       |
| `paths`         | Paths, each path is a sequence of oriented segment IDs | `walks`         |
| `cigar_strings` | The list of CIGAR strings                              | `strings`       |

### Walks Block

Each block consists of a header and a payload.
Since there are `W_len` walks, there will be exactly `ceiling(W_len / block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                       | Description                                               | Type     |
|-----------------------------|-----------------------------------------------------------|----------|
| `section_id`                | Section type (5 = walks)                                  | `uint8`  |
| `record_num`                | number of records in the block <= block_size              | `uint16` |
| `compression_samples`       | Encoding strategy for the sample IDs (2 bytes)            | `uint16` |
| `compressed_samples_len`    | length of compressed concatenated sample_id               | `uint64` |
| `uncompressed_samples_len`  | sum of the lengths of uncompressed concatenated sample_id | `uint64` |
| `compression_hep`           | Encoding strategy for the haplotype indices (2 bytes)     | `uint16` |
| `compressed_hep_len`        | length of compressed haplotype indices                    | `uint64` |
| `uncompressed_hep_len`      | sum of the lengths of uncompressed haplotype indices      | `uint64` |
| `compression_sequence`      | Encoding strategy for the sequence IDs (2 bytes)          | `uint16` |
| `compressed_sequence_len`   | length of compressed sequence IDs                         | `uint64` |
| `uncompressed_sequence_len` | sum of the lengths of uncompressed sequence IDs           | `uint64` |
| `compression_positions`     | Encoding strategy for the start and end positions (2 bytes) | `uint16` |
| `compressed_positions_len`  | length of compressed start and end positions              | `uint64` |
| `uncompressed_positions_len`| sum of the lengths of uncompressed positions              | `uint64` |
| `compression_walks`         | Encoding strategy for the walks (4 bytes)                 | `uint32` |
| `compressed_walk_len`       | length of compressed concatenated walks                   | `uint64` |
| `uncompressed_walk_len`     | sum of the lengths of uncompressed concatenated walks     | `uint64` |

#### Payload

| Field             | Description                                            | Type      |
|-------------------|--------------------------------------------------------|-----------|
| `samples`         | Sample IDs                                             | `strings` |
| `hep_indices`     | Haplotype indices                                      | `uints`   |
| `sequence_id`     | Sequence IDs                                           | `strings` |
| `start_positions` | Optional start positions                               | `uints`   |
| `end_positions`   | Optional end positions                                 | `uints`   |
| `walks`           | Walks, each walk is a sequence of oriented segment IDs | `walks`   |

**Layout:** Positions are stored as `[all_start_positions][all_end_positions]`.

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
| `0x??0B` | Concatenation + ZSTD Dict   | `string` |
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

### Payload for encoded `strings`

The payload of the encoded `strings` consists of:

1.  **Metadata**: A list of numbers, encoded according to the first-byte strategy (varint, fixed16, etc).
    - For **Concatenation**: This list contains the lengths of each string.
    - For **Superstring**: This list contains first all start positions, then all end positions of the strings.
    
    The first-byte strategy determines how this list of numbers is encoded. For superstring encoding, start and end positions are encoded independently using the same strategy.

2.  **Blob**: The superstring or the concatenated string, encoded according to the second-byte strategy.

The `compressed_len` field in block headers is the total number of bytes needed to store the encoded strings, that is: metadata bytes + blob bytes.

The `uncompressed_len` field is the sum of the lengths of the original strings (before any encoding).

## Bits

A `bits` field represents a list of bits packed into `uint64` words in little-endian format.

**Packing strategy:**
- Bits are packed LSB-first within each `uint64` word
- Bit at index `i` is stored at position `i % 64` within word `i / 64`
- The number of `uint64` words is `ceil(n / 64)` where `n` is the number of bits
- Unused bits in the final word (if any) are set to 0 when writing and MUST be ignored when reading

**Example:** For orientations `[1, 0, 1, 1, 0, ...]` (64 bits):
- Word 0 = `0b...01101` (bit 0 = 1, bit 1 = 0, bit 2 = 1, bit 3 = 1, bit 4 = 0, ...)

## Arithmetic Coding (0x??06)

**Format:**
- `uint32`: frequency table size
- `bytes`: frequency table (symbol:count pairs)
- `bytes`: arithmetic encoded data

The frequency table contains pairs of `(symbol: 1 byte, frequency: uint32)` for each symbol in the alphabet.

## Huffman Coding (0x??04, 0x??F4)

The Huffman encoding of a string (be it the concatenation or a superstring) consists of:

| Name              | Description            | Type    |
|-------------------|------------------------|---------|
| `codebook_len`    | Length of the codebook | `uint32` |
| `codebook`        | Huffman codebook       | `bytes` |
| `huffman_encoded` | The encoded string     | `bits`  |

The codebook is a list of 16 integers encoded using the first-byte strategy (from the string encoding code).
Each integer $L_i$ is the bit-length of the code for nibble value $i$.

### Nibble-Level Processing

1. **Symbol Extraction**: Each byte of the target string (the concatenated string or the superstring) is treated as two 4-bit symbols:
   - Symbol A: High nibble (bits 4–7)
   - Symbol B: Low nibble (bits 0–3)

2. **Encoding Order**: For every byte, Symbol A is encoded first, followed immediately by Symbol B.

3. **Alphabet Size**: The codebook always contains 16 entries (representing nibbles 0x0 through 0xF). A bit-length of 0 indicates the nibble is not present.

### Canonical Code Construction

The decoder MUST reconstruct the Huffman codes from the 16 lengths using canonical rules:

1. Symbols are sorted primarily by bit-length (ascending) and secondarily by symbol value (ascending).
2. The first code is all 0s for the first non-zero bit-length.
3. For subsequent codes: `current_code = (prev_code + 1) << (current_len - prev_len)`.

The byte-length of the `huffman_encoded` data is the total `compressed_len` of the field minus the bytes consumed by the
string metadata, the 4-byte `codebook_len`, and the encoded codebook itself.

The decoder MUST decode exactly `2 * L` symbols, where `L` is the number of characters in the string being reconstructed.

## BWT + Huffman encoding (0x??07)

Burrows-Wheeler Transform + Huffman coding provides excellent compression for repetitive sequences like DNA. The pipeline is:

1. Apply Burrows-Wheeler Transform in configurable blocks (default 64KB)
2. Apply Move-to-Front transform
3. Encode with Huffman coding

The block size can be configured via the `bwt_block_size` option in compression_options.

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
- Packed: `0b00011011` `0b00xxxxxx` = 0x1B 0x00 (2 bytes, last 6 bits are padding)

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
- `varint`: segment count (number of runs)
- For each segment:
  - 1 byte: mode (0x00=raw, 0x01=RLE)
  - `varint`: segment data length
  - segment data:
    - If raw mode: raw bytes
    - If RLE mode: sequence of `[char: 1 byte][count: varint]` pairs

**Algorithm:**
- Minimum run length: 3 characters (shorter runs use raw encoding)
- Automatically switches between raw and RLE modes within a string
- Run counts encoded as varint for efficiency

**Expected Compression:** 30-50% reduction on sequences with homopolymers or repetitive patterns.

**Primary Use Cases:**
- DNA sequences with homopolymer runs (AAAAAAA, GGGGGG, TTTTTT)
- Can be combined with 2-bit DNA encoding for additional compression
- General string data with repeated characters

## Dictionary Encoding (0x??0A)

Dictionary encoding is optimized for repetitive string data by replacing repeated strings with short references to a dictionary.

**Format (Concatenation mode):**
- `uint32`: dictionary size (number of unique strings)
- `varint` list: dictionary entry offsets (cumulative offsets into dictionary blob)
- `bytes`: concatenated dictionary entries (each entry is a unique string, no terminators)
- `varint` list: indices into dictionary for each input string

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

| Code         | Strategy                         |
|--------------|----------------------------------|
| `0x00??????` | none (identity)                  |
| `0x01??????` | numOperations + lengths + operations |
| `0x02??????` | string (treat as plain string)   |

### numOperations + lengths + operations (0x01??????)

We encode three components:

1. The list of the number of operations in each CIGAR string (`uints`) - encoded with strategy in byte 2
2. The list of lengths of the operations (`uints`) - encoded with strategy in byte 3
3. The operations as a packed string - encoded with strategy in byte 4

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

| Code         | Strategy          |
|--------------|-------------------|
| `0x00??????` | none (identity)   |
| `0x01??????` | orientation + strid |
| `0x02??????` | orientation + numid |

### orientation + strid (0x01??????)

We encode two components:

1. The list of orientations in binary form (0 corresponds to `>` or `+`, 1 corresponds to `<` or `-`) - encoded as `bits`
2. The list of segment IDs encoded as strings - encoded with strategy specified in bytes 2-4

**Format:**
- Byte 1 (0x01): Use orientation + strid decomposition
- Byte 2: Integer encoding for orientation bit count (typically 0x00 for none)
- Bytes 3-4: String encoding strategy for segment IDs (e.g., 0x0100 for varint lengths + none)

### orientation + numid (0x02??????)

We encode two components:

1. The list of orientations in binary form (0 corresponds to `>` or `+`, 1 corresponds to `<` or `-`) - encoded as `bits`
2. The list of segment IDs as integers - encoded with strategy specified in bytes 2-4

**Format:**
- Byte 1 (0x02): Use orientation + numid decomposition
- Byte 2: Integer encoding for orientation bit count (typically 0x00 for none)
- Bytes 3-4: Integer encoding strategy for segment IDs (e.g., 0x0100 for varint)

**Layout:** `[orientation_bits][segment_ids_encoded]`
