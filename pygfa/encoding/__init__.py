# ruff: noqa: F401 - All imports are intentional re-exports
from pygfa.encoding.integer_list_encoding import (
    compress_integer_list_delta,
    compress_integer_list_elias_gamma,
    compress_integer_list_elias_omega,
    compress_integer_list_fixed,
    compress_integer_list_golomb,
    compress_integer_list_none,
    compress_integer_list_rice,
    compress_integer_list_streamvbyte,
    compress_integer_list_varint,
    compress_integer_list_vbyte,
)
from pygfa.encoding.string_encoding import (
    compress_string_gzip,
    compress_string_list,
    compress_string_list_delta,
    compress_string_list_dictionary,
    compress_string_list_frontcoding,
    compress_string_list_huffman,
    compress_string_list_superstring_2bit,
    compress_string_list_superstring_huffman,
    compress_string_list_superstring_none,
    compress_string_list_superstring_ppm,
    compress_string_lzma,
    compress_string_none,
    compress_string_zstd,
    compress_string_zstd_dict,
    decompress_string_zstd_dict,
)
from pygfa.encoding.arithmetic_coding import (
    compress_string_arithmetic,
    compress_string_bwt_huffman,
    decompress_string_arithmetic,
    decompress_string_bwt_huffman,
)
from pygfa.encoding.dna_encoding import (
    compress_string_2bit_dna,
    compress_string_list_2bit_dna,
    decompress_string_2bit_dna,
)
from pygfa.encoding.rle_encoding import (
    compress_string_rle,
    compress_string_list_rle,
    decompress_string_rle,
)
from pygfa.encoding.cigar_encoding import (
    compress_string_cigar,
    compress_string_list_cigar,
    decompress_string_cigar,
)
from pygfa.encoding.dictionary_encoding import (
    compress_string_dictionary,
    compress_string_list_dictionary_wrapper,
    decompress_string_dictionary,
)
from pygfa.encoding.enums import (
    CigarDecomposition,
    IntegerEncoding,
    SpecialEncoding,
    StringEncoding,
    WalkDecomposition,
    make_compression_code,
    split_compression_code,
)
from pygfa.encoding.zstd_dict import (
    compress_with_dict,
    decompress_with_dict,
    load_dictionary,
    save_dictionary,
    train_dictionary,
)
from pygfa.encoding.lz4_codec import (
    compress_string_lz4,
    decompress_string_lz4,
)
from pygfa.encoding.brotli_codec import (
    compress_string_brotli,
    decompress_string_brotli,
)
from pygfa.encoding.bit_packing import (
    compress_integer_list_bitpacking,
    decompress_integer_list_bitpacking,
)
from pygfa.encoding.heuristic import (
    select_encoding,
    select_integer_encoding,
    select_string_encoding,
)
from pygfa.encoding.pfor_delta import (
    compress_integer_list_pfor_delta,
    decompress_integer_list_pfor_delta,
)
from pygfa.encoding.simple8b import (
    compress_integer_list_simple8b,
    decompress_integer_list_simple8b,
)
from pygfa.encoding.group_varint import (
    compress_integer_list_group_varint,
    decompress_integer_list_group_varint,
)
from pygfa.encoding.fibonacci_coding import (
    compress_integer_list_fibonacci,
    decompress_integer_list_fibonacci,
)
from pygfa.encoding.exp_golomb import (
    compress_integer_list_exp_golomb,
    decompress_integer_list_exp_golomb,
)
from pygfa.encoding.byte_packed import (
    compress_integer_list_byte_packed,
    decompress_integer_list_byte_packed,
)
from pygfa.encoding.masked_vbyte import (
    compress_integer_list_masked_vbyte,
    decompress_integer_list_masked_vbyte,
)
from pygfa.encoding.ppm_coding import (
    compress_string_list_ppm,
    compress_string_ppm,
)

COMPRESSION_OPTIONS: dict[str, str] = {
    "compression_segment_names": "2byte",
    "compression_str": "2byte",
    "compression_from": "1byte_int",
    "compression_to": "1byte_int",
    "compression_cigars": "4byte_cigar",
    "compression_path_names": "2byte",
    "compression_paths": "4byte_walks",
    "compression_sample_ids": "2byte",
    "compression_hep": "2byte",
    "compression_sequence": "1byte_str",
    "compression_positions_start": "1byte_int",
    "compression_positions_end": "1byte_int",
    "compression_walks": "4byte_walks",
}

INTEGER_ENCODING_NAMES: list[str] = [e.name.lower() for e in IntegerEncoding]
STRING_ENCODING_NAMES: list[str] = [e.name.lower() for e in StringEncoding]

INTEGER_ENCODINGS: dict[str, str] = {
    "none": "compress_integer_list_none",
    "varint": "compress_integer_list_varint",
    "fixed16": "compress_integer_list_fixed",
    "fixed32": "compress_integer_list_fixed",
    "fixed64": "compress_integer_list_fixed",
    "delta": "compress_integer_list_delta",
    "gamma": "compress_integer_list_elias_gamma",
    "omega": "compress_integer_list_elias_omega",
    "golomb": "compress_integer_list_golomb",
    "rice": "compress_integer_list_rice",
    "streamvbyte": "compress_integer_list_streamvbyte",
    "vbyte": "compress_integer_list_vbyte",
    "pfor_delta": "compress_integer_list_pfor_delta",
    "simple8b": "compress_integer_list_simple8b",
    "group_varint": "compress_integer_list_group_varint",
    "bit_packing": "compress_integer_list_bitpacking",
    "fibonacci": "compress_integer_list_fibonacci",
    "exp_golomb": "compress_integer_list_exp_golomb",
    "byte_packed": "compress_integer_list_byte_packed",
    "masked_vbyte": "compress_integer_list_masked_vbyte",
    "": "compress_integer_list_none",
}

STRING_ENCODINGS: dict[str, str] = {
    "none": "compress_string_none",
    "zstd": "compress_string_zstd",
    "zstd_dict": "compress_string_zstd_dict",
    "gzip": "compress_string_gzip",
    "lzma": "compress_string_lzma",
    "lz4": "compress_string_lz4",
    "brotli": "compress_string_brotli",
    "huffman": "compress_string_list_huffman",
    "frontcoding": "compress_string_list_frontcoding",
    "delta": "compress_string_list_delta",
    "dictionary": "compress_string_list_dictionary",
    "rle": "compress_string_rle",
    "cigar": "compress_string_cigar",
    "2bit": "compress_string_2bit_dna",
    "arithmetic": "compress_string_arithmetic",
    "bwt_huffman": "compress_string_bwt_huffman",
    "ppm": "compress_string_ppm",
    "superstring_none": "compress_string_list_superstring_none",
    "superstring_huffman": "compress_string_list_superstring_huffman",
    "superstring_2bit": "compress_string_list_superstring_2bit",
    "superstring_ppm": "compress_string_list_superstring_ppm",
    "": "compress_string_none",
}


def show_full_encodings() -> dict[str, list[str]]:
    """Return a dict mapping each compression option to all possible encoding values.

    Option names match the compression fields in the BGFA specification.
    For 2-byte fields, values are ``int_enc+str_enc`` combinations.
    For 4-byte CIGAR fields, values are ``decomp+int1+int2+str`` combinations.
    For 4-byte walks/paths fields, values are ``decomp+int+str`` combinations.
    For 1-byte integer-only fields, values are integer encoding names.
    For 1-byte string-only fields, values are string encoding names.
    """
    int_names = sorted(
        n for n in INTEGER_ENCODING_NAMES if n
    )
    str_names = sorted(
        n for n in STRING_ENCODING_NAMES if n
    )

    result: dict[str, list[str]] = {}
    for option, field_type in COMPRESSION_OPTIONS.items():
        if field_type == "2byte":
            result[option] = sorted(
                f"{ie}+{se}" for ie in int_names for se in str_names
            )
        elif field_type == "1byte_int":
            result[option] = list(int_names)
        elif field_type == "1byte_str":
            result[option] = list(str_names)
        elif field_type == "4byte_cigar":
            decomp_names = ["none", "numops_lengths_ops", "string"]
            result[option] = sorted(
                f"{d}+{ie1}+{ie2}+{se}"
                for d in decomp_names
                for ie1 in int_names
                for ie2 in int_names
                for se in str_names
            )
        elif field_type == "4byte_walks":
            decomp_names = ["none", "orientation_strid", "orientation_numid"]
            result[option] = sorted(
                f"{d}+{ie}+{se}"
                for d in decomp_names
                for ie in int_names
                for se in str_names
            )
    return result
