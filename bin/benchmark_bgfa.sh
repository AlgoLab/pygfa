#!/usr/bin/env bash
#
# Benchmark all BGFA encoding strategy combinations on the largest GFA files.
#
# Produces a TSV summary with: dataset, integer encoding, string encoding,
# original GFA size, BGFA size, compression ratio, encode time, decode time.
#
# Usage:
#   bash bin/benchmark_bgfa.sh
#   bash bin/benchmark_bgfa.sh results_dir   # custom output directory
#

set -euo pipefail
export LC_NUMERIC=C

RESULTS_DIR="${1:-results/benchmark}"
BGFATOOLS="pixi run python bin/bgfatools"
SUMMARY="$RESULTS_DIR/summary.tsv"

# --- Input files (two largest GFA files in data/) ---
GFA_FILES=(
	"data/atcc_staggered.assembly_graph_with_scaffolds.gfa"
	"data/medium_example.gfa"
)

# --- Encoding strategies (per BGFA spec) ---
INT_ENCODINGS=("" varint fixed32 fixed64 delta gamma omega golomb rice streamvbyte vbyte)
STR_ENCODINGS=("" zstd gzip lzma huffman)

# --- Helper: human-readable label for the empty-string identity encoding ---
label() { [[ -z "$1" ]] && echo "none" || echo "$1"; }

# --- Create output directory and write TSV header ---
mkdir -p "$RESULTS_DIR"
printf "dataset\tint_encoding\tstr_encoding\tgfa_bytes\tbgfa_bytes\tcompression_ratio\tencode_seconds\tdecode_seconds\n" \
	>"$SUMMARY"

total=$((${#GFA_FILES[@]} * ${#INT_ENCODINGS[@]} * ${#STR_ENCODINGS[@]}))
current=0

for gfa in "${GFA_FILES[@]}"; do
	dataset="$(basename "$gfa" .gfa)"
	gfa_size=$(stat --printf='%s' "$gfa" 2>/dev/null || stat -f '%z' "$gfa")
	subdir="$RESULTS_DIR/$dataset"
	mkdir -p "$subdir"

	for int_enc in "${INT_ENCODINGS[@]}"; do
		for str_enc in "${STR_ENCODINGS[@]}"; do
			current=$((current + 1))
			int_label=$(label "$int_enc")
			str_label=$(label "$str_enc")
			tag="${int_label}_${str_label}"

			bgfa_file="$subdir/${tag}.bgfa"
			printf "[%3d/%d] %-30s  int=%-12s str=%-8s " \
				"$current" "$total" "$dataset" "$int_label" "$str_label"

			# --- Encode: GFA -> BGFA ---
			enc_start=$(date +%s%N)
			if ! $BGFATOOLS bgfa "$gfa" "$bgfa_file" \
				--segment-names-payload-lengths "$int_enc" \
				--segment-names-payload-names "$str_enc" \
				--segments-payload-lengths "$int_enc" \
				--segments-payload-strings "$str_enc" \
				--links-payload-from "$int_enc" \
				--links-payload-to "$int_enc" \
				--links-payload-cigar-lengths "$int_enc" \
				--links-payload-cigar "$str_enc" \
				--paths-payload-names "$str_enc" \
				--paths-payload-segment-lengths "$int_enc" \
				--paths-payload-cigar-lengths "$int_enc" \
				--paths-payload-cigar "$str_enc" \
				--walks-payload-sample-ids "$str_enc" \
				--walks-payload-hep-indices "$int_enc" \
				--walks-payload-sequence-ids "$str_enc" \
				--walks-payload-start "$int_enc" \
				--walks-payload-end "$int_enc" \
				>/dev/null 2>&1; then
				printf "ENCODE FAILED\n"
				printf "%s\t%s\t%s\t%s\tERROR\t-\t-\t-\n" \
					"$dataset" "$int_label" "$str_label" "$gfa_size" >>"$SUMMARY"
				continue
			fi
			enc_end=$(date +%s%N)
			enc_ms=$(((enc_end - enc_start) / 1000000))
			enc_sec=$(awk "BEGIN {printf \"%.3f\", $enc_ms/1000}")

			bgfa_size=$(stat --printf='%s' "$bgfa_file" 2>/dev/null || stat -f '%z' "$bgfa_file")
			ratio=$(awk "BEGIN {printf \"%.4f\", $bgfa_size/$gfa_size}")

			# --- Decode: BGFA -> GFA ---
			dec_start=$(date +%s%N)
			if ! $BGFATOOLS cat "$bgfa_file" -o /dev/null >/dev/null 2>&1; then
				printf "enc=%.3fs  DECODE FAILED\n" "$enc_sec"
				printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\tERROR\n" \
					"$dataset" "$int_label" "$str_label" "$gfa_size" \
					"$bgfa_size" "$ratio" "$enc_sec" >>"$SUMMARY"
				rm -f "$bgfa_file"
				continue
			fi
			dec_end=$(date +%s%N)
			dec_ms=$(((dec_end - dec_start) / 1000000))
			dec_sec=$(awk "BEGIN {printf \"%.3f\", $dec_ms/1000}")

			printf "enc=%ss  dec=%ss  %s -> %s bytes (%.2f%%)\n" \
				"$enc_sec" "$dec_sec" "$gfa_size" "$bgfa_size" \
				"$(awk "BEGIN {printf \"%.2f\", $ratio*100}")"

			# --- Append row to summary ---
			printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
				"$dataset" "$int_label" "$str_label" "$gfa_size" \
				"$bgfa_size" "$ratio" "$enc_sec" "$dec_sec" >>"$SUMMARY"

			# Clean up BGFA file to save disk space
			rm -f "$bgfa_file"
		done
	done
done

echo ""
echo "=== Benchmark complete ==="
echo "Results: $SUMMARY"
echo "Combinations tested: $current"
echo ""
column -t -s $'\t' "$SUMMARY" | head -20
echo "..."
