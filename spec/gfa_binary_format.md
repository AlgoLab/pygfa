# Binary GFA format

## Binary GFA file: overall structure

We divide the file into the following parts. 
The first part is the file header, which contains some metadata.
All other parts are a list of blocks.

*  File Header
*  List of Segment Names Blocks
*  List of Segments Blocks
*  List of Links Blocks
*  List of Paths Blocks

Each list of blocks is the concatenation of the blocks, without any separator.
Each block has a header and a payload.

The `uint16` and `uint64` types are written as little endian.

## Conventions

A C string is an ASCII string terminated by `\0`

### File Header Section

| Field        | Description                                                  | Type       |
|--------------|--------------------------------------------------------------|------------|
| `version`    | Format version                                               | `uint16`   |
| `block_size` | number of objects stored in each block, default value = 1024 | `uint16`   |
| `S_len`      | Number of Segments                                           | `uint64`   |
| `L_len`      | Number of Links                                              | `uint64`   |
| `P_len`      | Number of Paths                                              | `uint64`   |
| `W_len`      | Number of Walks                                              | `uint64`   |
| `header`     | gfa header text                                              | `C string` |


### Segment Names Block

Each block consists of a header and a payload.
Since there are `S_len` segments, there will be exactly `ceiling(S_len /
block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field             | Description                                  | Type     |
|-------------------|----------------------------------------------|----------|
| record_num        | number of record in the block < = block_size | `uint16` |
| compression_names | Encoding strategy for the names              | `uint16` |
| compressed_len    | length of compressed names field             | `uint64` |
| uncompressed_len  | length of uncompressed names field           | `uint64` |

#### Payload

| Field | Description   | Type      |
|-------|---------------|-----------|
| names | Segment names | `strings` |
|       |               |           |

We associate an internal segment ID to each name, where the segment ID is an
incrementing integer starting at 0.

### Segments Block

Each block consists of a header and a payload.
Since there are `S_len` segments, there will be exactly `ceiling(S_len /
block_size)` blocks.
Only the last block can have fewer than `block_size` objects.


#### Header

| Field            | Description                                    | Type     |
|------------------|------------------------------------------------|----------|
| record_num       | number of record in the block < = block_size   | `uint16` |
| compression_str  | Encoding strategy for the segment sequences    | `uint16` |
| compressed_len   | length of compressed segment_sequences field   | `uint64` |
| uncompressed_len | length of uncompressed segment_sequences field | `uint64` |

#### Payload

| Field    | Description | Type      |
|----------|-------------|-----------|
| segments | Segments    | `strings` |

Description of each uncompressed segment sequence format

### Links Block

Each block consists of a header and a payload.
Since there are `L_len` links, there will be exactly `ceiling(L_len /
block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field              | Description                                  | Type     |
|--------------------|----------------------------------------------|----------|
| record_num         | number of record in the block <= block_size  | `uint16` |
| compression_fromto | Encoding strategy for the from and to fields | `uint16` |
| compression_cigars | Encoding strategy for the cigar strings      | `uint16` |
| compressed_len     | length of compressed concatenated cigars     | `uint64` |
| uncompressed_len   | length of uncompressed concatenated cigars   | `uint64` |

#### Payload

| Field            | Description                                       | Type            |
|------------------|---------------------------------------------------|-----------------|
| from             | Tail segment of the links                         | `uints`         |
| to               | Head segment of the  link                         | `uints`         |
| from_orientation | orientations of all from segments. 0 is +, 1 is - | `bits`          |
| to_orientation   | orientations of all from segments. 0 is +, 1 is - | `bits`          |
| cigar_strings    | CIGAR strings                                     | `cigar strings` |


### Paths Block

Each block consists of a header and a payload.
Since there are `P_len` segments, there will be exactly `ceiling(P_len /
block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                  | Description                                             | Type     |
|------------------------|---------------------------------------------------------|----------|
| record_num             | number of record in the block <= block_size             | `uint16` |
| compression_path_names | Encoding strategy for the path names                    | `uint16` |
| compression_paths      | Encoding strategy for the paths as list of segments ids | `uint16` |
| compression_cigars     | Encoding strategy for the cigar strings                 | `uint16` |
| compressed_len_cigar   | length of compressed concatenated cigars                | `uint64` |
| uncompressed_len_cigar | length of uncompressed concatenated cigars              | `uint64` |
| compressed_len_name    | length of compressed concatenated path_name             | `uint64` |
| uncompressed_len_name  | length of uncompressed concatenated path_name           | `uint64` |

#### Payload

| Field         | Description                                            | Type            |
|---------------|--------------------------------------------------------|-----------------|
| path_names    | path names                                             | `strings`       |
| paths         | Paths, each path is a sequence of oriented segment IDs | `walks`         |
| cigar_strings | The list of CIGAR strings                              | `cigar strings` |


### Walk Block

Each block consists of a header and a payload.
Since there are `W_len` segments, there will be exactly `ceiling(W_len /
block_size)` blocks.
Only the last block can have fewer than `block_size` objects.

#### Header

| Field                 | Description                                       | Type     |
|-----------------------|---------------------------------------------------|----------|
| record_num            | number of record in the block <= block_size       | `uint16` |
| compression_samples   | Encoding strategy for the sample IDs              | `uint16` |
| compression_hep       | Encoding strategy for the haplotype indices       | `uint16` |
| compression_sequence  | Encoding strategy for the sequence IDs            | `uint16` |
| compression_positions | Encoding strategy for the start and end positions | `uint16` |
| compression_walks     | Encoding strategy for the walks                   | `uint16` |
| compressed_len_sam    | length of compressed concatenated sample_id       | `uint64` |
| uncompressed_len_sam  | length of uncompressed concatenated sample_id     | `uint64` |
| compressed_len_seq    | length of compressed concatenated seq_id          | `uint64` |
| uncompressed_len_nseq | length of uncompressed concatenated seq_id        | `uint64` |
| compressed_len_walk   | length of compressed concatenated walks           | `uint64` |
| uncompressed_len_walk | length of uncompressed concatenated walks         | `uint64` |

#### Payload

| Field           | Description                                            | Type      |
|-----------------|--------------------------------------------------------|-----------|
| samples         | sample IDs                                             | `strings` |
| hep_indices     | Haplotype indices                                      | `uints`   |
| sequence_id     | sequence IDs                                           | `strings` |
| start_positions | optional start positions                               | `uints`   |
| end_positions   | optional end positions                                 | `uints`   |
| walks           | Walks, each walk is a sequence of oriented segment IDs | `walks`   |

## Encoding strategies

The code of each strategy consists of two bytes. Except for some special case,
the first byte encodes the strategy for a sequence of uints and the second byte
the strategy for a string.
For example the code 0x0102 is used for the method 0x01 for the lengths and the
method 0x02 for the strings.
We use question marks `??` to represent that all values of the byte can be used.

| Code   | Strategy       | Type    |
|--------|----------------|---------|
| 0x00?? | Identity       | `uints` |
| 0x??00 | Identity       | string  |
| 0x01?? | varint         | `uints` |
| 0x02?? | fixed16        | `uints` |
| 0x03?? | delta          | `uints` |
| 0x04?? | elias gamma    | `uints` |
| 0x05?? | elias omega    | `uints` |
| 0x06?? | golomb         | `uints` |
| 0x07?? | rice           | `uints` |
| 0x08?? | streamvbyte    | `uints` |
| 0x09?? | vbyte          | `uints` |
| 0x0A?? | fixed32        | `uints` |
| 0x0B?? | fixed64        | `uints` |
| 0x??01 | zstd           | string  |
| 0x??02 | gzip           | string  |
| 0x??03 | lzma           | string  |
| 0x??04 | Huffman        | string  |
| 0x??05 | 2-bit DNA      | string  |
| 0x??06 | Arithmetic     | string  |
| 0x??07 | BWT+Huffman    | string  |
| 0x??08 | RLE            | string  |
| 0x??09 | CIGAR-specific | string  |
| 0x??0A | Dictionary     | string  |
  
### Encoding strings

The first byte determines how we encode the list of lengths of the strings, the
second byte how we encode the concatenation of the strings.

Therefore `0x0102` implies that we use the varint method to encode the lengths
and the gzip method to encode the concatenation of the string.

#### Arithmetic Coding (0x??06)

Arithmetic coding uses an adaptive model that updates symbol frequencies as it encodes. The format is:
- uint32: original data length
- bytes: encoded bitstream

The encoder starts with a uniform distribution (all symbols have frequency 1) and adapts as it processes each byte. This provides good compression for sequences with non-uniform symbol distributions.

#### BWT + Huffman Coding (0x??07)

BWT (Burrows-Wheeler Transform) + Huffman coding provides excellent compression for repetitive sequences like DNA. The pipeline is:
1. Apply Burrows-Wheeler Transform in configurable blocks (default 64KB)
2. Apply Move-to-Front transform
3. Encode with Huffman coding

The block size can be configured via the `bwt_block_size` option in compression_options.

The format is:
- uint32: number of BWT blocks
- For each block:
  - uint32: primary index
  - uint32: block size
  - bytes: BWT data

#### 2-bit DNA Encoding (0x??05)

2-bit DNA encoding provides optimal compression for DNA/RNA sequences by encoding each nucleotide in 2 bits instead of 8 bits (75% size reduction). This is the most impactful encoding for pangenome data where sequences typically comprise 70-80% of file content.

**Nucleotide Mapping:**
- A (or a) = 00
- C (or c) = 01
- G (or g) = 10
- T (or t) = 11
- U (or u) = 11 (RNA uracil treated as thymine)

**Format:**
- 1 byte: flags
  - bit 0: has_exceptions (1 if exception table present)
  - bits 1-7: reserved
- packed_bases: 4 nucleotides per byte (2 bits each)
- If has_exceptions flag is set:
  - varint: exception count
  - varint list: exception positions
  - bytes: exception characters (one byte per exception)

**Exception Handling:**
Ambiguity codes (N, R, Y, K, M, S, W, B, D, H, V, -) and unknown characters are stored in the exception table with their original ASCII values, allowing perfect reconstruction while maintaining compression on standard ACGT sequences.

**Expected Compression:** 75% reduction on pure DNA/RNA sequences, slightly less with ambiguity codes.

**Primary Use Case:** Segment sequences, which are typically the largest data component in BGFA files.

#### Run-Length Encoding - RLE (0x??08)

Run-Length Encoding efficiently compresses sequences with repeated characters (homopolymers in DNA, repeated operations in other contexts). The implementation uses a hybrid mode that switches between raw and RLE encoding to prevent expansion on non-repetitive data.

**Format:**
- varint: segment count
- For each segment:
  - 1 byte: mode (0x00=raw, 0x01=RLE)
  - varint: segment data length
  - segment data:
    - If raw mode: raw bytes
    - If RLE mode: sequence of [char:1 byte][count:varint] pairs

**Algorithm:**
- Minimum run length: 3 characters (shorter runs use raw encoding)
- Automatically switches between raw and RLE modes within a string
- Run counts encoded as varint for efficiency

**Expected Compression:** 30-50% reduction on sequences with homopolymers or repetitive patterns.

**Primary Use Cases:**
- DNA sequences with homopolymer runs (AAAAAAA, GGGGGG, TTTTTT)
- Can be combined with 2-bit DNA encoding for additional compression
- General string data with repeated characters

#### Dictionary Encoding (0x??0A)

Dictionary encoding is optimized for repetitive string data by replacing repeated strings with short references to a dictionary. In the BGFA framework, the single-string encoder uses identity mode for compatibility, while the list-based encoder provides full dictionary compression.

**Single-String Mode (BGFA Framework):**
For compatibility with the BGFA block-based encoding where strings are processed individually, this mode uses identity encoding (no transformation).

**List Mode (Standalone Use):**
The full dictionary implementation (`compress_string_list_dictionary` in `pygfa/encoding/string_encoding.py`) provides:
- Dictionary construction from unique strings
- Frequency-based optimization
- Varint-encoded string references
- Maximum dictionary size: 65536 entries (configurable)

**Format (List Mode):**
- uint32: dictionary size
- varint list: dictionary offsets
- bytes: concatenated dictionary entries
- varint list: indices into dictionary for each string

**Expected Compression:** 60-90% reduction on highly repetitive data (e.g., sample IDs repeated across thousands of walks).

**Primary Use Cases:**
- Sample identifiers in walk blocks
- Segment names with common prefixes
- Path names with structural patterns
- Any string list with high repetition

### Expected Impact on File Sizes

The new encoding methods provide substantial compression improvements for typical pangenome data:

| Encoding | Target Data | Typical % of File | Expected Reduction | Overall Impact |
|----------|-------------|-------------------|-------------------|----------------|
| 2-bit DNA | Sequences | 70-80% | 75% | **50-60%** |
| RLE | Homopolymers | Variable | 30-50% | 10-15% |
| CIGAR-specific | Alignments | 5-10% | 40-60% | 2-5% |
| Dictionary | Sample IDs | 5-10% | 60-90% | 3-7% |

**Estimated Total File Size Reduction: 60-75%** for typical pangenome GFA files.

**Encoding Combinations:**
Encodings can be stacked for additional compression. For example:
- Segment sequences: 2-bit DNA + RLE (encode as 2-bit first, then apply RLE to packed data)
- Mixed approach: Different blocks can use different encodings based on data characteristics


### CIGAR-Specific Encoding (0x??09)

CIGAR (Compact Idiosyncratic Gapped Alignment Report) strings represent sequence alignments with alternating numbers and operation letters. This encoding exploits the structure of CIGAR strings to achieve better compression than general-purpose methods.

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
- varint: number of operations
- packed operations: 2 operations per byte (4 bits each)
  - High nibble: operation n
  - Low nibble: operation n+1
  - If odd number of operations, low nibble of last byte = 0xF (padding marker)
- varint list: operation lengths

**Example:**
CIGAR string "10M2I5D" is encoded as:
- num_ops: 3
- packed_ops: 0x01, 0x2F (operations M, I, D with padding)
- lengths: 10, 2, 5

**Expected Compression:** 40-60% reduction compared to ASCII CIGAR strings.

**Primary Use Cases:**
- Link overlaps (L lines in GFA)
- Path CIGAR strings (P lines in GFA)
- Any alignment representation using CIGAR format

### Encoding CIGAR strings

In this case we use 4 bytes to encode the strategy used. The first byte
represents how we decompose the CIGAR strings, the other bytes how we encode
each component.

| Code       | Strategy                         |
|------------|----------------------------------|
| 0x00?????? | Identity                         |
| 0x01?????? | numOperations+lengths+operations |
| 0x02?????? | string                           |
|            |                                  |

### Bits

a `bits` field is considered a list of `uint64`.

#### numOperations+lengths+operations
We encode three components:

1.  the list of the number of operations in the CIGAR strings (`uints`)
2.  the list of lengths of the operations (`uints`)
3.  The operations (a string)

Therefore `0x01020304` implies that we use the varint method to encode the list
of numbers of operations, the fixed16 method to encode the lengths, and the lzma
method to encode the concatenation of strings.

#### string

We compress the CIGAR strings separated by newlines with the method specified in
the second byte.
Therefore `0x02030000` implies that we use the lzma method.

### Walks and paths

In this case we use 4 bytes to encode the strategy used. The first byte
represents how we decompose the walk (or the path), the other bytes how we encode
each component.

| Code       | Strategy          |
|------------|-------------------|
| 0x00?????? | Identity          |
| 0x01?????? | orientation+strid |
| 0x02?????? | orientation+numid |
|            |                   |

#### orientation+strid
We encode two components:

1.  the list of orientations in binary form (0 corresponds to > or +, while 1
    corresponds to < or -) 
2.  the list of segment IDs seen as strings
