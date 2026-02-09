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
| from             | Tail segment of the links                         | `uint64`        |
| to               | Head segment of the  link                         | `uint64`        |
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

| Field                 | Description                                   | Type     |
|-----------------------|-----------------------------------------------|----------|
| record_num            | number of record in the block <= block_size   | `uint16` |
| compressed_len_sam    | length of compressed concatenated sample_id   | `uint64` |
| uncompressed_len_sam  | length of uncompressed concatenated sample_id | `uint64` |
| compressed_len_seq    | length of compressed concatenated seq_id      | `uint64` |
| uncompressed_len_nseq | length of uncompressed concatenated seq_id    | `uint64` |
| compressed_len_walk   | length of compressed concatenated walks       | `uint64` |
| uncompressed_len_walk | length of uncompressed concatenated walks     | `uint64` |

#### Payload

| Field           | Description                                            | Type      |
|-----------------|--------------------------------------------------------|-----------|
| samples         | sample IDs                                             | `strings` |
| hep_indices     | Haplotype indices                                      | uint      |
| sequence_id     | sequence IDs                                           | `strings` |
| start_positions | optional start positions                               | uint      |
| end_positions   | optional end positions                                 | uint      |
| walks           | Walks, each walk is a sequence of oriented segment IDs | `walks`   |

## Encoding strategies

The code of each strategy consists of two bytes. Except for some special case,
the first byte encodes the strategy for a sequence of uints and the second byte
the strategy for a string.
For example the code 0x0102 is used for the method 0x01 for the lengths and the
method 0x02 for the strings.
We use question marks `??` to represent that all values of the byte can be used.

| Code   | Strategy    | Type             |
|--------|-------------|------------------|
| 0x00?? | Identity    | list of integers |
| 0x??00 | Identity    | string           |
| 0x01?? | varint      | list of integers |
| 0x02?? | fixed16     | list of integers |
| 0x03?? | delta       | list of integers |
| 0x04?? | elias gamma | list of integers |
| 0x05?? | elias omega | list of integers |
| 0x06?? | golomb      | list of integers |
| 0x07?? | rice        | list of integers |
| 0x08?? | streamvbyte | list of integers |
| 0x09?? | vbyte       | list of integers |
| 0x0A?? | fixed32     | list of integers |
| 0x0B?? | fixed64     | list of integers |
| 0x??01 | zstd        | string           |
| 0x??02 | gzip        | string           |
| 0x??03 | lzma        | string           |
| 0x??04 | Huffman     | string           |
  
### Encoding a list of strings

The first byte determines how we encode the list of lengths of the strings, the
second byte how we encode the concatenation of the strings.

Therefore `0x0102` implies that we use the varint method to encode the lengths
and the gzip method to encode the concatenation of the string.

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

1.  the list of the number of operations in the CIGAR strings (a list of integers)
2.  the list of lengths of the operations (a list of integers)
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

#### orientation+numid
We encode two components:

1.  the list of orientations in binary form (0 corresponds to > or +, while 1
    corresponds to < or -) 
2.  the list of segment IDs seen as numbers
