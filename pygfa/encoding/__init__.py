from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint as compress_integer_list_varint,
    compress_integer_list_fixed as compress_integer_list_fixed,
    compress_integer_list_none as compress_integer_list_none,
    compress_integer_list_delta as compress_integer_list_delta,
    compress_integer_list_elias_gamma as compress_integer_list_elias_gamma,
    compress_integer_list_elias_omega as compress_integer_list_elias_omega,
    compress_integer_list_golomb as compress_integer_list_golomb,
    compress_integer_list_rice as compress_integer_list_rice,
    compress_integer_list_streamvbyte as compress_integer_list_streamvbyte,
    compress_integer_list_vbyte as compress_integer_list_vbyte,
)

from pygfa.encoding.string_encoding import (
    compress_string_zstd as compress_string_zstd,
    compress_string_gzip as compress_string_gzip,
    compress_string_lzma as compress_string_lzma,
    compress_string_none as compress_string_none,
    compress_string_list as compress_string_list,
    compress_string_list_frontcoding as compress_string_list_frontcoding,
    compress_string_list_delta as compress_string_list_delta,
    compress_string_list_dictionary as compress_string_list_dictionary,
    compress_string_list_huffman as compress_string_list_huffman,
)
