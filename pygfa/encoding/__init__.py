from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_varint,
    compress_integer_list_fixed,
    compress_integer_list_none,
)

from pygfa.encoding.string_encoding import (
    compress_string_zstd,
    compress_string_gzip,
    compress_string_lzma,
    compress_string_none,
    compress_string_list,
)
