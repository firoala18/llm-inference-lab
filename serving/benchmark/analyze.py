"""Turn sweep results into report charts and a summary table.

Reads  serving/benchmark/results/c<N>.json   (vllm bench serve output)
       serving/benchmark/results/gpu_c<N>.csv (1 Hz nvidia-smi samples)
Writes docs/img/{ttft,itl,throughput,gpu}.png and results/summary.csv

Run from the repo root with the .venv active:
    python serving/benchmark/analyze.py
"""

import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RESULTS = HERE / "results"
IMG = HERE / ".." / ".." / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

CONCURRENCIES = [1, 2, 4, 8, 16, 32]

# Chart chrome (validated palette, light mode)
SURFACE = "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"   # series 1 + 2, CVD-validated pair
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"


def load() -> pd.DataFrame:
    rows = []
    for c in CONCURRENCIES:
        d = json.loads((RESULTS / f"c{c}.json").read_text())
        gpu = pd.read_csv(RESULTS / f"gpu_c{c}.csv", header=None,
                          names=["util_pct", "mem_mib"])
        rows.append({
            "concurrency": c,
            "ttft_med_ms": d["median_ttft_ms"],
            "ttft_p99_ms": d["p99_ttft_ms"],
            "itl_med_ms": d["median_itl_ms"],
            "tok_per_s": d["output_throughput"],
            "req_per_s": d["request_throughput"],
            "failed": d["failed"],
            "gpu_util_mean_pct": gpu["util_pct"].mean(),
            "gpu_util_max_pct": gpu["util_pct"].max(),
            "vram_max_mib": gpu["mem_mib"].max(),
        })
    return pd.DataFrame(rows)


def style(ax, title, ylabel):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=12, loc="left", pad=12)
    ax.set_xlabel("gleichzeitige Requests (Concurrency)", color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.set_xscale("log", base=2)
    ax.set_xticks(CONCURRENCIES, [str(c) for c in CONCURRENCIES])
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.set_ylim(bottom=0)
    ax.margins(x=0.04)


def save(fig, name):
    out = IMG / name
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out.resolve()}")


def main():
    df = load()
    df.round(1).to_csv(RESULTS / "summary.csv", index=False)
    print(f"wrote {(RESULTS / 'summary.csv').resolve()}")
    x = df["concurrency"]

    # 1 — TTFT: the user-facing "does it feel instant?" metric
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(x, df["ttft_med_ms"], color=BLUE, lw=2, marker="o", ms=7,
            label="Median")
    ax.plot(x, df["ttft_p99_ms"], color=ORANGE, lw=2, marker="o", ms=7,
            label="P99")
    ax.axhline(2000, color=MUTED, lw=1, ls=(0, (4, 4)))
    ax.text(1, 2080, "SLO-Leitlinie: 2 s (P99)", color=MUTED, fontsize=8)
    style(ax, "Time To First Token vs. Concurrency (RTX 3090, Qwen3-8B)",
          "TTFT [ms]")
    ax.legend(frameon=False, labelcolor=INK2)
    save(fig, "ttft.png")

    # 2 — ITL: smoothness of streaming once a request is admitted
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(x, df["itl_med_ms"], color=BLUE, lw=2, marker="o", ms=7)
    style(ax, "Inter-Token-Latenz (Median) vs. Concurrency", "ITL [ms]")
    save(fig, "itl.png")

    # 3 — throughput: the operator's cost-per-token view
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(x, df["tok_per_s"], color=BLUE, lw=2, marker="o", ms=7)
    for c in (1, 8, 32):  # selective direct labels, text in ink not series color
        row = df[df["concurrency"] == c].iloc[0]
        ax.annotate(f"{row['tok_per_s']:.0f}", (c, row["tok_per_s"]),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", color=INK2, fontsize=9)
    style(ax, "Token-Durchsatz vs. Concurrency", "Output-Tokens / s")
    save(fig, "throughput.png")

    # 4 — GPU utilization: how much of the card the batch actually uses
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(x, df["gpu_util_mean_pct"], color=BLUE, lw=2, marker="o", ms=7)
    style(ax, "GPU-Auslastung (Mittel je Stufe) vs. Concurrency",
          "nvidia-smi util [%]")
    ax.set_ylim(0, 100)
    save(fig, "gpu.png")

    print(df.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
