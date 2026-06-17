#!/usr/bin/env python3
"""Recommend default encodings from benchmark summary CSV.

Reads a benchmark summary CSV (potentially zstd-compressed) and outputs
ranked encoding recommendations per compression option.

Usage:
    pixi run python tools/recommend_defaults.py results/benchmark/summary.csv.zst
    pixi run python tools/recommend_defaults.py results/benchmark/summary.csv.zst --mode balanced --top 10
    pixi run python tools/recommend_defaults.py results/benchmark/summary.csv.zst --mode pareto
    pixi run python tools/recommend_defaults.py results/benchmark/summary.csv.zst --group-by gc_content
    pixi run python tools/recommend_defaults.py results/benchmark/summary.csv.zst --output-format markdown
"""

import argparse
import csv
import io
import math
import statistics


def open_csv(path: str):
    """Open a CSV file, transparently handling .zst compression."""
    if path.endswith(".zst"):
        import zstandard as zstd
        with open(path, "rb") as f:
            dctx = zstd.ZstdDecompressor()
            reader = dctx.stream_reader(f)
            return io.TextIOWrapper(reader, encoding="utf-8")
    return open(path, newline="")


def load_data(path: str) -> list[dict]:
    """Load CSV rows into a list of dicts with derived fields."""
    with open_csv(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        ulen = float(row.get("uncompressed_length", 0) or 0)
        clen = float(row.get("compressed_length", 0) or 0)
        encode_ms = float(row.get("encode_time_ms", 0) or 0)
        decode_ms = float(row.get("decode_time_ms", 0) or 0)

        row["_ratio"] = ulen / clen if clen > 0 else 1.0
        total_ms = encode_ms + decode_ms
        row["_throughput"] = ulen / (total_ms / 1000.0) if total_ms > 0 else float("inf")
        row["_total_ms"] = total_ms
        row["_encode_ms"] = encode_ms
        row["_decode_ms"] = decode_ms

    return rows


def group_by_option(rows: list[dict]) -> dict[str, list[dict]]:
    """Group rows by compression_option."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        opt = row.get("compression_option", "unknown")
        if opt not in groups:
            groups[opt] = []
        groups[opt].append(row)
    return groups


def aggregate_by_encoding(rows: list[dict]) -> list[dict]:
    """For a given option's rows, aggregate by compression_value."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        val = row.get("compression_value", "unknown")
        if val not in groups:
            groups[val] = []
        groups[val].append(row)

    result = []
    for val, group in groups.items():
        ratios = [r["_ratio"] for r in group]
        throughputs = [r["_throughput"] for r in group if r["_throughput"] != float("inf")]
        encode_times = [r["_encode_ms"] for r in group if r["_encode_ms"] > 0]
        decode_times = [r["_decode_ms"] for r in group if r["_decode_ms"] > 0]

        result.append({
            "encoding": val,
            "num_datasets": len(set(r.get("original_gfa", "") for r in group)),
            "ratio_mean": sum(ratios) / len(ratios) if ratios else 0,
            "ratio_median": statistics.median(ratios) if ratios else 0,
            "ratio_min": min(ratios) if ratios else 0,
            "ratio_max": max(ratios) if ratios else 0,
            "encode_ms_mean": sum(encode_times) / len(encode_times) if encode_times else 0,
            "decode_ms_mean": sum(decode_times) / len(decode_times) if decode_times else 0,
            "throughput_mean": sum(throughputs) / len(throughputs) if throughputs else 0,
        })

    return result


def compute_pareto(encodings: list[dict]) -> list[dict]:
    """Filter to Pareto-optimal encodings (not dominated on ratio and decode speed)."""
    candidates = [e for e in encodings if e["decode_ms_mean"] > 0 and e["ratio_mean"] > 1.0]
    if not candidates:
        return encodings

    pareto = []
    for i, e1 in enumerate(candidates):
        dominated = False
        for j, e2 in enumerate(candidates):
            if i == j:
                continue
            # e2 dominates e1 if it's better in both ratio and decode speed
            if (e2["ratio_mean"] >= e1["ratio_mean"] and
                    e2["decode_ms_mean"] <= e1["decode_ms_mean"] and
                    (e2["ratio_mean"] > e1["ratio_mean"] or e2["decode_ms_mean"] < e1["decode_ms_mean"])):
                dominated = True
                break
        if not dominated:
            pareto.append(e1)

    return pareto


def balanced_score(e: dict, max_throughput: float) -> float:
    """Composite score: ratio weighted against decode speed."""
    if (max_throughput <= 0 or max_throughput == float("inf")
        or e["throughput_mean"] <= 0 or e["throughput_mean"] == float("inf")):
        return e["ratio_mean"]
    speed_bonus = 1.0 + math.log(e["throughput_mean"] / max_throughput) if e["throughput_mean"] > 0 else 1.0
    return e["ratio_mean"] * speed_bonus


def rank(encodings: list[dict], mode: str) -> list[dict]:
    """Sort encodings by the selected mode."""
    if mode == "best-ratio":
        return sorted(encodings, key=lambda e: e["ratio_median"], reverse=True)
    elif mode == "best-speed":
        return sorted(encodings, key=lambda e: e["decode_ms_mean"])
    elif mode == "pareto":
        pareto = compute_pareto(encodings)
        return sorted(pareto, key=lambda e: e["ratio_median"], reverse=True)
    elif mode == "balanced":
        max_tp = max((e["throughput_mean"] for e in encodings), default=1.0)
        for e in encodings:
            e["_score"] = balanced_score(e, max_tp)
        return sorted(encodings, key=lambda e: e["_score"], reverse=True)
    else:
        return sorted(encodings, key=lambda e: e["ratio_median"], reverse=True)


def format_text(ranked: dict[str, list[dict]], top: int) -> str:
    """Format results as plain text."""
    lines = []
    for option, encs in sorted(ranked.items()):
        lines.append(f"\n## {option}")
        lines.append(f"  {'rank':>4}  {'encoding':<30} {'ratio':>8} {'enc_ms':>8} {'dec_ms':>8} {'score':>8}")
        lines.append(f"  {'-'*4}  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for i, e in enumerate(encs[:top]):
            score = e.get("_score", e["ratio_median"])
            lines.append(
                f"  {i+1:>4}  {e['encoding']:<30} "
                f"{e['ratio_median']:>7.1f}x "
                f"{e['encode_ms_mean']:>7.1f} "
                f"{e['decode_ms_mean']:>7.1f} "
                f"{score:>7.1f}"
            )
        if encs:
            best = encs[0]["encoding"]
            lines.append(f"\n  Recommended default: {best}")
    return "\n".join(lines)


def format_markdown(ranked: dict[str, list[dict]], top: int) -> str:
    """Format results as markdown tables."""
    lines = []
    for option, encs in sorted(ranked.items()):
        lines.append(f"\n### {option}")
        lines.append("")
        lines.append("| Rank | Encoding | Ratio | Encode ms | Decode ms | Score |")
        lines.append("|------|----------|-------|-----------|-----------|-------|")
        for i, e in enumerate(encs[:top]):
            score = e.get("_score", e["ratio_median"])
            lines.append(
                f"| {i+1} | {e['encoding']} | {e['ratio_median']:.1f}x | "
                f"{e['encode_ms_mean']:.1f} | {e['decode_ms_mean']:.1f} | {score:.1f} |"
            )
        if encs:
            lines.append(f"\n**Recommended:** `{encs[0]['encoding']}`")
    return "\n".join(lines)


def format_json(ranked: dict[str, list[dict]], top: int) -> str:
    """Format results as JSON."""
    import json
    result = {}
    for option, encs in ranked.items():
        result[option] = [
            {
                "rank": i + 1,
                "encoding": e["encoding"],
                "ratio_median": round(e["ratio_median"], 2),
                "encode_ms_mean": round(e["encode_ms_mean"], 2),
                "decode_ms_mean": round(e["decode_ms_mean"], 2),
                "num_datasets": e["num_datasets"],
            }
            for i, e in enumerate(encs[:top])
        ]
    return json.dumps(result, indent=2)


def group_by_characteristic(rows: list[dict], characteristic: str) -> dict[str, list[dict]]:
    """Split rows into buckets by a characterization column."""
    values = [float(r.get(characteristic, 0) or 0) for r in rows if r.get(characteristic, "") != ""]
    if not values:
        return {"all": rows}

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q2 = sorted_vals[n // 2]
    q3 = sorted_vals[3 * n // 4]

    buckets = {"q1_low": [], "q2_medlow": [], "q3_medhigh": [], "q4_high": []}

    for row in rows:
        val = float(row.get(characteristic, 0) or 0)
        if val <= q1:
            buckets["q1_low"].append(row)
        elif val <= q2:
            buckets["q2_medlow"].append(row)
        elif val <= q3:
            buckets["q3_medhigh"].append(row)
        else:
            buckets["q4_high"].append(row)

    return {k: v for k, v in buckets.items() if v}


def main():
    parser = argparse.ArgumentParser(description="Recommend default encodings from benchmark summary")
    parser.add_argument("summary", help="Path to summary CSV (or .csv.zst)")
    parser.add_argument("--mode", choices=["best-ratio", "best-speed", "balanced", "pareto"],
                        default="balanced", help="Ranking mode (default: balanced)")
    parser.add_argument("--top", type=int, default=10, help="Show top N per option (default: 10)")
    parser.add_argument("--output-format", choices=["text", "markdown", "json"],
                        default="text", help="Output format (default: text)")
    parser.add_argument("--group-by", type=str, default=None,
                        help="Group results by characterization column (e.g. gc_content, avg_seq_len)")
    args = parser.parse_args()

    rows = load_data(args.summary)

    if args.group_by:
        char_buckets = group_by_characteristic(rows, args.group_by)
        output_parts = []
        for bucket, bucket_rows in sorted(char_buckets.items()):
            options = group_by_option(bucket_rows)
            ranked = {}
            for opt, opt_rows in options.items():
                encs = aggregate_by_encoding(opt_rows)
                ranked[opt] = rank(encs, args.mode)

            fmt = format_text if args.output_format == "text" else (
                format_markdown if args.output_format == "markdown" else format_json)
            bucket_header = f"\n{'='*60}\n# Group: {args.group_by}={bucket}  (n={len(bucket_rows)} rows)\n{'='*60}"
            output_parts.append(bucket_header + fmt(ranked, args.top))
        print("\n".join(output_parts))
    else:
        options = group_by_option(rows)
        ranked = {}
        for opt, opt_rows in options.items():
            encs = aggregate_by_encoding(opt_rows)
            ranked[opt] = rank(encs, args.mode)

        if args.output_format == "text":
            print(format_text(ranked, args.top))
        elif args.output_format == "markdown":
            print(format_markdown(ranked, args.top))
        else:
            print(format_json(ranked, args.top))


if __name__ == "__main__":
    main()
