#!/usr/bin/env python3

import sys
import os

# Add the project root to the Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import tomllib
from pygfa.gfa import GFA


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    
    parser = argparse.ArgumentParser(description="Convert GFA file to BGFA format")
    parser.add_argument("input_file", help="Path to input GFA file")
    parser.add_argument("output_file", help="Path to output BGFA file")
    parser.add_argument(
        "--block-size",
        type=int,
        default=1024,
        help="Block size for BGFA format (default: 1024)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--config", "-c", type=str, help="Path to TOML configuration file"
    )

    # create the dictionary integers_encoding where the keys are all
    # possible functions to encode a list of integers, taken from gfa.py
    integers_encoding = {
        "varint": "compress_integer_list_varint",
        "fixed32": "compress_integer_list_fixed",
        "fixed64": "compress_integer_list_fixed",
        "delta": "compress_integer_list_delta",
        "gamma": "compress_integer_list_elias_gamma",
        "omega": "compress_integer_list_elias_omega",
        "golomb": "compress_integer_list_golomb",
        "rice": "compress_integer_list_rice",
        "streamvbyte": "compress_integer_list_streamvbyte",
        "vbyte": "compress_integer_list_vbyte",
        "": "compress_integer_list_none",
    }
    integers_encoding_str = (
        f" possible values: {'/'.join(integers_encoding.keys())[:-1]}"
    )
    # create the dictionary string_encoding where the keys are all
    # possible functions to encode a string, taken from gfa.py
    string_encoding = {
        "zstd": "compress_string_zstd",
        "gzip": "compress_string_gzip",
        "lzma": "compress_string_lzma",
        "frontcoding": "compress_string_list_frontcoding",
        "delta": "compress_string_list_delta",
        "dictionary": "compress_string_list_dictionary",
        "huffman": "compress_string_list_huffman",
        "": "compress_string_none",
    }
    string_encoding_str = f" possible values: {'/'.join(string_encoding.keys())[:-1]}"

    # Compression method options for each component
    parser.add_argument(
        "--segment-names-header",
        type=str,
        default="",
        help="Compression method for segment names header (default: '')"
        + string_encoding_str,
    )
    parser.add_argument(
        "--segment-names-payload-lengths",
        type=str,
        default="",
        help="Compression method for segment names payload lengths (default: '')",
    )
    parser.add_argument(
        "--segment-names-payload-names",
        type=str,
        default="",
        help="Compression method for segment names payload names (default: '')"
        + string_encoding_str,
    )
    parser.add_argument(
        "--segments-header",
        type=str,
        default="",
        help="Compression method for segments header (default: '')"
        + string_encoding_str,
    )
    parser.add_argument(
        "--segments-payload-lengths",
        type=str,
        default="",
        help="Compression method for segments payload lengths (default: '')",
    )
    parser.add_argument(
        "--segments-payload-strings",
        type=str,
        default="",
        help="Compression method for segments payload strings (default: '')"
        + string_encoding_str,
    )
    parser.add_argument(
        "--links-header",
        type=str,
        default="",
        help="Compression method for links header (default: '')",
    )
    parser.add_argument(
        "--links-payload-from",
        type=str,
        default="",
        help="Compression method for links payload from (default: '')",
    )
    parser.add_argument(
        "--links-payload-to",
        type=str,
        default="",
        help="Compression method for links payload to (default: '')",
    )
    parser.add_argument(
        "--links-payload-cigar-lengths",
        type=str,
        default="",
        help="Compression method for links payload cigar lengths (default: '')",
    )
    parser.add_argument(
        "--links-payload-cigar",
        type=str,
        default="",
        help="Compression method for links payload cigar (default: '')",
    )
    parser.add_argument(
        "--paths-header",
        type=str,
        default="",
        help="Compression method for paths header (default: '')",
    )
    parser.add_argument(
        "--paths-payload-names",
        type=str,
        default="",
        help="Compression method for paths payload names (default: '')",
    )
    parser.add_argument(
        "--paths-payload-segment-lengths",
        type=str,
        default="",
        help="Compression method for paths payload segment lengths (default: '')",
    )
    parser.add_argument(
        "--paths-payload-path-ids",
        type=str,
        default="",
        help=f"Compression method for paths payload path ids (default: ''), possible values: {'/'.join(string_encoding.keys())}",
    )
    parser.add_argument(
        "--paths-payload-cigar-lengths",
        type=str,
        default="",
        help="Compression method for paths payload cigar lengths (default: '')",
    )
    parser.add_argument(
        "--paths-payload-cigar",
        type=str,
        default="",
        help="Compression method for paths payload cigar (default: '')",
    )
    parser.add_argument(
        "--walks-header",
        type=str,
        default="",
        help="Compression method for walks header (default: '')",
    )
    parser.add_argument(
        "--walks-payload-sample-ids",
        type=str,
        default="",
        help="Compression method for walks payload sample ids (default: '')",
    )
    parser.add_argument(
        "--walks-payload-hep-indices",
        type=str,
        default="",
        help="Compression method for walks payload hep indices (default: '')",
    )
    parser.add_argument(
        "--walks-payload-sequence-ids",
        type=str,
        default="",
        help="Compression method for walks payload sequence ids (default: '')",
    )
    parser.add_argument(
        "--walks-payload-start",
        type=str,
        default="",
        help="Compression method for walks payload start (default: '')",
    )
    parser.add_argument(
        "--walks-payload-end",
        type=str,
        default="",
        help="Compression method for walks payload end (default: '')",
    )
    parser.add_argument(
        "--walks-payload-walks",
        type=str,
        default="",
        help="Compression method for walks payload walks (default: '')",
    )

    args = parser.parse_args(args)

    # Load configuration from TOML file if provided
    config = {}
    if args.config:
        if not os.path.exists(args.config):
            print(
                f"Error: Configuration file '{args.config}' not found", file=sys.stderr
            )
            sys.exit(1)

        try:
            with open(args.config, "rb") as f:
                config = tomllib.load(f)
        except ValueError as e:
            print(
                f"Error: Invalid TOML format in '{args.config}': {e}", file=sys.stderr
            )
            sys.exit(1)
        except Exception as e:
            print(
                f"Error: Failed to read configuration file '{args.config}': {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Merge command line arguments with configuration file values
    # Command line arguments take precedence over configuration file values
    block_size = config.get("block_size", args.block_size)
    verbose = config.get("verbose", args.verbose)

    # Get compression methods from config or use defaults
    compression_methods = {
        "segment_names_header": config.get(
            "segment_names_header", args.segment_names_header
        ),
        "segment_names_payload_lengths": config.get(
            "segment_names_payload_lengths", args.segment_names_payload_lengths
        ),
        "segment_names_payload_names": config.get(
            "segment_names_payload_names", args.segment_names_payload_names
        ),
        "segments_header": config.get("segments_header", args.segments_header),
        "segments_payload_lengths": config.get(
            "segments_payload_lengths", args.segments_payload_lengths
        ),
        "segments_payload_strings": config.get(
            "segments_payload_strings", args.segments_payload_strings
        ),
        "links_header": config.get("links_header", args.links_header),
        "links_payload_from": config.get("links_payload_from", args.links_payload_from),
        "links_payload_to": config.get("links_payload_to", args.links_payload_to),
        "links_payload_cigar_lengths": config.get(
            "links_payload_cigar_lengths", args.links_payload_cigar_lengths
        ),
        "links_payload_cigar": config.get(
            "links_payload_cigar", args.links_payload_cigar
        ),
        "paths_header": config.get("paths_header", args.paths_header),
        "paths_payload_names": config.get(
            "paths_payload_names", args.paths_payload_names
        ),
        "paths_payload_segment_lengths": config.get(
            "paths_payload_segment_lengths", args.paths_payload_segment_lengths
        ),
        "paths_payload_path_ids": config.get(
            "paths_payload_path_ids", args.paths_payload_path_ids
        ),
        "paths_payload_cigar_lengths": config.get(
            "paths_payload_cigar_lengths", args.paths_payload_cigar_lengths
        ),
        "paths_payload_cigar": config.get(
            "paths_payload_cigar", args.paths_payload_cigar
        ),
        "walks_header": config.get("walks_header", args.walks_header),
        "walks_payload_sample_ids": config.get(
            "walks_payload_sample_ids", args.walks_payload_sample_ids
        ),
        "walks_payload_hep_indices": config.get(
            "walks_payload_hep_indices", args.walks_payload_hep_indices
        ),
        "walks_payload_sequence_ids": config.get(
            "walks_payload_sequence_ids", args.walks_payload_sequence_ids
        ),
        "walks_payload_start": config.get(
            "walks_payload_start", args.walks_payload_start
        ),
        "walks_payload_end": config.get("walks_payload_end", args.walks_payload_end),
        "walks_payload_walks": config.get(
            "walks_payload_walks", args.walks_payload_walks
        ),
    }

    # Validate compression methods
    for component, method in compression_methods.items():
        if method and method not in integers_encoding and method not in string_encoding:
            print(
                f"Error: Invalid compression method '{method}' for {component}. "
                f"Valid methods are: {list(integers_encoding.keys()) + list(string_encoding.keys())}",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        # Read GFA file
        g = GFA.from_gfa(args.input_file)

        # Build compression options dictionary
        compression_options = {
            "block_size": block_size,
        }
        # Add all compression methods to the options
        for key, value in compression_methods.items():
            compression_options[key] = value

        # Write BGFA file
        g.to_bgfa(args.output_file, block_size, compression_options)

        if verbose:
            print(f"Successfully converted {args.input_file} to {args.output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
