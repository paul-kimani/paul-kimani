#!/usr/bin/env python3
"""Render a strategy tearsheet card as SVG from a backtest equity curve.

Standard library only, so it runs anywhere including a bare GitHub Action.

Usage
-----
  python scripts/profile_cards.py --csv data/gold_pulse.csv \
      --name "Gold Pulse" --meta "XAUUSD · H1 · 2021-2026" \
      --out assets/card-gold-pulse.svg

The CSV needs a date column and an equity column (defaults: `date`, `equity`).
Rows must be in chronological order, one row per bar or per day.

With no --csv, a synthetic series is generated and the card is stamped
SAMPLE DATA. Never publish a sample card as if it were a real result.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import date, timedelta

W, H = 520, 250
BG, LINE, DIM, TEXT = "#0D1117", "#30363D", "#7D8590", "#E6EDF3"
UP, DOWN, GRID = "#58A6FF", "#F85149", "#1B2129"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


# ---------------------------------------------------------------- data

def load_csv(path: str, date_col: str, equity_col: str):
    dates, equity = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw = row[equity_col].strip().replace(",", "")
            if not raw:
                continue
            dates.append(row[date_col].strip())
            equity.append(float(raw))
    if len(equity) < 3:
        raise SystemExit(f"{path}: need at least 3 equity points")
    return dates, equity


def synthetic(n: int = 760, seed: int = 7):
    """Demo series only. Drift and vol are arbitrary, not a backtest."""
    rng = random.Random(seed)
    start = date.today() - timedelta(days=n)
    dates, equity, level = [], [], 10_000.0
    for i in range(n):
        level *= 1 + rng.gauss(0.0006, 0.011)
        dates.append((start + timedelta(days=i)).isoformat())
        equity.append(level)
    return dates, equity


# ------------------------------------------------------------- metrics

def drawdown_series(equity):
    peak, dd = equity[0], []
    for v in equity:
        peak = max(peak, v)
        dd.append(v / peak - 1.0)
    return dd


def metrics(equity, periods_per_year: int):
    rets = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    n = len(rets)
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)

    total = equity[-1] / equity[0] - 1.0
    years = n / periods_per_year
    cagr = (equity[-1] / equity[0]) ** (1 / years) - 1.0 if years > 0 else 0.0
    vol = sd * math.sqrt(periods_per_year)
    sharpe = (mean / sd) * math.sqrt(periods_per_year) if sd > 0 else 0.0

    downside = [r for r in rets if r < 0]
    dsd = math.sqrt(sum(r * r for r in downside) / len(downside)) if downside else 0.0
    sortino = (mean / dsd) * math.sqrt(periods_per_year) if dsd > 0 else 0.0

    maxdd = min(drawdown_series(equity))
    hit = sum(1 for r in rets if r > 0) / n
    return {
        "total": total, "cagr": cagr, "vol": vol, "sharpe": sharpe,
        "sortino": sortino, "maxdd": maxdd, "hit": hit,
        "calmar": cagr / abs(maxdd) if maxdd < 0 else 0.0,
    }


# -------------------------------------------------------------- render

def resample(values, target=200):
    """Thin a long series for drawing. Metrics still use every point."""
    if len(values) <= target:
        return values
    step = (len(values) - 1) / (target - 1)
    out = [values[round(i * step)] for i in range(target)]
    out[-1] = values[-1]
    return out


def project(values, x0, x1, y0, y1, lo=None, hi=None):
    lo = min(values) if lo is None else lo
    hi = max(values) if hi is None else hi
    span = (hi - lo) or 1.0
    step = (x1 - x0) / (len(values) - 1)
    return [(x0 + i * step, y1 - (v - lo) / span * (y1 - y0))
            for i, v in enumerate(values)]


def polyline(pts):
    return " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}"
                    for i, (x, y) in enumerate(pts))


def pct(x, dp=1):
    return f"{x * 100:+.{dp}f}%"


def card(name, meta, dates, equity, m, sample: bool) -> str:
    dd = drawdown_series(equity)
    eq_pts = project(resample(equity), 24, W - 24, 74, 150)
    dd_pts = project(resample(dd), 24, W - 24, 172, 202, lo=min(dd), hi=0.0)

    area = polyline(eq_pts) + f" L{W - 24} 150 L24 150 Z"
    dd_area = polyline(dd_pts) + f" L{W - 24} 172 L24 172 Z"
    last_x, last_y = eq_pts[-1]

    cells = [
        ("CAGR", pct(m["cagr"]), UP if m["cagr"] > 0 else DOWN),
        ("SHARPE", f"{m['sharpe']:.2f}", TEXT),
        ("MAX DD", pct(m["maxdd"]), DOWN),
        ("CALMAR", f"{m['calmar']:.2f}", TEXT),
    ]
    cw = (W - 48) / len(cells)
    stats = []
    for i, (label, value, colour) in enumerate(cells):
        cx = 24 + i * cw + cw / 2
        stats.append(
            f'<text x="{cx:.1f}" y="228" fill="{colour}" font-size="17" '
            f'font-weight="700" text-anchor="middle">{value}</text>'
            f'<text x="{cx:.1f}" y="242" fill="{DIM}" font-size="9" '
            f'letter-spacing="1.3" text-anchor="middle">{label}</text>'
        )

    stamp = ""
    if sample:
        stamp = (f'<text x="{W - 24}" y="34" fill="#D29922" font-size="9" '
                 f'letter-spacing="1.5" text-anchor="end">SAMPLE DATA</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{name} strategy card">
  <defs>
    <linearGradient id="eqfill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{UP}" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="{UP}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="10" fill="{BG}" stroke="{LINE}"/>
  <g font-family="{MONO}">
    <text x="24" y="34" fill="{TEXT}" font-size="15" font-weight="700">{name}</text>
    <text x="24" y="52" fill="{DIM}" font-size="10.5" letter-spacing="1.1">{meta}</text>
    {stamp}
    <path d="M24 62H{W - 24}" stroke="{LINE}"/>

    <path d="M24 112H{W - 24}" stroke="{GRID}"/>
    <path d="{area}" fill="url(#eqfill)"/>
    <path d="{polyline(eq_pts)}" fill="none" stroke="{UP}" stroke-width="1.8" stroke-linejoin="round"/>
    <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="{UP}"/>
    <text x="24" y="72" fill="{DIM}" font-size="9" letter-spacing="1.2">EQUITY</text>

    <path d="{dd_area}" fill="{DOWN}" fill-opacity="0.18"/>
    <path d="{polyline(dd_pts)}" fill="none" stroke="{DOWN}" stroke-width="1.2"/>
    <text x="24" y="168" fill="{DIM}" font-size="9" letter-spacing="1.2">DRAWDOWN</text>

    <path d="M24 210H{W - 24}" stroke="{LINE}"/>
    {''.join(stats)}
  </g>
</svg>
'''


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv")
    p.add_argument("--date-col", default="date")
    p.add_argument("--equity-col", default="equity")
    p.add_argument("--name", default="Strategy")
    p.add_argument("--meta", default="")
    p.add_argument("--periods", type=int, default=252,
                   help="periods per year: 252 daily, 6240 H1 FX, 1560 H4")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="assets/card.svg")
    a = p.parse_args()

    if a.csv:
        dates, equity = load_csv(a.csv, a.date_col, a.equity_col)
        sample = False
    else:
        dates, equity = synthetic(seed=a.seed)
        sample = True

    m = metrics(equity, a.periods)
    meta = a.meta or f"{dates[0]} → {dates[-1]}"
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(card(a.name, meta, dates, equity, m, sample))

    print(f"{a.out}  total {pct(m['total'])}  sharpe {m['sharpe']:.2f}  "
          f"maxdd {pct(m['maxdd'])}  hit {m['hit'] * 100:.1f}%"
          + ("  [SAMPLE]" if sample else ""))


if __name__ == "__main__":
    main()
