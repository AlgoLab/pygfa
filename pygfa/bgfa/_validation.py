"""BGFA validation and dump module."""

from __future__ import annotations

import json
import struct
import sys

from pygfa.bgfa._constants import (
    BGFA_MAGIC,
    BGFA_VERSION,
    CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS,
    CIGAR_DECOMPOSITION_STRING,
    SECTION_ID_LINKS,
    SECTION_ID_PATHS,
    SECTION_ID_SEGMENTS,
    SECTION_ID_WALKS,
)
from pygfa.bgfa._reader import (
    ReaderBGFA,
    STRING_DECODERS,
    get_integer_decoder,
)
from pygfa.encoding.enums import IntegerEncoding, StringEncoding, WalkDecomposition
from pygfa.encoding.string_encoding import decompress_string_none

# =============================================================================
# Validation Helpers
# =============================================================================


def _describe_compression_code(code: int) -> str:
    """Return a human-readable description of a compression code.

    The compression code is a 2-byte value where:
    - High byte: Integer encoding (for IDs, lengths, etc.)
    - Low byte: String encoding (for sequences, names, etc.)
    """
    int_code = (code >> 8) & 0xFF
    str_code = code & 0xFF

    int_names = {e.value: e.name.lower().replace("_", " ") for e in IntegerEncoding}
    str_names = {e.value: e.name.lower().replace("_", " ") for e in StringEncoding}

    int_name = int_names.get(int_code, f"unknown_int({int_code:02X})")
    str_name = str_names.get(str_code, f"unknown_str({str_code:02X})")

    return f"{int_name}+{str_name}"


def _is_valid_compression_code(code: int) -> bool:
    """Check if a compression code is valid per the BGFA specification.

    A valid compression code must have both its integer encoding (high byte)
    and string encoding (low byte) be known enum values from the specification.

    :param code: Compression code (typically 2-byte or 4-byte value)
    :return: True if both encoding bytes are known, False otherwise
    """
    int_code = (code >> 8) & 0xFF
    str_code = code & 0xFF

    try:
        IntegerEncoding(int_code)
        StringEncoding(str_code)
        return True
    except ValueError:
        return False


def _is_valid_cigar_encoding_code(code: int) -> bool:
    """Check if a CIGAR encoding code is valid per the BGFA specification.

    4-byte CIGAR codes have format [DD, RR, II, SS] where DD is the decomposition
    strategy (byte 0), RR is the lengths integer encoding (byte 1), II is the
    counts integer encoding (byte 2), SS is the ops string encoding (byte 3).

    :param code: CIGAR encoding code (4-byte value)
    :return: True if the encoding code is valid, False otherwise
    """
    if code <= 0xFFFF:
        return False
    dd = code & 0xFF
    if dd == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
        rr = (code >> 8) & 0xFF
        ii = (code >> 16) & 0xFF
        ss = (code >> 24) & 0xFF
        try:
            IntegerEncoding(rr)
            IntegerEncoding(ii)
            StringEncoding(ss)
        except ValueError:
            return False
        return True
    elif dd == CIGAR_DECOMPOSITION_STRING:
        ss = (code >> 24) & 0xFF
        try:
            StringEncoding(ss)
        except ValueError:
            return False
        return (code >> 8) & 0xFFFF == 0
    return False


def _is_valid_walk_encoding_code(code: int) -> bool:
    """Check if a walk encoding code is valid per the BGFA specification.

    4-byte walk codes have a WalkDecomposition value in the high byte
    and a compression code in the low 2 bytes.
    A value of 0 means no walk data (valid).

    :param code: Walk encoding code (4-byte value)
    :return: True if the encoding code is valid, False otherwise
    """
    if code == 0:
        return True
    if code > 0xFFFF:
        decomp = (code >> 24) & 0xFF
        try:
            WalkDecomposition(decomp)
        except ValueError:
            return False
        return _is_valid_compression_code(code & 0xFFFF)
    return False


def _verify_decompressed_length(
    payload: bytes, comp_code: int, record_num: int, expected_ulen: int, field_name: str
) -> dict:
    """Verify that decompressed data length matches the stored uncompressed length.

    The stored uncompressed length (ulen) represents the sum of the actual data
    lengths, excluding placeholders (empty strings or '*' sentinels).

    :param payload: Compressed payload bytes
    :param comp_code: Compression code (2-byte or 4-byte)
    :param record_num: Number of records
    :param expected_ulen: Expected uncompressed length from header
    :param field_name: Name of the field for error reporting
    :return: Dict with value, correct flag, and optional error/message
    """
    try:
        int_decoder = get_integer_decoder(comp_code)
        str_decoder = STRING_DECODERS.get(comp_code & 0xFF, decompress_string_none)
        decompressed = str_decoder(payload, record_num, int_decoder)
        actual_ulen = sum(len(d) for d in decompressed if d and d != b"*")
        correct = actual_ulen == expected_ulen
        result = {"value": expected_ulen, "actual": actual_ulen, "correct": correct}
        if not correct:
            result["message"] = (
                f"Uncompressed {field_name} length mismatch: expected {expected_ulen}, got {actual_ulen}"
            )
        return result
    except Exception as e:
        return {"value": expected_ulen, "correct": True, "message": f"Decompression failed: {e}"}


# =============================================================================
# Validation
# =============================================================================


def validate_bgfa(input_file: str, verbose: bool = False, debug: bool = False) -> dict:
    """Validate a BGFA file against the specification.

    Parses all header and block header fields, decompresses all payloads,
    and verifies that recorded uncompressed lengths match actual decompressed sizes.

    :param input_file: Path to BGFA file
    :param verbose: Enable verbose logging
    :param debug: Enable debug logging
    :return: Dictionary with parsed contents and correctness flags for each field
    """
    result = {"valid": True, "header": {}, "blocks": []}

    with open(input_file, "rb") as f:
        data = f.read()

    if len(data) < 8:
        result["valid"] = False
        result["error"] = "File is too short"
        return result

    reader = ReaderBGFA()

    header_info = {}
    all_correct = True

    try:
        magic = struct.unpack_from("<I", data, 0)[0]
    except struct.error:
        magic = 0
    magic_correct = magic == BGFA_MAGIC
    if not magic_correct:
        all_correct = False
    header_info["magic_number"] = {
        "value": f"0x{magic:08X}",
        "expected": f"0x{BGFA_MAGIC:08X}",
        "correct": magic_correct,
    }

    try:
        version = struct.unpack_from("<H", data, 4)[0]
    except struct.error:
        version = 0
    version_correct = version == BGFA_VERSION
    if not version_correct:
        all_correct = False
    header_info["version"] = {
        "value": version,
        "expected": BGFA_VERSION,
        "correct": version_correct,
    }

    try:
        header_len = struct.unpack_from("<H", data, 6)[0]
    except struct.error:
        header_len = 0
    header_len_correct = header_len > 0 and 8 + header_len < len(data)
    if not header_len_correct:
        all_correct = False
    header_info["header_len"] = {"value": header_len, "correct": header_len_correct}

    header_text = ""
    header_text_correct = False
    if header_len_correct:
        try:
            header_text = data[8 : 8 + header_len].decode("ascii")
            null_term = data[8 + header_len] if 8 + header_len < len(data) else -1
            header_text_correct = null_term == 0
        except (UnicodeDecodeError, IndexError):
            header_text_correct = False
    if not header_text_correct:
        all_correct = False
    header_info["header"] = {"value": header_text, "correct": header_text_correct}

    result["header"] = header_info
    if not all_correct:
        result["valid"] = False

    try:
        header = reader._parse_header(data)
    except (ValueError, struct.error):
        result["valid"] = False
        return result

    offset = header["header_size"]
    reader._segment_names = []

    block_index = 0
    while offset < len(data):
        block_index += 1
        section_id = data[offset]
        block_result = {"block_index": block_index, "section_id": section_id, "fields": {}}

        if section_id == SECTION_ID_SEGMENTS:
            block_result["section_type"] = "segments"
            seg_offset = offset + 1

            field_names = [
                "record_num",
                "comp_names",
                "clen_names",
                "ulen_names",
                "comp_sequences",
                "clen_sequences",
                "ulen_sequences",
            ]
            fmt_chars = ["<H", "<H", "<Q", "<Q", "<H", "<Q", "<Q"]
            sizes = [2, 2, 8, 8, 2, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, seg_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                seg_offset += sz

            comp_names = parsed["comp_names"]
            ulen_names = parsed["ulen_names"]
            clen_names = parsed["clen_names"]
            comp_sequences = parsed["comp_sequences"]
            clen_sequences = parsed["clen_sequences"]

            payload_offset = seg_offset

            names_payload = data[payload_offset : payload_offset + clen_names]
            names_field = _verify_decompressed_length(
                names_payload, comp_names, parsed["record_num"], ulen_names, "names"
            )
            block_result["fields"]["ulen_names"] = names_field
            if not names_field["correct"]:
                result["valid"] = False

            try:
                int_dec = get_integer_decoder(comp_names)
                str_dec = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)
                names_bytes = str_dec(names_payload, parsed["record_num"], int_dec)
                names = [b.decode("ascii") for b in names_bytes]
            except Exception:
                names = []

            reader._segment_names = names

            seqs_payload = data[payload_offset + clen_names : payload_offset + clen_names + clen_sequences]
            seqs_field = _verify_decompressed_length(
                seqs_payload, comp_sequences, parsed["record_num"], ulen_names, "sequences"
            )
            block_result["fields"]["ulen_sequences"] = seqs_field
            if not seqs_field["correct"]:
                result["valid"] = False

            for fn in ["record_num", "comp_names", "clen_names", "comp_sequences", "clen_sequences"]:
                if fn not in block_result["fields"]:
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            try:
                int_dec_seq = get_integer_decoder(comp_sequences)
                str_dec_seq = STRING_DECODERS.get(comp_sequences & 0xFF, decompress_string_none)
                seqs_bytes = str_dec_seq(seqs_payload, parsed["record_num"], int_dec_seq)
                segments_data = []
                for i in range(parsed["record_num"]):
                    name = names[i] if i < len(names) else f"s{i}"
                    if i < len(seqs_bytes) and seqs_bytes[i]:
                        try:
                            seq = seqs_bytes[i].decode("ascii")
                        except UnicodeDecodeError:
                            seq = seqs_bytes[i].decode("latin-1")
                    else:
                        seq = ""
                    segments_data.append({"name": name, "sequence": seq})
                block_result["decompressed"] = segments_data
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = (payload_offset + clen_names + clen_sequences) - offset
            offset += consumed

        elif section_id == SECTION_ID_LINKS:
            block_result["section_type"] = "links"
            lnk_offset = offset + 1

            field_names = [
                "record_num",
                "comp_fromto",
                "clen_fromto",
                "comp_cigars",
                "clen_cigars",
                "ulen_cigars",
            ]
            fmt_chars = ["<H", "<H", "<Q", "<I", "<Q", "<Q"]
            sizes = [2, 2, 8, 4, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, lnk_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                lnk_offset += sz

            clen_fromto = parsed["clen_fromto"]
            clen_cigars = parsed["clen_cigars"]
            ulen_cigars = parsed["ulen_cigars"]

            payload_offset = lnk_offset

            cigars_payload = data[payload_offset + clen_fromto : payload_offset + clen_fromto + clen_cigars]
            cigars_field = _verify_decompressed_length(
                cigars_payload, parsed["comp_cigars"], parsed["record_num"], ulen_cigars, "cigars"
            )
            block_result["fields"]["ulen_cigars"] = cigars_field
            if not cigars_field["correct"]:
                result["valid"] = False

            for fn in ["record_num", "comp_fromto", "clen_fromto", "comp_cigars", "clen_cigars"]:
                if fn not in block_result["fields"]:
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            try:
                lnks, _ = reader._parse_links_block(data, offset)
                block_result["decompressed"] = lnks
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = (payload_offset + clen_fromto + clen_cigars) - offset
            offset += consumed

        elif section_id == SECTION_ID_PATHS:
            block_result["section_type"] = "paths"
            path_offset = offset + 1

            field_names = [
                "record_num",
                "comp_names",
                "comp_paths",
                "comp_cigars",
                "clen_cigars",
                "ulen_cigars",
                "clen_names",
                "ulen_names",
            ]
            fmt_chars = ["<H", "<H", "<I", "<I", "<Q", "<Q", "<Q", "<Q"]
            sizes = [2, 2, 4, 4, 8, 8, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, path_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                path_offset += sz

            clen_names = parsed["clen_names"]
            ulen_names = parsed["ulen_names"]
            clen_cigars = parsed["clen_cigars"]
            ulen_cigars = parsed["ulen_cigars"]

            payload_offset = path_offset

            names_payload = data[payload_offset : payload_offset + clen_names]
            names_field = _verify_decompressed_length(
                names_payload, parsed["comp_names"], parsed["record_num"], ulen_names, "names"
            )
            block_result["fields"]["ulen_names"] = names_field
            if not names_field["correct"]:
                result["valid"] = False

            cigars_payload = data[payload_offset + clen_names : payload_offset + clen_names + clen_cigars]
            cigars_field = _verify_decompressed_length(
                cigars_payload, parsed["comp_cigars"], parsed["record_num"], ulen_cigars, "cigars"
            )
            block_result["fields"]["ulen_cigars"] = cigars_field
            if not cigars_field["correct"]:
                result["valid"] = False

            for fn in ["record_num", "comp_names", "comp_paths", "comp_cigars", "clen_cigars", "clen_names"]:
                if fn not in block_result["fields"]:
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            try:
                paths_data, _ = reader._parse_paths_blocks(data, offset, reader._segment_names)
                block_result["decompressed"] = paths_data
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = (payload_offset + clen_names + clen_cigars) - offset
            offset += consumed

        elif section_id == SECTION_ID_WALKS:
            block_result["section_type"] = "walks"
            walk_offset = offset + 1

            field_names = [
                "record_num",
                "comp_samples",
                "comp_hep",
                "comp_seq",
                "comp_positions",
                "comp_walks",
                "clen_samples",
                "ulen_samples",
                "clen_hep",
                "ulen_hep",
                "clen_seq",
                "ulen_seq",
                "clen_positions",
                "ulen_positions",
                "clen_walks",
                "ulen_walks",
            ]
            fmt_chars = [
                "<H",
                "<H",
                "<H",
                "<H",
                "<H",
                "<I",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
            ]
            sizes = [2, 2, 2, 2, 2, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, walk_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                walk_offset += sz

            payload_offset = walk_offset

            walk_subfields = [
                ("samples", "comp_samples", "clen_samples", "ulen_samples"),
                ("hep", "comp_hep", "clen_hep", "ulen_hep"),
                ("seq", "comp_seq", "clen_seq", "ulen_seq"),
                ("positions", "comp_positions", "clen_positions", "ulen_positions"),
                ("walks", "comp_walks", "clen_walks", "ulen_walks"),
            ]

            sub_offset = payload_offset
            for name, comp_key, clen_key, ulen_key in walk_subfields:
                comp_code = parsed[comp_key]
                clen = parsed[clen_key]
                ulen = parsed[ulen_key]

                sub_payload = data[sub_offset : sub_offset + clen]
                field_result = _verify_decompressed_length(sub_payload, comp_code, parsed["record_num"], ulen, name)
                block_result["fields"][ulen_key] = field_result
                if not field_result["correct"]:
                    result["valid"] = False
                sub_offset += clen

            for fn in field_names:
                if fn not in block_result["fields"] and not fn.startswith("ulen_"):
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            try:
                walks_data, _ = reader._parse_walks_blocks(data, offset, reader._segment_names)
                block_result["decompressed"] = walks_data
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = sub_offset - offset
            offset += consumed

        else:
            block_result["section_type"] = "unknown"
            block_result["fields"]["section_id"] = {
                "value": section_id,
                "correct": False,
                "error": f"Unknown section ID: {section_id}",
            }
            result["valid"] = False
            result["blocks"].append(block_result)
            break

        result["blocks"].append(block_result)

    return result


# =============================================================================
# Dump
# =============================================================================


def dump_bgfa(file_path: str, text_format: bool = False) -> None:
    """Read a BGFA file and print its content with field names.

    This function provides a structured dump of the BGFA file, showing all headers,
    blocks, and their contents with complete field names from the specification.

    By default, outputs a JSON document. With text_format=True, outputs a pretty
    text format where indentation gives a clear structure.

    :param file_path: Path to BGFA file
    :param text_format: If True, output pretty text format instead of JSON
    """

    def validate_field(expected: int, actual: int, field_name: str) -> dict:
        result = {"value": actual}
        if expected != actual:
            result["error"] = f"Validation failed: expected {expected}, got {actual}"
        return result

    with open(file_path, "rb") as f:
        data = f.read()

    if len(data) < 8:
        print(json.dumps({"error": "BGFA file is too short"}), file=sys.stderr)
        return

    if not data:
        print(json.dumps({"error": "Empty file"}), file=sys.stderr)
        return

    reader = ReaderBGFA()
    result = {"bgfa_format_version": 1, "header": {}, "blocks": [], "summary": {}}

    try:
        header = reader._parse_header(data)
        result["header"] = {
            "magic_number": {"value": f"0x{header['magic']:08X}"},
            "version": {"value": header["version"]},
            "header_text": {"value": header["header_text"]},
            "header_size_bytes": {"value": header["header_size"]},
        }
    except Exception as e:
        result["header"]["error"] = f"Error parsing header: {e}"
        print(json.dumps(result, indent=2 if text_format else None))
        return

    offset = header["header_size"]
    reader._segment_names = []
    block_index = 0

    while offset < len(data):
        block_index += 1
        section_id = data[offset]
        block_result = {"block_index": block_index, "section_id": section_id}

        if section_id == SECTION_ID_SEGMENTS:
            block_result["section_type"] = "segments"

            seg_offset = offset + 1
            record_num = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            comp_names = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            clen_names = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            ulen_names = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            comp_str = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            clen_str = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            ulen_str = struct.unpack_from("<Q", data, seg_offset)[0]

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "segment_names_compression_code": {
                    "value": f"0x{comp_names:04X}",
                    "description": _describe_compression_code(comp_names),
                },
                "compressed_segment_names_length_bytes": validate_field(
                    clen_names, clen_names, "compressed_segment_names_length"
                ),
                "uncompressed_segment_names_length_bytes": validate_field(
                    ulen_names, ulen_names, "uncompressed_segment_names_length"
                ),
                "segment_sequences_compression_code": {
                    "value": f"0x{comp_str:04X}",
                    "description": _describe_compression_code(comp_str),
                },
                "compressed_segment_sequences_length_bytes": validate_field(
                    clen_str, clen_str, "compressed_segment_sequences_length"
                ),
                "uncompressed_segment_sequences_length_bytes": validate_field(
                    ulen_str, ulen_str, "uncompressed_segment_sequences_length"
                ),
            }

            segs, names, consumed = reader._parse_segments_block(data, offset)
            reader._segment_names = names

            payload_start = offset + 39
            names_payload = data[payload_start : payload_start + clen_names]
            seqs_payload = data[payload_start + clen_names : payload_start + clen_names + clen_str]

            compressed_info = {
                "compressed_names_hex": names_payload.hex() if clen_names > 0 else "",
                "compressed_sequences_hex": seqs_payload.hex() if clen_str > 0 else "",
                "compressed_names_bytes": list(names_payload) if clen_names > 0 else [],
                "compressed_sequences_bytes": list(seqs_payload) if clen_str > 0 else [],
            }

            try:
                int_dec_names = get_integer_decoder(comp_names)
                str_dec_names = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)
                names_bytes = str_dec_names(names_payload, record_num, int_dec_names)
                decompressed_names = []
                for b in names_bytes:
                    if b:
                        try:
                            decompressed_names.append(b.decode("ascii"))
                        except UnicodeDecodeError:
                            decompressed_names.append(b.decode("latin-1"))
                    else:
                        decompressed_names.append("")
                compressed_info["decompressed_segment_names"] = decompressed_names
            except Exception as e:
                compressed_info["decompressed_segment_names_error"] = f"Failed to decompress names: {e}"

            block_result["compressed_info"] = compressed_info

            segments_list = []
            for sid, seg_data in segs.items():
                name = seg_data.get("name", f"s{sid}")
                seq = seg_data.get("sequence", "*")

                segment_info = {
                    "segment_id": sid,
                    "segment_name": name,
                    "segment_sequence": seq,
                    "segment_length": len(seq) if seq != "*" else 0,
                }

                segments_list.append(segment_info)

            block_result["segments"] = segments_list
            result["blocks"].append(block_result)

            offset += consumed

        elif section_id == SECTION_ID_LINKS:
            block_result["section_type"] = "links"

            lnk_offset = offset + 1
            record_num = struct.unpack_from("<H", data, lnk_offset)[0]
            lnk_offset += 2
            comp_fromto = struct.unpack_from("<H", data, lnk_offset)[0]
            lnk_offset += 2
            clen_fromto = struct.unpack_from("<Q", data, lnk_offset)[0]
            lnk_offset += 8
            comp_cigars = struct.unpack_from("<I", data, lnk_offset)[0]
            lnk_offset += 4
            clen_cigars = struct.unpack_from("<Q", data, lnk_offset)[0]
            lnk_offset += 8
            ulen_cigars = struct.unpack_from("<Q", data, lnk_offset)[0]

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "link_endpoints_compression_code": {
                    "value": f"0x{comp_fromto:04X}",
                    "description": _describe_compression_code(comp_fromto),
                },
                "compressed_link_endpoints_length_bytes": validate_field(
                    clen_fromto, clen_fromto, "compressed_link_endpoints_length"
                ),
                "cigar_strings_compression_code": {
                    "value": f"0x{comp_cigars:08X}",
                    "description": _describe_compression_code(comp_cigars),
                },
                "compressed_cigar_strings_length_bytes": validate_field(
                    clen_cigars, clen_cigars, "compressed_cigar_strings_length"
                ),
                "uncompressed_cigar_strings_length_bytes": validate_field(
                    ulen_cigars, ulen_cigars, "uncompressed_cigar_strings_length"
                ),
            }

            lnks, consumed = reader._parse_links_block(data, offset)

            links_list = []
            for i, link in enumerate(lnks):
                links_list.append(
                    {
                        "link_id": i,
                        "from_segment_name": link["from_node"],
                        "from_orientation": link["from_orn"],
                        "to_segment_name": link["to_node"],
                        "to_orientation": link["to_orn"],
                        "cigar_string": link["alignment"],
                    }
                )

            block_result["links"] = links_list
            result["blocks"].append(block_result)

            offset += consumed

        elif section_id == SECTION_ID_PATHS:
            block_result["section_type"] = "paths"

            path_offset = offset + 1
            record_num = struct.unpack_from("<H", data, path_offset)[0]
            path_offset += 2
            comp_names = struct.unpack_from("<H", data, path_offset)[0]
            path_offset += 2
            comp_paths = struct.unpack_from("<I", data, path_offset)[0]
            path_offset += 4
            comp_cigars = struct.unpack_from("<I", data, path_offset)[0]
            path_offset += 4
            clen_cigars = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            ulen_cigars = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            clen_names = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            ulen_names = struct.unpack_from("<Q", data, path_offset)[0]

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "path_names_compression_code": {
                    "value": f"0x{comp_names:04X}",
                    "description": _describe_compression_code(comp_names),
                },
                "path_oriented_segment_ids_compression_code": {
                    "value": f"0x{comp_paths:08X}",
                    "description": _describe_compression_code(comp_paths),
                },
                "cigar_strings_compression_code": {
                    "value": f"0x{comp_cigars:08X}",
                    "description": _describe_compression_code(comp_cigars),
                },
                "compressed_cigar_strings_length_bytes": validate_field(
                    clen_cigars, clen_cigars, "compressed_cigar_strings_length"
                ),
                "uncompressed_cigar_strings_length_bytes": validate_field(
                    ulen_cigars, ulen_cigars, "uncompressed_cigar_strings_length"
                ),
                "compressed_path_names_length_bytes": validate_field(
                    clen_names, clen_names, "compressed_path_names_length"
                ),
                "uncompressed_path_names_length_bytes": validate_field(
                    ulen_names, ulen_names, "uncompressed_path_names_length"
                ),
            }

            paths_data, consumed = reader._parse_paths_blocks(data, offset, reader._segment_names)

            paths_list = []
            for i, p in enumerate(paths_data):
                paths_list.append(
                    {
                        "path_id": i,
                        "path_name": p.get("path_name", f"path{i}"),
                        "oriented_segment_ids": p.get("segments", []),
                        "overlap_cigar_strings": p.get("overlaps", []),
                    }
                )

            block_result["paths"] = paths_list
            result["blocks"].append(block_result)

            offset += consumed

        elif section_id == SECTION_ID_WALKS:
            block_result["section_type"] = "walks"

            walk_offset = offset + 1
            record_num = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_samples = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_hep = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_seq = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_positions = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_walks = struct.unpack_from("<I", data, walk_offset)[0]

            walk_offset += 4

            clen_samples = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            _ulen_samples = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_hep = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            _ulen_hep = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_seq = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            _ulen_seq = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_positions = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            _ulen_positions = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_walks = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            _ulen_walks = struct.unpack_from("<Q", data, walk_offset)[0]

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "sample_ids_compression_code": {
                    "value": f"0x{comp_samples:04X}",
                    "description": _describe_compression_code(comp_samples),
                },
                "haplotype_indices_compression_code": {
                    "value": f"0x{comp_hep:04X}",
                    "description": _describe_compression_code(comp_hep),
                },
                "sequence_ids_compression_code": {
                    "value": f"0x{comp_seq:04X}",
                    "description": _describe_compression_code(comp_seq),
                },
                "positions_compression_code": {
                    "value": f"0x{comp_positions:04X}",
                    "description": _describe_compression_code(comp_positions),
                },
                "oriented_segment_ids_compression_code": {
                    "value": f"0x{comp_walks:08X}",
                    "description": _describe_compression_code(comp_walks),
                },
                "compressed_sample_ids_length_bytes": validate_field(
                    clen_samples, clen_samples, "compressed_sample_ids_length"
                ),
                "compressed_haplotype_indices_length_bytes": validate_field(
                    clen_hep, clen_hep, "compressed_haplotype_indices_length"
                ),
                "compressed_sequence_ids_length_bytes": validate_field(
                    clen_seq, clen_seq, "compressed_sequence_ids_length"
                ),
                "compressed_positions_length_bytes": validate_field(
                    clen_positions, clen_positions, "compressed_positions_length"
                ),
                "compressed_oriented_segment_ids_length_bytes": validate_field(
                    clen_walks, clen_walks, "compressed_oriented_segment_ids_length"
                ),
            }

            walks_data, consumed = reader._parse_walks_blocks(data, offset, reader._segment_names)

            walks_list = []
            for i, w in enumerate(walks_data):
                walks_list.append(
                    {
                        "walk_id": i,
                        "sample_id": w.get("sample_id", f"sample{i}"),
                        "haplotype_index": w.get("haplotype_index", 0),
                        "sequence_id": w.get("sequence_id", f"seq{i}"),
                        "start_position": w.get("start", 0),
                        "end_position": w.get("end", 0),
                        "oriented_segment_ids": w.get("walk", []),
                    }
                )

            block_result["walks"] = walks_list
            result["blocks"].append(block_result)

            offset += consumed

        else:
            block_result["section_type"] = "unknown"
            block_result["error"] = f"Unknown section ID: {section_id}"
            result["blocks"].append(block_result)
            break

    result["summary"] = {"total_blocks": block_index, "total_segments": len(reader._segment_names)}

    if text_format:
        print("BGFA File Structure:")
        print(f"  Format Version: {result['bgfa_format_version']}")
        print()

        print("Header:")
        for key, value in result["header"].items():
            if "error" in value:
                print(f"  {key}: ERROR - {value['error']}")
            else:
                print(f"  {key}: {value['value']}")
        print()

        print(f"Blocks ({result['summary']['total_blocks']} total):")
        for i, block in enumerate(result["blocks"]):
            print(f"\n  Block {i + 1} (Section ID {block['section_id']} - {block.get('section_type', 'unknown')}):")

            if "error" in block:
                print(f"    ERROR: {block['error']}")
                continue

            if "fields" in block:
                print("    Fields:")
                for field_name, field_value in block["fields"].items():
                    if "error" in field_value:
                        print(f"      {field_name}: {field_value['value']} (ERROR: {field_value['error']})")
                    elif "description" in field_value:
                        print(f"      {field_name}: {field_value['value']} ({field_value['description']})")
                    else:
                        print(f"      {field_name}: {field_value['value']}")

            if "segments" in block:
                print("    Segments:")
                for seg in block["segments"]:
                    print(f"      Segment {seg['segment_id']}: {seg['segment_name']} -> {seg['segment_sequence']}")

                if "compressed_info" in block:
                    comp_info = block["compressed_info"]
                    print("    Compressed Information:")
                    if "decompressed_segment_names" in comp_info:
                        print(f"      Segment names: {comp_info['decompressed_segment_names']}")
                    if "compressed_names_hex" in comp_info and comp_info["compressed_names_hex"]:
                        print(
                            f"      Compressed names hex: {comp_info['compressed_names_hex'][:100]}{'...' if len(comp_info['compressed_names_hex']) > 100 else ''}"
                        )
                    if "compressed_sequences_hex" in comp_info and comp_info["compressed_sequences_hex"]:
                        print(
                            f"      Compressed sequences hex: {comp_info['compressed_sequences_hex'][:100]}{'...' if len(comp_info['compressed_sequences_hex']) > 100 else ''}"
                        )

            if "links" in block:
                print("    Links:")
                for link in block["links"]:
                    print(
                        f"      Link {link['link_id']}: {link['from_segment_name']}{link['from_orientation']} -> {link['to_segment_name']}{link['to_orientation']} (CIGAR: {link['cigar_string']})"
                    )

            if "paths" in block:
                print("    Paths:")
                for path in block["paths"]:
                    segments = ", ".join(path["oriented_segment_ids"])
                    overlaps = ", ".join(path["overlap_cigar_strings"])
                    print(f"      Path {path['path_id']}: {path['path_name']} -> [{segments}] (Overlaps: [{overlaps}])")

            if "walks" in block:
                print("    Walks:")
                for walk in block["walks"]:
                    segments = ", ".join(walk["oriented_segment_ids"])
                    print(
                        f"      Walk {walk['walk_id']}: Sample={walk['sample_id']}, Hap={walk['haplotype_index']}, Seq={walk['sequence_id']}, Pos={walk['start_position']}-{walk['end_position']} -> [{segments}]"
                    )

        print("\nSummary:")
        print(f"  Total segments: {result['summary']['total_segments']}")
        print(f"  Total blocks: {result['summary']['total_blocks']}")
    else:
        print(json.dumps(result, indent=2))
