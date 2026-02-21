from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_delta as compress_integer_list_delta,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_elias_gamma as compress_integer_list_elias_gamma,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_elias_omega as compress_integer_list_elias_omega,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_fixed as compress_integer_list_fixed,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_golomb as compress_integer_list_golomb,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_none as compress_integer_list_none,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_rice as compress_integer_list_rice,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_streamvbyte as compress_integer_list_streamvbyte,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint as compress_integer_list_varint,
)
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_vbyte as compress_integer_list_vbyte,
)
from pygfa.encoding.string_encoding import (
    compress_string_gzip as compress_string_gzip,
)
from pygfa.encoding.string_encoding import (
    compress_string_list as compress_string_list,
)
from pygfa.encoding.string_encoding import (
    compress_string_list_delta as compress_string_list_delta,
)
from pygfa.encoding.string_encoding import (
    compress_string_list_dictionary as compress_string_list_dictionary,
)
from pygfa.encoding.string_encoding import (
    compress_string_list_frontcoding as compress_string_list_frontcoding,
)
from pygfa.encoding.string_encoding import (
    compress_string_list_huffman as compress_string_list_huffman,
)
from pygfa.encoding.string_encoding import (
    compress_string_lzma as compress_string_lzma,
)
from pygfa.encoding.string_encoding import (
    compress_string_none as compress_string_none,
)
from pygfa.encoding.string_encoding import (
    compress_string_zstd as compress_string_zstd,
)
from pygfa.encoding.string_encoding import (
    compress_string_zstd_dict as compress_string_zstd_dict,
)
from pygfa.encoding.string_encoding import (
    decompress_string_zstd_dict as decompress_string_zstd_dict,
)
from pygfa.encoding.arithmetic_coding import (
    compress_string_arithmetic as compress_string_arithmetic,
)
from pygfa.encoding.arithmetic_coding import (
    compress_string_bwt_huffman as compress_string_bwt_huffman,
)
from pygfa.encoding.arithmetic_coding import (
    decompress_string_arithmetic as decompress_string_arithmetic,
)
from pygfa.encoding.arithmetic_coding import (
    decompress_string_bwt_huffman as decompress_string_bwt_huffman,
)
from pygfa.encoding.dna_encoding import (
    compress_string_2bit_dna as compress_string_2bit_dna,
)
from pygfa.encoding.dna_encoding import (
    compress_string_list_2bit_dna as compress_string_list_2bit_dna,
)
from pygfa.encoding.dna_encoding import (
    decompress_string_2bit_dna as decompress_string_2bit_dna,
)
from pygfa.encoding.rle_encoding import (
    compress_string_rle as compress_string_rle,
)
from pygfa.encoding.rle_encoding import (
    compress_string_list_rle as compress_string_list_rle,
)
from pygfa.encoding.rle_encoding import (
    decompress_string_rle as decompress_string_rle,
)
from pygfa.encoding.cigar_encoding import (
    compress_string_cigar as compress_string_cigar,
)
from pygfa.encoding.cigar_encoding import (
    compress_string_list_cigar as compress_string_list_cigar,
)
from pygfa.encoding.cigar_encoding import (
    decompress_string_cigar as decompress_string_cigar,
)
from pygfa.encoding.dictionary_encoding import (
    compress_string_dictionary as compress_string_dictionary,
)
from pygfa.encoding.dictionary_encoding import (
    compress_string_list_dictionary_wrapper as compress_string_list_dictionary_wrapper,
)
from pygfa.encoding.dictionary_encoding import (
    decompress_string_dictionary as decompress_string_dictionary,
)
from pygfa.encoding.enums import (
    IntegerEncoding as IntegerEncoding,
    StringEncoding as StringEncoding,
    WalkDecomposition as WalkDecomposition,
    CigarDecomposition as CigarDecomposition,
    SpecialEncoding as SpecialEncoding,
    make_compression_code as make_compression_code,
    split_compression_code as split_compression_code,
)
from pygfa.encoding.zstd_dict import (
    train_dictionary as train_dictionary,
    save_dictionary as save_dictionary,
    load_dictionary as load_dictionary,
    compress_with_dict as compress_with_dict,
    decompress_with_dict as decompress_with_dict,
)
from pygfa.encoding.lz4_codec import (
    compress_string_lz4 as compress_string_lz4,
    decompress_string_lz4 as decompress_string_lz4,
)
from pygfa.encoding.brotli_codec import (
    compress_string_brotli as compress_string_brotli,
    decompress_string_brotli as decompress_string_brotli,
)
from pygfa.encoding.bit_packing import (
    compress_integer_list_bitpacking as compress_integer_list_bitpacking,
    decompress_integer_list_bitpacking as decompress_integer_list_bitpacking,
)
from pygfa.encoding.heuristic import (
    select_integer_encoding as select_integer_encoding,
    select_string_encoding as select_string_encoding,
    select_encoding as select_encoding,
)
from pygfa.encoding.pfor_delta import (
    compress_integer_list_pfor_delta as compress_integer_list_pfor_delta,
    decompress_integer_list_pfor_delta as decompress_integer_list_pfor_delta,
)
from pygfa.encoding.simple8b import (
    compress_integer_list_simple8b as compress_integer_list_simple8b,
    decompress_integer_list_simple8b as decompress_integer_list_simple8b,
)
from pygfa.encoding.group_varint import (
    compress_integer_list_group_varint as compress_integer_list_group_varint,
    decompress_integer_list_group_varint as decompress_integer_list_group_varint,
)
from pygfa.encoding.fibonacci_coding import (
    compress_integer_list_fibonacci as compress_integer_list_fibonacci,
    decompress_integer_list_fibonacci as decompress_integer_list_fibonacci,
)
from pygfa.encoding.exp_golomb import (
    compress_integer_list_exp_golomb as compress_integer_list_exp_golomb,
    decompress_integer_list_exp_golomb as decompress_integer_list_exp_golomb,
)
from pygfa.encoding.byte_packed import (
    compress_integer_list_byte_packed as compress_integer_list_byte_packed,
    decompress_integer_list_byte_packed as decompress_integer_list_byte_packed,
)
from pygfa.encoding.masked_vbyte import (
    compress_integer_list_masked_vbyte as compress_integer_list_masked_vbyte,
    decompress_integer_list_masked_vbyte as decompress_integer_list_masked_vbyte,
)
from pygfa.encoding.ppm_coding import (
    compress_string_ppm as compress_string_ppm,
    compress_string_list_ppm as compress_string_list_ppm,
)
