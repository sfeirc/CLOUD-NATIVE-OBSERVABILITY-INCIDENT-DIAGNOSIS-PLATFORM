from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmarks" / "results"


def load(label: str) -> dict[str, Any]:
    if Path(label).name != label:
        raise ValueError("result label must be a single directory name")
    data = json.loads((RESULTS / label / "summary.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("benchmark summary must contain a JSON object")
    return cast(dict[str, Any], data)


def improvement(before: float, after: float) -> float:
    return (before - after) / before * 100


def compare(baseline_label: str, candidate_label: str, output_label: str) -> dict[str, Any]:
    baseline = load(baseline_label)
    candidate = load(candidate_label)
    baseline_meta = baseline["metadata"]
    candidate_meta = candidate["metadata"]
    checks = {
        "hardware_equal": baseline_meta["hardware"] == candidate_meta["hardware"],
        "operating_system_equal": (
            baseline_meta["operating_system"] == candidate_meta["operating_system"]
        ),
        "python_equal": (
            baseline_meta["software"]["python"] == candidate_meta["software"]["python"]
        ),
        "sizes_equal": (
            baseline_meta["configuration"]["sizes"] == candidate_meta["configuration"]["sizes"]
        ),
        "repetitions_equal": (
            baseline_meta["configuration"]["repetitions"]
            == candidate_meta["configuration"]["repetitions"]
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"benchmark result sets are not comparable: {checks}")

    baseline_by_size = {item["configured_baseline_items"]: item for item in baseline["summary"]}
    rows = []
    for candidate_item in candidate["summary"]:
        size = candidate_item["configured_baseline_items"]
        baseline_item = baseline_by_size[size]
        rows.append(
            {
                "configured_baseline_items": size,
                "baseline_median_ms": baseline_item["median_ms"],
                "candidate_median_ms": candidate_item["median_ms"],
                "median_improvement_percent": improvement(
                    baseline_item["median_ms"], candidate_item["median_ms"]
                ),
                "baseline_p95_ms": baseline_item["p95_ms"],
                "candidate_p95_ms": candidate_item["p95_ms"],
                "p95_improvement_percent": improvement(
                    baseline_item["p95_ms"], candidate_item["p95_ms"]
                ),
            }
        )

    result = {
        "generated_at": time.time(),
        "comparability_checks": checks,
        "baseline": {"label": baseline_label, "commit": baseline_meta["commit"]},
        "candidate": {"label": candidate_label, "commit": candidate_meta["commit"]},
        "comparison": rows,
    }
    output = RESULTS / output_label
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    render_svg(rows, output / "comparison.svg")
    return result


def render_svg(rows: list[dict[str, float]], output: Path) -> None:
    width, height = 940, 500
    left, top, plot_width, plot_height = 80, 55, 820, 350
    max_value = max(row["baseline_p95_ms"] for row in rows) * 1.15
    group_width = plot_width / len(rows)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#091019"/>',
        "<style>text{font-family:system-ui;fill:#dce8f2}.muted{fill:#91a5b8}"
        ".grid{stroke:#26384c;stroke-width:1}</style>",
        '<text x="80" y="30" font-size="20" font-weight="600">'
        "Measured correlation latency: baseline vs optimized</text>",
    ]
    for tick in range(6):
        value = max_value * tick / 5
        y = top + plot_height - plot_height * tick / 5
        parts.append(f'<line class="grid" x1="80" x2="900" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(
            f'<text class="muted" x="70" y="{y + 4:.1f}" text-anchor="end">{value:.1f}</text>'
        )
    for index, row in enumerate(rows):
        center = left + group_width * (index + 0.5)
        for offset, key, color in (
            (-25, "baseline_median_ms", "#ffbd59"),
            (25, "candidate_median_ms", "#35d0ba"),
        ):
            value = row[key]
            bar_height = value / max_value * plot_height
            parts.append(
                f'<rect x="{center + offset - 20:.1f}" '
                f'y="{top + plot_height - bar_height:.1f}" width="40" '
                f'height="{bar_height:.1f}" rx="3" fill="{color}"/>'
            )
        parts.append(
            f'<text x="{center:.1f}" y="430" text-anchor="middle">'
            f"{int(row['configured_baseline_items']):,}</text>"
        )
        parts.append(
            f'<text class="muted" x="{center:.1f}" y="450" text-anchor="middle">'
            f"{row['median_improvement_percent']:.1f}% faster</text>"
        )
    parts.extend(
        [
            '<text class="muted" x="490" y="482" text-anchor="middle">'
            "Configured baseline evidence items</text>",
            '<rect x="675" y="16" width="12" height="12" fill="#ffbd59"/>'
            '<text x="693" y="27">baseline median</text>',
            '<rect x="810" y="16" width="12" height="12" fill="#35d0ba"/>'
            '<text x="828" y="27">optimized</text>',
            "</svg>",
        ]
    )
    output.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two Incident Lens benchmark runs")
    parser.add_argument("--baseline", default="local")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.baseline, args.candidate, args.output), indent=2))


if __name__ == "__main__":
    main()
