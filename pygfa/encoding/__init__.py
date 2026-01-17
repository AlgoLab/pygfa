from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint as compress_integer_list_varint,
    compress_integer_list_fixed as compress_integer_list_fixed,
    compress_integer_list_none as compress_integer_list_none,
)

from pygfa.encoding.string_encoding import (
    compress_string_zstd as compress_string_zstd,
    compress_string_gzip as compress_string_gzip,
    compress_string_lzma as compress_string_lzma,
    compress_string_none as compress_string_none,
    compress_string_list as compress_string_list,
)
