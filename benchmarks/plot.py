from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmarks" / "results" / "local"


def main() -> None:
    data = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))["summary"]
    width, height = 900, 480
    margin = {"left": 80, "right": 30, "top": 45, "bottom": 70}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    max_y = max(item["p95_ms"] for item in data) * 1.15
    bar_group = plot_w / len(data)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#091019"/>',
        "<style>text{font-family:system-ui;fill:#dce8f2}.muted{fill:#91a5b8}.grid{stroke:#26384c;stroke-width:1}</style>",
        '<text x="80" y="28" font-size="20" font-weight="600">Correlation analysis latency</text>',
    ]
    for tick in range(6):
        value = max_y * tick / 5
        y = margin["top"] + plot_h - plot_h * tick / 5
        parts.append(f'<line class="grid" x1="80" x2="870" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(
            f'<text class="muted" x="70" y="{y + 4:.1f}" text-anchor="end">{value:.1f}</text>'
        )
    for index, item in enumerate(data):
        center = margin["left"] + bar_group * (index + 0.5)
        for offset, key, color in ((-20, "median_ms", "#35d0ba"), (20, "p95_ms", "#ffbd59")):
            value = item[key]
            bar_h = value / max_y * plot_h
            parts.append(
                f'<rect x="{center + offset - 17:.1f}" y="{margin["top"] + plot_h - bar_h:.1f}" '
                f'width="34" height="{bar_h:.1f}" rx="3" fill="{color}"/>'
            )
        parts.append(
            f'<text x="{center:.1f}" y="{height - 42}" text-anchor="middle">'
            f"{item['configured_baseline_items']:,}</text>"
        )
    parts.extend(
        [
            '<text class="muted" x="475" y="465" text-anchor="middle">'
            "Configured baseline evidence items</text>",
            '<text class="muted" transform="translate(20 240) rotate(-90)" '
            'text-anchor="middle">milliseconds</text>',
            '<rect x="660" y="16" width="12" height="12" fill="#35d0ba"/>'
            '<text x="678" y="27">median</text>',
            '<rect x="755" y="16" width="12" height="12" fill="#ffbd59"/>'
            '<text x="773" y="27">p95</text>',
            "</svg>",
        ]
    )
    (RESULTS / "correlation_latency.svg").write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
