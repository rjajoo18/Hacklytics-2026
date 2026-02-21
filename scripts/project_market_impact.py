#!/usr/bin/env python3
"""
scripts/project_market_impact.py
==================================
90-Day Stock Market Projection driven by Tariff Impact CSV.

Model Design
------------
A) Baseline path (per index / per stock):
   - Fetch last `lookback_days` of daily closing prices via yfinance
     (falls back to hard-coded defaults if internet is unavailable)
   - Estimate annualized drift mu and volatility sigma from log-returns
   - Project forward deterministically:
       baseline[d] = last_close * exp(mu_daily * d)   d in 1..horizon

B) Tariff shock / decay curve:
   - total_impact_pct from CSV (sum of Move_*% columns across all rows)
   - Two-phase curve:
       Phase 1  (1 <= d <= bottom_day) : linear ramp to full impact
           cumulative(d) = total_impact_pct * (d / bottom_day)
       Phase 2  (d > bottom_day) : saturating partial recovery
           cumulative(d) = total_impact_pct
                           * (1 - recovery_fraction
                              * (1 - exp(-(d - bottom_day) / tau_recovery)))
   - Maximum shock is at exactly d == bottom_day (default: day 15)
   - By day 90 the settled impact is total_impact_pct * (1 - recovery_fraction)

C) Impacted path:
       impacted[d] = baseline[d] * (1 + cumulative(d) / 100)

Index-Level Aggregation
-----------------------
The Move_SP500_%, Move_Nasdaq_%, Move_Dow_%, Move_Sector_Top50_% columns are
already weighted contributions (price_gap * sensitivity_coefficient * index_weight).
Total index impact = SUM across all rows (positives and negatives cancel partially).
Sector impact      = SUM of Move_Sector_Top50_% grouped by Sector.

"Top 50 per sector" approximation
----------------------------------
True top-50-by-market-cap requires real-time data.  This script uses curated
20-stock lists per sector (S&P 500 GICS constituents) as a representative sample.
Label in plots: "Top {n} Stocks (representative sample)".

Usage
-----
From repo root:
    python -m scripts.project_market_impact
    python -m scripts.project_market_impact \\
        --master_csv global_tariff_impact_master.csv \\
        --horizon_days 90 \\
        --lookback_days 252 \\
        --out_dir outputs \\
        --use_yfinance true \\
        --bottom_day 15 \\
        --recovery_fraction 0.35 \\
        --tau_recovery 30

Outputs
-------
outputs/index_paths.csv            -- date, sp500_baseline, sp500_impacted, ...
outputs/sector_paths.csv           -- date, sector, baseline_proxy, impacted_proxy
outputs/stocks_paths_sample.csv    -- sample of stock-level paths (3 sectors x 5 stocks)
outputs/sectors/{sector}_top50.csv -- full per-sector stock paths
outputs/plots/sp500_90d.png
outputs/plots/nasdaq100_90d.png
outputs/plots/dow_90d.png
outputs/plots/sectors_top50_90d.png          -- dashboard grid
outputs/plots/sectors/sector_{name}_top50.png -- individual sector plots
"""

import argparse
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── matplotlib: must use non-interactive backend before importing pyplot ──────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter


# =============================================================================
# Constants
# =============================================================================

REQUIRED_COLUMNS = {
    "Country",
    "Sector",
    "Move_SP500_%",
    "Move_Nasdaq_%",
    "Move_Dow_%",
    "Move_Sector_Top50_%",
}

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25

# Index configuration
INDEX_CFG = {
    "sp500": {
        "ticker": "^GSPC",
        "label": "S&P 500",
        "col": "Move_SP500_%",
        "default_price": 5_100.0,
        "default_mu_annual": 0.10,
        "default_sigma_annual": 0.18,
        "color_base": "#1565C0",
        "color_impact": "#C62828",
        "plot_file": "sp500_90d.png",
    },
    "nasdaq": {
        "ticker": "^NDX",
        "label": "NASDAQ-100",
        "col": "Move_Nasdaq_%",
        "default_price": 18_500.0,
        "default_mu_annual": 0.12,
        "default_sigma_annual": 0.22,
        "color_base": "#2E7D32",
        "color_impact": "#E65100",
        "plot_file": "nasdaq100_90d.png",
    },
    "dow": {
        "ticker": "^DJI",
        "label": "Dow Jones Industrial Average",
        "col": "Move_Dow_%",
        "default_price": 42_000.0,
        "default_mu_annual": 0.09,
        "default_sigma_annual": 0.15,
        "color_base": "#6A1B9A",
        "color_impact": "#BF360C",
        "plot_file": "dow_90d.png",
    },
}

# Curated sector -> representative stock tickers
# (S&P 500 GICS constituents, ~20 per sector; labeled as representative sample)
SECTOR_TICKERS: dict[str, list[str]] = {
    "Metals": [
        "NUE", "STLD", "CLF", "X", "AA", "FCX", "ATI", "CMC",
        "SCCO", "WPM", "AEM", "NEM", "GOLD", "KGC", "MP", "CENX",
        "HL", "PAAS", "AGI", "CRUS",
    ],
    "Steel_Aluminum": [
        "X", "NUE", "STLD", "CLF", "AA", "ATI", "RS", "CMC",
        "KALU", "CENX", "IIIN", "GBX", "TRN", "HAYN", "ZEUS",
        "MDU", "MLM", "VMC", "ASTE", "CSTM",
    ],
    "Automotive": [
        "GM", "F", "TSLA", "RIVN", "LCID", "APTV", "LEA", "BWA",
        "ALV", "MGA", "GNTX", "VC", "ADNT", "LKQ", "HOG",
        "THRM", "DORM", "MPAA", "STLA", "MODV",
    ],
    "Aerospace": [
        "BA", "RTX", "LMT", "NOC", "GD", "HEI", "TDG", "SPR",
        "KTOS", "LDOS", "SAIC", "BAH", "CACI", "DRS", "MRCY",
        "AVAV", "JOBY", "ACHR", "ERJ", "AIR",
    ],
    "Pharmaceuticals": [
        "JNJ", "PFE", "MRK", "ABBV", "LLY", "BMY", "AMGN", "GILD",
        "BIIB", "VRTX", "REGN", "ALNY", "INCY", "EXAS", "IONS",
        "NBIX", "ACAD", "EXEL", "SRPT", "HZNP",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "PXD", "EOG", "MPC", "VLO", "PSX",
        "SLB", "HAL", "OXY", "DVN", "HES", "BKR", "FANG",
        "APA", "MRO", "OVV", "CTRA", "RRC",
    ],
    "Agriculture": [
        "ADM", "BG", "MOS", "NTR", "CF", "FMC", "CTVA", "DE",
        "AGCO", "CNH", "INGR", "CALM", "TSN", "HRL", "CAG",
        "CPB", "GIS", "K", "VITL", "BUNGE",
    ],
    "Lumber": [
        "WY", "PCH", "IP", "PKG", "SLVM", "BCC", "LPX", "UFP",
        "BECN", "IBP", "BLDR", "MAS", "TREX", "AZEK", "DOOR",
        "PGTI", "ROCK", "UFPI", "CLW", "PCA",
    ],
    "Maritime": [
        "ZIM", "MATX", "KEX", "STNG", "FRO", "INSW", "TEN", "DHT",
        "NAT", "ESEA", "GSL", "DAC", "CMRE", "SFL", "GOGL",
        "TRMD", "TNP", "SBLK", "GNK", "HAFNI",
    ],
    "Minerals": [
        "FCX", "NEM", "GOLD", "AEM", "WPM", "PAAS", "HL", "CDE",
        "EGO", "KGC", "AG", "FSM", "MAG", "SSRM", "IAG",
        "BTG", "MUX", "AGI", "PVG", "GATO",
    ],
    # Fallback for unrecognized sectors
    "General": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "JPM",
        "V", "UNH", "XOM", "JNJ", "PG", "MA", "HD",
        "CVX", "MRK", "ABBV", "PEP", "KO",
    ],
}

# Fallback GBM params for individual stocks when yfinance fails
_STOCK_FALLBACK = {
    "mu_annual": 0.08,
    "sigma_annual": 0.25,
    "last_price": 100.0,
}


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="90-Day Market Impact Projection from Tariff CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--master_csv",
        default="global_tariff_impact_master.csv",
        help="Path to global_tariff_impact_master.csv (default: %(default)s)",
    )
    p.add_argument(
        "--horizon_days",
        type=int,
        default=90,
        help="Calendar days to project forward (default: 90)",
    )
    p.add_argument(
        "--lookback_days",
        type=int,
        default=252,
        help="Historical trading-day window for baseline estimation (default: 252)",
    )
    p.add_argument(
        "--out_dir",
        default="outputs",
        help="Root output directory (default: outputs/)",
    )
    p.add_argument(
        "--use_yfinance",
        default="true",
        help="Fetch real prices from yfinance: true/false (default: true)",
    )
    p.add_argument(
        "--bottom_day",
        type=int,
        default=15,
        help="Day at which maximum tariff shock is felt (default: 15)",
    )
    p.add_argument(
        "--recovery_fraction",
        type=float,
        default=0.35,
        help="Fraction [0,1] of shock that recovers by day 90 (default: 0.35)",
    )
    p.add_argument(
        "--tau_recovery",
        type=float,
        default=30.0,
        help="Recovery time constant in days (default: 30)",
    )
    return p.parse_args()


# =============================================================================
# Data loading & validation
# =============================================================================

def _resolve_csv(path: str) -> Path:
    """Try several locations to find the master CSV."""
    candidates = [
        Path(path),
        Path("HACKLYTICS_2026") / Path(path).name,
        Path("..") / Path(path).name,
        Path(__file__).parent.parent / Path(path).name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"Cannot find master CSV '{path}'.\n"
        f"  Tried: {[str(c) for c in candidates]}"
    )


def load_and_validate(path: str) -> pd.DataFrame:
    """Load master CSV and validate required columns."""
    p = _resolve_csv(path)
    df = pd.read_csv(p)
    print(f"Loaded {len(df):,} rows x {len(df.columns)} cols from: {p.resolve()}")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        print(f"\nERROR: Missing required columns: {sorted(missing)}")
        print(f"  Available: {list(df.columns)}")
        sys.exit(1)

    # Coerce numeric move columns
    move_cols = ["Move_SP500_%", "Move_Nasdaq_%", "Move_Dow_%", "Move_Sector_Top50_%"]
    for col in move_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Normalize sector names: spaces/& -> _, collapse doubles
    df["Sector"] = (
        df["Sector"]
        .str.strip()
        .str.replace(r"[\s&]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
    )

    n_bad = df[move_cols].isna().any(axis=1).sum()
    if n_bad:
        print(f"  WARNING: {n_bad} rows had non-numeric Move_* values -> filled with 0")

    return df


# =============================================================================
# Impact aggregation
# =============================================================================

def aggregate_impacts(df: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame]:
    """
    Sum Move_*% columns to get index-level and sector-level total impacts.

    Returns
    -------
    index_impacts : dict  {'sp500': float, 'nasdaq': float, 'dow': float}
    sector_impacts: DataFrame  ['Sector', 'sector_impact_pct']
    """
    index_impacts = {
        "sp500":  float(df["Move_SP500_%"].sum()),
        "nasdaq": float(df["Move_Nasdaq_%"].sum()),
        "dow":    float(df["Move_Dow_%"].sum()),
    }

    sector_impacts = (
        df.groupby("Sector")["Move_Sector_Top50_%"]
        .sum()
        .reset_index()
        .rename(columns={"Move_Sector_Top50_%": "sector_impact_pct"})
        .sort_values("sector_impact_pct")
    )

    print("\n=== Index-Level Aggregated Tariff Impact ===")
    for k, v in index_impacts.items():
        sign = "+" if v >= 0 else ""
        print(f"  {k.upper():8s}: {sign}{v:.4f}%")

    print("\n=== Sector-Level Aggregated Tariff Impact ===")
    for _, row in sector_impacts.iterrows():
        sign = "+" if row["sector_impact_pct"] >= 0 else ""
        print(f"  {row['Sector']:25s}: {sign}{row['sector_impact_pct']:.4f}%")

    return index_impacts, sector_impacts


# =============================================================================
# Shock / decay curve
# =============================================================================

def shock_decay_curve(
    horizon: int,
    total_impact_pct: float,
    bottom_day: int,
    recovery_fraction: float,
    tau_recovery: float,
) -> np.ndarray:
    """
    Two-phase cumulative tariff impact curve for days 1..horizon.

    Phase 1 (d <= bottom_day):  linear ramp from 0 to total_impact_pct
    Phase 2 (d >  bottom_day):  saturating partial recovery

        cumulative(d) = total_impact_pct * (1 - recovery_fraction
                                            * (1 - exp(-(d-bottom_day)/tau_recovery)))

    Parameters
    ----------
    horizon          : number of forward days
    total_impact_pct : total tariff shock, e.g. -1.5 means -1.5%
    bottom_day       : day of maximum impact (end of Phase 1)
    recovery_fraction: fraction [0,1] of impact that reverts by ~3*tau_recovery
    tau_recovery     : recovery e-folding time constant (days)

    Returns
    -------
    np.ndarray of shape (horizon,) -- cumulative impact % for day 1..horizon
    """
    days = np.arange(1, horizon + 1, dtype=float)

    # Phase 1: linear build-up
    phase1 = total_impact_pct * np.minimum(days / max(bottom_day, 1), 1.0)

    # Phase 2 multiplier: approaches (1 - recovery_fraction) asymptotically
    phase2_mult = np.where(
        days > bottom_day,
        1.0 - recovery_fraction * (1.0 - np.exp(-(days - bottom_day) / tau_recovery)),
        1.0,
    )

    return phase1 * phase2_mult


# =============================================================================
# Price data fetching
# =============================================================================

def _fetch_yfinance(ticker: str, lookback_days: int) -> dict | None:
    """
    Download historical prices and estimate GBM parameters.
    Returns None on any failure.
    """
    try:
        import yfinance as yf

        end = datetime.today()
        # Buffer 50% extra calendar days to ensure enough trading days
        start = end - timedelta(days=int(lookback_days * 1.6))

        hist = yf.download(
            ticker, start=start, end=end, progress=False, auto_adjust=True
        )
        if hist is None or len(hist) < 20:
            return None

        closes = hist["Close"].squeeze().dropna()
        log_ret = np.log(closes / closes.shift(1)).dropna()

        mu_daily    = float(log_ret.mean())
        sigma_daily = float(log_ret.std())
        last_price  = float(closes.iloc[-1])

        return {
            "last_price":      last_price,
            "mu_annual":       mu_daily * TRADING_DAYS_PER_YEAR,
            "sigma_annual":    sigma_daily * TRADING_DAYS_PER_YEAR ** 0.5,
            "mu_daily_cal":    mu_daily * TRADING_DAYS_PER_YEAR / CALENDAR_DAYS_PER_YEAR,
            "source":          "yfinance",
            "n_obs":           len(log_ret),
        }
    except Exception:
        return None


def get_price_params(
    ticker: str,
    lookback_days: int,
    use_yfinance: bool,
    default_price: float,
    default_mu_annual: float,
    default_sigma_annual: float,
) -> dict:
    """Return GBM params dict, attempting yfinance then falling back to defaults."""
    if use_yfinance:
        params = _fetch_yfinance(ticker, lookback_days)
        if params:
            return params

    mu_annual = default_mu_annual
    return {
        "last_price":   default_price,
        "mu_annual":    mu_annual,
        "sigma_annual": default_sigma_annual,
        "mu_daily_cal": mu_annual / CALENDAR_DAYS_PER_YEAR,
        "source":       "default",
        "n_obs":        0,
    }


# =============================================================================
# Path generation
# =============================================================================

def baseline_path(last_price: float, mu_daily_cal: float, horizon: int) -> np.ndarray:
    """Deterministic GBM: last_price * exp(mu_daily * d) for d in 1..horizon."""
    days = np.arange(1, horizon + 1, dtype=float)
    return last_price * np.exp(mu_daily_cal * days)


def impacted_path(
    base: np.ndarray,
    total_impact_pct: float,
    bottom_day: int,
    recovery_fraction: float,
    tau_recovery: float,
) -> np.ndarray:
    """Apply shock/decay curve on top of baseline."""
    curve = shock_decay_curve(
        len(base), total_impact_pct, bottom_day, recovery_fraction, tau_recovery
    )
    return base * (1.0 + curve / 100.0)


def future_dates(horizon: int) -> pd.DatetimeIndex:
    """Calendar days starting tomorrow."""
    today = pd.Timestamp.today().normalize()
    return pd.date_range(start=today + pd.Timedelta(days=1), periods=horizon, freq="D")


# =============================================================================
# Plotting helpers
# =============================================================================

def _fmt_price(x, _):
    if abs(x) >= 1_000:
        return f"${x:,.0f}"
    return f"${x:.2f}"


def _annotate_end(ax, dates, arr, label, color, va="bottom"):
    ax.annotate(
        f"{label}: {_fmt_price(arr[-1], None)}",
        xy=(dates[-1], arr[-1]),
        fontsize=8,
        color=color,
        ha="right",
        va=va,
    )


def plot_index(
    dates: pd.DatetimeIndex,
    base: np.ndarray,
    imp: np.ndarray,
    cfg: dict,
    total_impact_pct: float,
    out_path: str,
) -> None:
    """Single index projection plot with baseline and impacted lines."""
    fig, ax = plt.subplots(figsize=(13, 6))

    ax.plot(dates, base, color=cfg["color_base"],   lw=2.5, label="Baseline (no tariff shock)", zorder=3)
    ax.plot(dates, imp,  color=cfg["color_impact"], lw=2.5, linestyle="--",
            label=f"Tariff-Impacted  (total shock: {total_impact_pct:+.3f}%)", zorder=3)

    ax.fill_between(dates, base, imp,
                    where=(imp < base), alpha=0.12, color="red",   label="Negative shock zone")
    ax.fill_between(dates, base, imp,
                    where=(imp >= base), alpha=0.12, color="green", label="Positive shock zone")

    sign = "+" if total_impact_pct >= 0 else ""
    ax.set_title(
        f"{cfg['label']}  --  90-Day Tariff-Impact Projection\n"
        f"Tariff shock: {sign}{total_impact_pct:.3f}%  |  "
        "Model: deterministic GBM baseline + linear ramp / saturating recovery",
        fontsize=12, pad=10,
    )
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Price", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_price))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=35, ha="right")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.25)

    _annotate_end(ax, dates, base, "Baseline",  cfg["color_base"],   va="bottom")
    _annotate_end(ax, dates, imp,  "Impacted",  cfg["color_impact"], va="top")

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_single_sector(
    dates: pd.DatetimeIndex,
    sector: str,
    stocks: dict,       # ticker -> {'baseline': arr, 'impacted': arr}
    impact_pct: float,
    out_path: str,
) -> None:
    """
    One plot per sector: thin stock lines (normalized to 100 at day 0),
    bold sector-average line.
    """
    fig, ax = plt.subplots(figsize=(14, 7))

    base_norms, imp_norms = [], []

    for ticker, paths in stocks.items():
        b0 = paths["baseline"][0]
        if b0 <= 0:
            continue
        bn = paths["baseline"] / b0 * 100.0
        in_ = paths["impacted"] / b0 * 100.0
        ax.plot(dates, bn,  color="#1565C0", lw=0.7, alpha=0.35, zorder=2)
        ax.plot(dates, in_, color="#C62828", lw=0.7, alpha=0.35, zorder=2)
        base_norms.append(bn)
        imp_norms.append(in_)

    n_stocks = len(base_norms)
    if base_norms:
        avg_b = np.mean(base_norms, axis=0)
        avg_i = np.mean(imp_norms,  axis=0)
        ax.plot(dates, avg_b, color="#0D47A1", lw=3.0, zorder=4,
                label=f"Sector-Avg Baseline ({n_stocks} stocks)")
        ax.plot(dates, avg_i, color="#B71C1C", lw=3.0, linestyle="--", zorder=4,
                label=f"Sector-Avg Impacted (sector shock: {impact_pct:+.3f}%)")
        ax.fill_between(dates, avg_b, avg_i, alpha=0.18,
                        color="red" if impact_pct < 0 else "green")

    ax.axhline(100.0, color="gray", lw=0.6, linestyle=":", alpha=0.6)
    sector_clean = sector.replace("_", " ")
    ax.set_title(
        f"Sector: {sector_clean}  --  Top {n_stocks} Representative Stocks\n"
        f"90-Day Projection  |  Sector Tariff Impact: {impact_pct:+.3f}%\n"
        "(Thin lines = individual stocks, Bold = sector average; normalized to 100 at Day 0)",
        fontsize=11,
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized Price (Day 0 = 100)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=35, ha="right")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_sector_dashboard(
    dates: pd.DatetimeIndex,
    sector_data: dict,   # sector -> {stocks, sector_impact_pct}
    out_path: str,
) -> None:
    """
    One dashboard figure (grid of subplots) showing sector-average
    baseline vs impacted for all sectors.  Also triggers per-sector plots.
    """
    sectors = sorted(sector_data.keys())
    n = len(sectors)
    if n == 0:
        return

    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(7 * ncols, 5 * nrows), squeeze=False)

    for idx, sector in enumerate(sectors):
        row, col = divmod(idx, ncols)
        ax = axes[row][col]

        info    = sector_data[sector]
        stocks  = info["stocks"]
        imp_pct = info["sector_impact_pct"]

        base_norms, imp_norms = [], []
        for paths in stocks.values():
            b0 = paths["baseline"][0]
            if b0 <= 0:
                continue
            base_norms.append(paths["baseline"] / b0 * 100.0)
            imp_norms.append(paths["impacted"] / b0 * 100.0)

        if base_norms:
            avg_b = np.mean(base_norms, axis=0)
            avg_i = np.mean(imp_norms,  axis=0)
            ax.plot(dates, avg_b, color="#1565C0", lw=2.0, label="Baseline")
            ax.plot(dates, avg_i, color="#C62828", lw=2.0, linestyle="--", label="Impacted")
            ax.fill_between(dates, avg_b, avg_i, alpha=0.2,
                            color="red" if imp_pct < 0 else "green")

        ax.axhline(100.0, color="gray", lw=0.5, linestyle=":", alpha=0.5)
        ax.set_title(
            f"{sector.replace('_', ' ')}\nImpact: {imp_pct:+.3f}%",
            fontsize=9,
        )
        ax.set_ylabel("Norm. Price", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.tick_params(axis="both", labelsize=7)
        ax.grid(True, alpha=0.2)
        if idx == 0:
            ax.legend(fontsize=7)

    # Hide unused cells
    for idx in range(n, nrows * ncols):
        row, col = divmod(idx, ncols)
        axes[row][col].set_visible(False)

    fig.suptitle(
        "Sector Top-N Representative Stocks -- 90-Day Tariff Impact Dashboard\n"
        "(sector-average normalized to 100 at Day 0; Blue=Baseline, Red=Impacted)",
        fontsize=13, y=1.01,
    )
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# =============================================================================
# CSV saving
# =============================================================================

def save_index_csv(
    dates: pd.DatetimeIndex,
    index_results: dict,
    out_dir: str,
) -> None:
    rows: dict = {"date": dates.date}
    for key, res in index_results.items():
        rows[f"{key}_baseline"] = np.round(res["baseline"], 4)
        rows[f"{key}_impacted"] = np.round(res["impacted"], 4)
    p = Path(out_dir) / "index_paths.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(p, index=False)
    print(f"  Saved: {p}")


def save_sector_csvs(
    dates: pd.DatetimeIndex,
    sector_data: dict,
    out_dir: str,
) -> None:
    sector_rows = []
    sectors_dir = Path(out_dir) / "sectors"
    sectors_dir.mkdir(parents=True, exist_ok=True)

    for sector, info in sector_data.items():
        stocks   = info["stocks"]
        imp_pct  = info["sector_impact_pct"]

        if not stocks:
            continue

        bases = np.array([v["baseline"] for v in stocks.values()])
        imps  = np.array([v["impacted"]  for v in stocks.values()])
        avg_b = bases.mean(axis=0)
        avg_i = imps.mean(axis=0)

        for date, b, i in zip(dates.date, avg_b, avg_i):
            sector_rows.append({
                "date":                  date,
                "sector":                sector,
                "baseline_proxy":        round(float(b), 4),
                "impacted_proxy":        round(float(i), 4),
                "sector_total_impact_pct": round(imp_pct, 6),
            })

        # Per-sector stock CSV
        stock_dict: dict = {"date": dates.date}
        for ticker, paths in stocks.items():
            stock_dict[f"{ticker}_baseline"] = np.round(paths["baseline"], 4)
            stock_dict[f"{ticker}_impacted"] = np.round(paths["impacted"], 4)
        csv_path = sectors_dir / f"{sector.lower()}_top50.csv"
        pd.DataFrame(stock_dict).to_csv(csv_path, index=False)

    if sector_rows:
        p = Path(out_dir) / "sector_paths.csv"
        pd.DataFrame(sector_rows).to_csv(p, index=False)
        print(f"  Saved: {p}")
        print(f"  Per-sector CSVs: {sectors_dir}/")


def save_sample_csv(
    dates: pd.DatetimeIndex,
    sector_data: dict,
    out_dir: str,
    n_sectors: int = 3,
    n_stocks: int = 5,
) -> None:
    """Save a compact sample CSV (3 sectors x 5 stocks)."""
    rows: dict = {"date": dates.date}
    for sector, info in list(sector_data.items())[:n_sectors]:
        for ticker, paths in list(info["stocks"].items())[:n_stocks]:
            key = f"{sector[:10]}_{ticker}"
            rows[f"{key}_base"] = np.round(paths["baseline"], 4)
            rows[f"{key}_imp"]  = np.round(paths["impacted"], 4)
    p = Path(out_dir) / "stocks_paths_sample.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(p, index=False)
    print(f"  Saved: {p}")


# =============================================================================
# Sector-tickers resolution
# =============================================================================

def resolve_sector_tickers(sector: str) -> tuple[str, list[str]]:
    """
    Return (matched_key, tickers) for a sector name from the CSV.
    Falls back to 'General' if no match found.
    """
    # Try exact match
    if sector in SECTOR_TICKERS:
        return sector, SECTOR_TICKERS[sector]

    # Case-insensitive + underscore-normalised match
    norm = sector.lower().replace("_", "")
    for key in SECTOR_TICKERS:
        if key.lower().replace("_", "") == norm:
            return key, SECTOR_TICKERS[key]

    # Substring match (e.g. "Steel" matches "Steel_Aluminum")
    for key in SECTOR_TICKERS:
        if norm in key.lower().replace("_", "") or key.lower().replace("_", "") in norm:
            return key, SECTOR_TICKERS[key]

    return "General", SECTOR_TICKERS["General"]


# =============================================================================
# Main orchestration
# =============================================================================

def main() -> None:
    args = parse_args()
    use_yf = args.use_yfinance.lower() in ("true", "1", "yes")

    print("=" * 68)
    print("  90-Day Market Impact Projection  --  Tariff Scenario")
    print("=" * 68)
    print(f"  master_csv        : {args.master_csv}")
    print(f"  horizon_days      : {args.horizon_days}")
    print(f"  lookback_days     : {args.lookback_days}")
    print(f"  use_yfinance      : {use_yf}")
    print(f"  bottom_day        : {args.bottom_day}")
    print(f"  recovery_fraction : {args.recovery_fraction:.0%}")
    print(f"  tau_recovery      : {args.tau_recovery}d")
    print(f"  out_dir           : {args.out_dir}/")
    print()

    # ------------------------------------------------------------------
    # 1. Load CSV
    # ------------------------------------------------------------------
    df = load_and_validate(args.master_csv)

    # ------------------------------------------------------------------
    # 2. Aggregate impacts
    # ------------------------------------------------------------------
    index_impacts, sector_impacts_df = aggregate_impacts(df)

    # ------------------------------------------------------------------
    # 3. Future date range
    # ------------------------------------------------------------------
    dates = future_dates(args.horizon_days)

    # ------------------------------------------------------------------
    # 4. Build index paths
    # ------------------------------------------------------------------
    print("\n=== Building Index Price Paths ===")
    index_results: dict = {}

    for key, cfg in INDEX_CFG.items():
        print(f"\n  [{cfg['label']}]  ticker={cfg['ticker']}", end="  ")
        params = get_price_params(
            ticker             = cfg["ticker"],
            lookback_days      = args.lookback_days,
            use_yfinance       = use_yf,
            default_price      = cfg["default_price"],
            default_mu_annual  = cfg["default_mu_annual"],
            default_sigma_annual=cfg["default_sigma_annual"],
        )
        src = params["source"]
        print(
            f"source={src}  last_price=${params['last_price']:,.2f}"
            f"  mu_annual={params['mu_annual']:+.3f}"
        )

        base = baseline_path(params["last_price"], params["mu_daily_cal"], args.horizon_days)
        imp  = impacted_path(
            base, index_impacts[key],
            args.bottom_day, args.recovery_fraction, args.tau_recovery,
        )

        index_results[key] = {
            "baseline":         base,
            "impacted":         imp,
            "total_impact_pct": index_impacts[key],
            "cfg":              cfg,
            "params":           params,
        }

    # ------------------------------------------------------------------
    # 5. Build sector + stock paths
    # ------------------------------------------------------------------
    print("\n=== Building Sector & Stock Price Paths ===")
    sector_data: dict = {}
    price_cache: dict = {}   # ticker -> params (avoid re-fetching)

    for _, row in sector_impacts_df.iterrows():
        sector    = row["Sector"]
        imp_pct   = float(row["sector_impact_pct"])
        _, tickers = resolve_sector_tickers(sector)

        print(f"\n  [{sector}]  impact={imp_pct:+.4f}%  tickers={len(tickers)}")

        stocks: dict = {}
        for ticker in tickers:
            if ticker not in price_cache:
                p = None
                if use_yf:
                    p = _fetch_yfinance(ticker, args.lookback_days)
                if p is None:
                    p = {
                        "last_price":   _STOCK_FALLBACK["last_price"],
                        "mu_annual":    _STOCK_FALLBACK["mu_annual"],
                        "mu_daily_cal": _STOCK_FALLBACK["mu_annual"] / CALENDAR_DAYS_PER_YEAR,
                        "source":       "default",
                        "n_obs":        0,
                    }
                price_cache[ticker] = p

            p = price_cache[ticker]
            b = baseline_path(p["last_price"], p["mu_daily_cal"], args.horizon_days)
            i = impacted_path(
                b, imp_pct,
                args.bottom_day, args.recovery_fraction, args.tau_recovery,
            )
            stocks[ticker] = {"baseline": b, "impacted": i}
            sys.stdout.write(".")
            sys.stdout.flush()
        print()  # newline after dots

        sector_data[sector] = {"stocks": stocks, "sector_impact_pct": imp_pct}

    # ------------------------------------------------------------------
    # 6. Save CSVs
    # ------------------------------------------------------------------
    print("\n=== Saving CSV Outputs ===")
    save_index_csv(dates, index_results, args.out_dir)
    save_sector_csvs(dates, sector_data, args.out_dir)
    save_sample_csv(dates, sector_data, args.out_dir)

    # ------------------------------------------------------------------
    # 7. Generate plots
    # ------------------------------------------------------------------
    print("\n=== Generating Plots ===")
    plots_dir = Path(args.out_dir) / "plots"

    # Index plots
    for key, res in index_results.items():
        plot_index(
            dates,
            res["baseline"],
            res["impacted"],
            res["cfg"],
            res["total_impact_pct"],
            str(plots_dir / res["cfg"]["plot_file"]),
        )

    # Per-sector individual plots
    sector_plots_dir = plots_dir / "sectors"
    for sector, info in sector_data.items():
        plot_single_sector(
            dates,
            sector,
            info["stocks"],
            info["sector_impact_pct"],
            str(sector_plots_dir / f"sector_{sector.lower()}_top50.png"),
        )

    # Sector dashboard summary
    plot_sector_dashboard(
        dates,
        sector_data,
        str(plots_dir / "sectors_top50_90d.png"),
    )

    # ------------------------------------------------------------------
    # 8. Final summary
    # ------------------------------------------------------------------
    print("\n=== 90-Day End-Point Summary ===")
    print(f"  {'Index':<32} {'Baseline Day-90':>18} {'Impacted Day-90':>18} {'Delta':>12}")
    print("  " + "-" * 82)
    for key, res in index_results.items():
        b_end = res["baseline"][-1]
        i_end = res["impacted"][-1]
        delta = i_end - b_end
        print(
            f"  {res['cfg']['label']:<32}"
            f"  {_fmt_price(b_end, None):>16}"
            f"  {_fmt_price(i_end, None):>16}"
            f"  {'+' if delta >= 0 else ''}{_fmt_price(delta, None):>10}"
        )

    print(f"\nDone. All outputs written to: {Path(args.out_dir).resolve()}")
    print(f"Plots directory:              {plots_dir.resolve()}")


if __name__ == "__main__":
    main()
