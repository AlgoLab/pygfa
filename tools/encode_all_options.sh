#!/usr/bin/env bash
# Encode a GFA file with all possible compression options, saving BGFA files.
#
# For each (option, encoding) pair from show_full_encodings(), generates a BGFA
# file where only that option uses the given encoding — all others default to
# "none".  Mirrors the single-parameter sweep in the Snakemake benchmark.
#
# Usage:
#   pixi run bash tools/encode_all_options.sh data/example_3.gfa
#   pixi run bash tools/encode_all_options.sh data/example_3.gfa -o my_bgfa_files
#   pixi run bash tools/encode_all_options.sh data/example_3.gfa --include-cigar
#   pixi run bash tools/encode_all_options.sh data/example_3.gfa --option compression_sequences
#   pixi run bash tools/encode_all_options.sh data/example_3.gfa --dry-run

set -euo pipefail

# --- Defaults ---
OUTPUT_DIR="encoding_output"
BLOCK_SIZE=1024
INCLUDE_CIGAR=0
DRY_RUN=0
SINGLE_OPTION=""
GFA_FILE=""
VERBOSE=0

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output-dir)
            OUTPUT_DIR="$2"; shift 2 ;;
        --block-size)
            BLOCK_SIZE="$2"; shift 2 ;;
        --include-cigar)
            INCLUDE_CIGAR=1; shift ;;
        --option)
            SINGLE_OPTION="$2"; shift 2 ;;
        --dry-run)
            DRY_RUN=1; shift ;;
        -v|--verbose)
            VERBOSE=1; shift ;;
        -h|--help)
            sed -n '2,/^$/{s/^# //p; s/^#//p}' "$0"
            exit 0 ;;
        -*)
            echo "Unknown flag: $1" >&2; exit 1 ;;
        *)
            if [[ -z "$GFA_FILE" ]]; then
                GFA_FILE="$1"
            else
                echo "Unexpected argument: $1" >&2; exit 1
            fi
            shift ;;
    esac
done

if [[ -z "$GFA_FILE" ]]; then
    echo "Error: GFA file required." >&2
    echo "Usage: $0 <gfa_file> [-o output_dir] [--dry-run] [--include-cigar] [--option OPT]" >&2
    exit 1
fi

if [[ ! -f "$GFA_FILE" ]]; then
    echo "Error: file not found: $GFA_FILE" >&2
    exit 1
fi

# --- Option → CLI flag mapping (mirrors workflow/Snakefile OPTION_CLI_MAP) ---
declare -A OPTION_TO_FLAG=(
    ["compression_segment_names"]="--compression-segment-names"
    ["compression_sequences"]="--compression-sequences"
    ["compression_from"]="--compression-link-endpoints"
    ["compression_to"]="--compression-link-endpoints"
    ["compression_cigars"]="--compression-link-cigars"
    ["compression_path_names"]="--compression-path-names"
    ["compression_paths"]="--compression-path-sequences"
    ["compression_sample_ids"]="--compression-walk-sample-ids"
    ["compression_haplotype_indices"]="--compression-walk-haplotype-indices"
    ["compression_sequence_ids"]="--compression-walk-sequence-ids"
    ["compression_positions_start"]="--compression-walk-positions-start"
    ["compression_positions_end"]="--compression-walk-positions-end"
    ["compression_walks"]="--compression-walk-steps"
)

# All distinct CLI flags (only one per shared flag)
ALL_FLAGS=(
    "--compression-segment-names"
    "--compression-sequences"
    "--compression-link-endpoints"
    "--compression-link-cigars"
    "--compression-path-names"
    "--compression-path-sequences"
    "--compression-walk-sample-ids"
    "--compression-walk-haplotype-indices"
    "--compression-walk-sequence-ids"
    "--compression-walk-positions-start"
    "--compression-walk-positions-end"
    "--compression-walk-steps"
)

# --- Get encodings JSON ---
ENCODINGS_JSON=$(pixi run python bin/bgfatools show-full-encodings 2>/dev/null)
if [[ -z "$ENCODINGS_JSON" ]]; then
    echo "Error: failed to get encodings from bgfatools show-full-encodings" >&2
    exit 1
fi

# --- Use Python to extract (option, encoding) pairs ---
# Output format: option<TAB>encoding (one per line).
# JSON is piped via stdin to avoid ARG_MAX limits.
emit_pairs() {
    echo "$1" | python3 -c "
import json, sys

data = json.load(sys.stdin)
single = sys.argv[1]
include_cigar = sys.argv[2] == '1'

for option, encodings in sorted(data.items()):
    if single and option != single:
        continue
    if 'cigar' in option and not include_cigar:
        continue
    for enc in encodings:
        print(f'{option}\t{enc}')
" "$SINGLE_OPTION" "$INCLUDE_CIGAR"
}

# --- Count and preview ---
mapfile -t PAIRS < <(emit_pairs "$ENCODINGS_JSON")
TOTAL=${#PAIRS[@]}
echo "Total BGFA files to generate: $TOTAL"

if [[ "$DRY_RUN" -eq 1 ]]; then
    CURRENT_OPT=""
    COUNT=0
    for pair in "${PAIRS[@]}"; do
        IFS=$'\t' read -r opt enc <<< "$pair"
        if [[ "$opt" != "$CURRENT_OPT" ]]; then
            echo ""
            echo "[$opt]"
            CURRENT_OPT="$opt"
            COUNT=0
        fi
        safe="${enc//\//_}"
        safe="${safe//\+/_}"
        echo "  ${OUTPUT_DIR}/${opt}/${safe}.bgfa"
        COUNT=$((COUNT + 1))
    done
    exit 0
fi

# --- Generate ---
GENERATED=0
CURRENT_OPT=""
CURRENT_DIR=""

for pair in "${PAIRS[@]}"; do
    IFS=$'\t' read -r opt enc <<< "$pair"

    if [[ "$opt" != "$CURRENT_OPT" ]]; then
        CURRENT_OPT="$opt"
        CURRENT_DIR="${OUTPUT_DIR}/${opt}"
        mkdir -p "$CURRENT_DIR"
        echo "[$opt] → $CURRENT_DIR/"
    fi

    safe="${enc//\//_}"
    safe="${safe//\+/_}"
    out="${CURRENT_DIR}/${safe}.bgfa"

    # Build CLI flags: all set to "none" except the active one
    flag_args=""
    for flag in "${ALL_FLAGS[@]}"; do
        if [[ "$flag" == "${OPTION_TO_FLAG[$opt]}" ]]; then
            flag_args="$flag_args $flag $enc"
        else
            flag_args="$flag_args $flag none"
        fi
    done

    if [[ "$VERBOSE" -eq 1 ]]; then
        echo "  $out"
    fi

    pixi run python bin/bgfatools bgfa "$GFA_FILE" "$out" \
        --block-size "$BLOCK_SIZE" \
        $flag_args > /dev/null 2>&1

    GENERATED=$((GENERATED + 1))
done

echo ""
echo "Done: $GENERATED BGFA files written to $OUTPUT_DIR/"
