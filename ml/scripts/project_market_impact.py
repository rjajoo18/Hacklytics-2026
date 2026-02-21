#!/usr/bin/env python3
"""
scripts/project_market_impact.py
==================================
90-Day Stock Market Projection driven by Tariff Impact CSV.

Model Design
------------
A) Baseline path (per index / per stock):
   - Fetch last `lookback_days` of daily closing prices via yfinance
     (falls back to deterministic drift-only if internet is unavailable)
   - Estimate annualized drift mu and volatility sigma from log-returns
   - Project forward using Merton Jump Diffusion (JD) model:

       S_{t+dt} = S_t
                * exp((mu - 0.5*sigma^2 - lambda*k)*dt + sigma*sqrt(dt)*Z)
                * prod_{i=1}^{N(dt)} exp(mu_J + sigma_J * eps_i)

     where:
       dt       = 1/365.25  (calendar-day step, consistent with 90-day horizon)
       k        = exp(mu_J + 0.5*sigma_J^2) - 1   (compensator: E[jump factor] - 1)
       N(dt)    ~ Poisson(lambda * dt)              (number of jumps per step)
       Z, eps_i ~ N(0,1) independently

   - Merton JD defaults:
       --jump_lambda  1.0     Jump intensity (events/year). Range: 0.5-2.0 typical.
       --jump_mu     -0.02    Mean log-jump. Negative = downward/crash bias.
       --jump_sigma   0.08    Std-dev of log-jump sizes. Range: 0.05-0.15 typical.
       --seed         42      RNG seed for full reproducibility.

   - Fallback to deterministic drift-only when yfinance is unavailable:
       baseline[d] = last_price * exp(mu_daily_cal * d)

B) Tariff shock / decay curve:
   - total_impact_pct from CSV (sum of Move_*% columns across all rows)
   - Two-phase curve:
       Phase 1  (1 <= d <= bottom_day) : linear ramp to full impact
           cumulative(d) = total_impact_pct * (d / bottom_day)
       Phase 2  (d > bottom_day) : saturating partial recovery
           cumulative(d) = total_impact_pct
                           * (1 - recovery_fraction
                              * (1 - exp(-(d - bottom_day) / tau)))
   - Maximum shock at d == bottom_day (default: 12)
   - Settled impact by day 90: total_impact_pct * (1 - recovery_fraction)
   - CLI: --bottom_day (default 12), --recovery_fraction (default 0.5), --tau (default 20)

C) Impacted path:
       impacted[d] = baseline[d] * (1 + cumulative(d) / 100)

Index-Level Aggregation
-----------------------
Move_SP500_%, Move_Nasdaq_%, Move_Dow_%, Move_Sector_Top50_% are already
weighted contributions (price_gap * sensitivity_coefficient * index_weight).
Total index impact = SUM across all rows.
Sector impact      = SUM of Move_Sector_Top50_% grouped by Sector.

Sector Top-10 Stocks
---------------------
Curated 20-stock lists per sector (S&P 500 GICS constituents), sliced to top
10. Each stock is labeled in both CSV outputs and plots.
Label in plots: "Top 10 Representative Stocks".

Usage
-----
From ml/ directory (project root):
    python -m scripts.project_market_impact
    python -m scripts.project_market_impact \\
        --master_csv global_tariff_impact_master.csv \\
        --horizon_days 90 \\
        --lookback_days 252 \\
        --out_dir outputs \\
        --use_yfinance true \\
        --seed 42 \\
        --jump_lambda 1.0 \\
        --jump_mu -0.02 \\
        --jump_sigma 0.08 \\
        --bottom_day 12 \\
        --recovery_fraction 0.5 \\
        --tau 20

Outputs
-------
outputs/index_paths.csv                        -- long: date, index, baseline_price, impacted_price, total_impact_pct
outputs/sector_paths.csv                       -- date, sector, baseline_proxy_price, impacted_proxy_price, sector_total_impact_pct
outputs/stock_paths.csv                        -- date, sector, ticker, baseline_price, impacted_price, sector_total_impact_pct
outputs/sectors/{sector}_top10.csv             -- per-sector stock paths (same columns as stock_paths.csv)
outputs/plots/sp500_90d.png
outputs/plots/nasdaq100_90d.png
outputs/plots/dow_90d.png
outputs/plots/sectors/{sector}_top10_90d.png   -- one plot per sector, each ticker labeled
outputs/plots/sectors_top10_overview.png       -- sector dashboard grid
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

# Calendar-day time step used by Merton JD (1 day in year units)
DT_CALENDAR = 1.0 / CALENDAR_DAYS_PER_YEAR

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
# (S&P 500 GICS constituents, ~20 per sector; top 10 used per run)
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

# Fallback params for individual stocks when yfinance fails
# (used only when source == "default"; JD is skipped in that case)
_STOCK_FALLBACK = {
    "mu_annual":    0.08,
    "sigma_annual": 0.25,
    "last_price":   100.0,
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
        "--seed",
        type=int,
        default=42,
        help="RNG seed for Merton Jump Diffusion reproducibility (default: 42)",
    )

    # ── Merton Jump Diffusion parameters ─────────────────────────────────────
    # Default: lambda=1.0  =>  ~1 jump/year (moderate market events)
    # Default: mu_J=-0.02  =>  -2%% mean log-jump size (slight crash bias)
    # Default: sigma_J=0.08 => 8%% jump volatility (0.05-0.15 is typical)
    p.add_argument(
        "--jump_lambda",
        type=float,
        default=1.0,
        help="Poisson jump intensity lambda (events/year). Default: 1.0 (range 0.5-2.0)",
    )
    p.add_argument(
        "--jump_mu",
        type=float,
        default=-0.02,
        help="Mean log-jump size mu_J. Negative => downward/crash bias. Default: -0.02",
    )
    p.add_argument(
        "--jump_sigma",
        type=float,
        default=0.08,
        help="Std-dev of log-jump sizes sigma_J. Default: 0.08 (range 0.05-0.15)",
    )

    # ── Shock curve parameters ────────────────────────────────────────────────
    # Default: bottom_day=12  => max shock felt by day 12 (range 10-15)
    # Default: recovery_fraction=0.5 => 50%% recovery by day ~3*tau (range 0.3-0.7)
    # Default: tau=20 => recovery e-folding time of 20 days
    p.add_argument(
        "--bottom_day",
        type=int,
        default=12,
        help="Day of maximum tariff shock (default: 12, range 10-15)",
    )
    p.add_argument(
        "--recovery_fraction",
        type=float,
        default=0.5,
        help="Fraction [0,1] of shock that recovers by day 90 (default: 0.5)",
    )
    # Accept both --tau and --tau_recovery for backward compatibility
    p.add_argument(
        "--tau", "--tau_recovery",
        dest="tau",
        type=float,
        default=20.0,
        help="Recovery time constant in days (default: 20). Alias: --tau_recovery",
    )
    return p.parse_args()


# =============================================================================
# Data loading & validation
# =============================================================================

def _resolve_csv(path: str) -> Path:
    """
    Try several locations to find the master CSV.

    Search order (first match wins):
      1. Path as given (works if absolute or cwd-relative)
      2. ml/ project directory (works when called from ml/ parent)
      3. Next to this script's parent (ml/global_tariff_impact_master.csv)
      4. Bare filename in cwd
      5. Bare filename in script parent
    """
    script_dir  = Path(__file__).resolve().parent   # ml/scripts/
    project_dir = script_dir.parent                 # ml/

    candidates = [
        Path(path),
        project_dir / Path(path).name,                       # ml/<filename>
        project_dir.parent / "ml" / Path(path).name,         # ../ml/<filename>
        Path(path).name,                                      # bare filename in cwd
        project_dir / path,                                   # ml/<full-relative-path>
    ]
    for c in candidates:
        try:
            if c.exists():
                return c.resolve()
        except OSError:
            continue

    raise FileNotFoundError(
        f"Cannot find master CSV '{path}'.\n"
        f"  Tried: {[str(c) for c in candidates]}\n"
        f"  Run from ml/ directory or pass an absolute path via --master_csv."
    )


def load_and_validate(path: str) -> pd.DataFrame:
    """Load master CSV and validate required columns."""
    p = _resolve_csv(path)
    df = pd.read_csv(p)
    print(f"Loaded {len(df):,} rows x {len(df.columns)} cols from: {p}")

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
    tau: float,
) -> np.ndarray:
    """
    Two-phase cumulative tariff impact curve for days 1..horizon.

    Phase 1 (d <= bottom_day):  linear ramp from 0 to total_impact_pct
    Phase 2 (d >  bottom_day):  saturating partial recovery

        cumulative(d) = total_impact_pct * (1 - recovery_fraction
                                            * (1 - exp(-(d-bottom_day)/tau)))

    Parameters
    ----------
    horizon           : number of forward days
    total_impact_pct  : total tariff shock, e.g. -1.5 means -1.5%
    bottom_day        : day of maximum impact (end of Phase 1); default 12
    recovery_fraction : fraction [0,1] of impact that reverts; default 0.5
    tau               : recovery e-folding time constant (days); default 20

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
        1.0 - recovery_fraction * (1.0 - np.exp(-(days - bottom_day) / tau)),
        1.0,
    )

    return phase1 * phase2_mult


# =============================================================================
# Price data fetching
# =============================================================================

def _fetch_yfinance(ticker: str, lookback_days: int) -> dict | None:
    """
    Download historical prices and estimate drift / volatility.
    Returns None on any failure.
    """
    try:
        import yfinance as yf

        end   = datetime.today()
        start = end - timedelta(days=int(lookback_days * 1.6))

        hist = yf.download(
            ticker, start=start, end=end, progress=False, auto_adjust=True
        )
        if hist is None or len(hist) < 20:
            return None

        closes     = hist["Close"].squeeze().dropna()
        log_ret    = np.log(closes / closes.shift(1)).dropna()
        mu_daily   = float(log_ret.mean())
        sigma_daily = float(log_ret.std())
        last_price  = float(closes.iloc[-1])

        return {
            "last_price":   last_price,
            "mu_annual":    mu_daily * TRADING_DAYS_PER_YEAR,
            "sigma_annual": sigma_daily * (TRADING_DAYS_PER_YEAR ** 0.5),
            "mu_daily_cal": mu_daily * TRADING_DAYS_PER_YEAR / CALENDAR_DAYS_PER_YEAR,
            "source":       "yfinance",
            "n_obs":        len(log_ret),
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
    """Return price params dict, trying yfinance then falling back to defaults."""
    if use_yfinance:
        params = _fetch_yfinance(ticker, lookback_days)
        if params:
            return params

    # Deterministic fallback (no historical data)
    return {
        "last_price":   default_price,
        "mu_annual":    default_mu_annual,
        "sigma_annual": default_sigma_annual,
        "mu_daily_cal": default_mu_annual / CALENDAR_DAYS_PER_YEAR,
        "source":       "default",
        "n_obs":        0,
    }


# =============================================================================
# Merton Jump Diffusion model
# =============================================================================

def jump_diffusion_path(
    last_price: float,
    mu_annual: float,
    sigma_annual: float,
    horizon: int,
    dt: float,
    jump_lambda: float,
    jump_mu: float,
    jump_sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Simulate a Merton Jump Diffusion price path (calendar-day stepping).

    Model (per daily step):
        S_{t+dt} = S_t
                 * exp((mu - 0.5*sigma^2 - lambda*k)*dt + sigma*sqrt(dt)*Z)
                 * prod_{i=1}^{N(dt)} exp(mu_J + sigma_J * eps_i)

    where:
        k        = exp(mu_J + 0.5*sigma_J^2) - 1     [jump compensator]
        N(dt)    ~ Poisson(lambda * dt)                [jumps per step]
        Z, eps_i ~ N(0,1) independently

    Parameters
    ----------
    last_price   : starting (today's) price
    mu_annual    : annualized drift (from historical log-returns)
    sigma_annual : annualized volatility (from historical log-returns)
    horizon      : number of daily steps to simulate
    dt           : time step in years; use DT_CALENDAR = 1/365.25
    jump_lambda  : Poisson intensity lambda (jumps/year); default 1.0
    jump_mu      : mean log-jump size mu_J; default -0.02 (crash bias)
    jump_sigma   : std-dev of log-jump sizes sigma_J; default 0.08
    rng          : numpy.random.Generator (seeded for reproducibility)

    Returns
    -------
    np.ndarray of shape (horizon,) -- simulated prices for days 1..horizon
    """
    # k = E[jump factor] - 1 = exp(mu_J + 0.5*sigma_J^2) - 1
    k = np.exp(jump_mu + 0.5 * jump_sigma ** 2) - 1.0

    prices = np.empty(horizon + 1)
    prices[0] = last_price

    for d in range(horizon):
        Z = rng.standard_normal()
        log_ret = (
            (mu_annual - 0.5 * sigma_annual ** 2 - jump_lambda * k) * dt
            + sigma_annual * np.sqrt(dt) * Z
        )

        n_jumps = rng.poisson(jump_lambda * dt)
        if n_jumps > 0:
            eps      = rng.standard_normal(n_jumps)
            log_ret += (jump_mu + jump_sigma * eps).sum()

        prices[d + 1] = prices[d] * np.exp(log_ret)

    return prices[1:]  # days 1..horizon


def _deterministic_baseline(
    last_price: float, mu_daily_cal: float, horizon: int
) -> np.ndarray:
    """
    Fallback path when yfinance data is unavailable.
    Deterministic drift: last_price * exp(mu_daily_cal * d) for d in 1..horizon.
    """
    days = np.arange(1, horizon + 1, dtype=float)
    return last_price * np.exp(mu_daily_cal * days)


def build_path(
    params: dict,
    horizon: int,
    jump_lambda: float,
    jump_mu: float,
    jump_sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Choose Merton JD (if yfinance data available) or deterministic baseline.

    JD requires estimated sigma; falls back to drift-only when source='default'.
    """
    if params.get("source") == "yfinance" and params.get("sigma_annual", 0.0) > 0.0:
        return jump_diffusion_path(
            last_price   = params["last_price"],
            mu_annual    = params["mu_annual"],
            sigma_annual = params["sigma_annual"],
            horizon      = horizon,
            dt           = DT_CALENDAR,
            jump_lambda  = jump_lambda,
            jump_mu      = jump_mu,
            jump_sigma   = jump_sigma,
            rng          = rng,
        )
    # Deterministic drift-only fallback (no internet / no historical data)
    return _deterministic_baseline(
        params["last_price"], params["mu_daily_cal"], horizon
    )


def impacted_path(
    base: np.ndarray,
    total_impact_pct: float,
    bottom_day: int,
    recovery_fraction: float,
    tau: float,
) -> np.ndarray:
    """Apply shock/decay curve on top of baseline path."""
    curve = shock_decay_curve(
        len(base), total_impact_pct, bottom_day, recovery_fraction, tau
    )
    return base * (1.0 + curve / 100.0)


def future_dates(horizon: int) -> pd.DatetimeIndex:
    """Calendar days starting tomorrow for a horizon-day window."""
    today = pd.Timestamp.today().normalize()
    return pd.date_range(
        start=today + pd.Timedelta(days=1), periods=horizon, freq="D"
    )


# =============================================================================
# Sanity checks
# =============================================================================

def sanity_checks(
    index_results: dict,
    sector_impacts_df: pd.DataFrame,
) -> None:
    """
    Print a sanity table and emit warnings for suspicious values.

    Warnings:
      - |total_impact_pct| > 15%  =>  may indicate sensitivity miscalibration
      - positive shock for broad tariffs  =>  verify sign convention
    """
    print("\n" + "=" * 74)
    print("  SANITY TABLE")
    print("=" * 74)
    header = (
        f"  {'Index':<30} {'Start':>10} {'Base Day90':>12}"
        f" {'Imp Day90':>12} {'Impact%':>9}"
    )
    print(header)
    print("  " + "-" * 70)
    for key, res in index_results.items():
        start  = res["params"]["last_price"]
        b_end  = res["baseline"][-1]
        i_end  = res["impacted"][-1]
        impact = res["total_impact_pct"]
        sign   = "+" if impact >= 0 else ""
        print(
            f"  {res['cfg']['label']:<30}"
            f"  {_fmt_price(start, None):>10}"
            f"  {_fmt_price(b_end, None):>10}"
            f"  {_fmt_price(i_end, None):>10}"
            f"  {sign}{impact:.3f}%"
        )
        if abs(impact) > 15.0:
            print(
                f"    WARNING: |total_impact_pct| = {abs(impact):.2f}% > 15%"
                f" for {key.upper()}. Review sensitivity coefficients."
            )
        if impact > 0.0:
            print(
                f"    NOTE: Positive shock ({impact:+.3f}%) for {key.upper()}."
                " Verify sign/sensitivity if broad tariffs are expected negative."
            )

    print(f"\n  {'Sector':<25} {'Impact%':>10}  {'Status'}")
    print("  " + "-" * 55)
    for _, row in sector_impacts_df.iterrows():
        sector = row["Sector"]
        impact = float(row["sector_impact_pct"])
        sign   = "+" if impact >= 0 else ""
        flags  = []
        if abs(impact) > 15.0:
            flags.append("WARNING: >15%")
        if impact > 0.0:
            flags.append("NOTE: positive shock")
        flag_str = " | ".join(flags) if flags else "ok"
        print(f"  {sector:<25} {sign}{impact:>8.4f}%  {flag_str}")

    print("=" * 74)


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
    params: dict,
    jump_lambda: float,
    jump_mu: float,
    jump_sigma: float,
    out_path: str,
) -> None:
    """Single index projection plot: baseline (JD or deterministic) + impacted."""
    if params.get("source") == "yfinance":
        model_label = (
            f"Merton JD (lambda={jump_lambda}, mu_J={jump_mu:+.3f},"
            f" sigma_J={jump_sigma:.3f})"
        )
    else:
        model_label = "Deterministic drift-only (fallback; no live data)"

    fig, ax = plt.subplots(figsize=(13, 6))

    ax.plot(dates, base, color=cfg["color_base"], lw=2.5,
            label=f"Baseline [{model_label}]", zorder=3)
    ax.plot(dates, imp, color=cfg["color_impact"], lw=2.5, linestyle="--",
            label=f"Tariff-Impacted  (total shock: {total_impact_pct:+.3f}%)",
            zorder=3)

    ax.fill_between(dates, base, imp,
                    where=(imp < base), alpha=0.12, color="red",
                    label="Negative shock zone")
    ax.fill_between(dates, base, imp,
                    where=(imp >= base), alpha=0.12, color="green",
                    label="Positive shock zone")

    sign = "+" if total_impact_pct >= 0 else ""
    ax.set_title(
        f"{cfg['label']}  --  90-Day Tariff-Impact Projection\n"
        f"Tariff shock: {sign}{total_impact_pct:.3f}%  |  {model_label}",
        fontsize=11, pad=10,
    )
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Price", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_price))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=35, ha="right")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.25)

    _annotate_end(ax, dates, base, "Baseline", cfg["color_base"],   va="bottom")
    _annotate_end(ax, dates, imp,  "Impacted", cfg["color_impact"], va="top")

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
    Per-sector plot with two layers:

    1. Individual stocks (impacted path):
       - Solid colored line per ticker, lw=1.2, labeled in legend
       - Each stock normalized to its own Day-0 price = 100

    2. Sector trendlines (averages across all stocks):
       - Dashed black line  = sector-average IMPACTED  (the "general trendline")
       - Dotted gray line   = sector-average BASELINE  (no-tariff reference)
       - Shaded fill between them shows the net tariff effect
    """
    fig, ax = plt.subplots(figsize=(15, 7))

    cmap        = plt.get_cmap("tab10")
    ticker_list = list(stocks.keys())
    colors      = [cmap(i % 10) for i in range(len(ticker_list))]

    base_norms, imp_norms = [], []

    for color, ticker in zip(colors, ticker_list):
        paths = stocks[ticker]
        b0    = paths["baseline"][0]
        if b0 <= 0:
            continue
        bn  = paths["baseline"] / b0 * 100.0
        in_ = paths["impacted"]  / b0 * 100.0

        # Individual stock: solid colored line for the impacted path, labeled by ticker
        ax.plot(dates, in_, color=color, lw=1.2, alpha=0.82, linestyle="-",
                label=ticker, zorder=3)

        base_norms.append(bn)
        imp_norms.append(in_)

    n_stocks = len(imp_norms)
    if base_norms:
        avg_b = np.mean(base_norms, axis=0)
        avg_i = np.mean(imp_norms,  axis=0)

        # Sector baseline trendline: gray dotted
        ax.plot(dates, avg_b, color="gray", lw=1.8, linestyle=":",
                alpha=0.75, zorder=4,
                label=f"Sector Baseline Trend ({n_stocks} stocks)")
        # Sector impacted trendline: bold black dashed
        ax.plot(dates, avg_i, color="black", lw=2.6, linestyle="--",
                zorder=5,
                label=f"Sector Impacted Trend ({impact_pct:+.3f}%)")
        ax.fill_between(dates, avg_b, avg_i, alpha=0.08,
                        color="red" if impact_pct < 0 else "green")

    ax.axhline(100.0, color="lightgray", lw=0.8, linestyle="--", alpha=0.6)
    sector_clean = sector.replace("_", " ")
    ax.set_title(
        f"Sector: {sector_clean}  --  Top {n_stocks} Representative Stocks\n"
        f"90-Day Tariff-Impacted Projection  |  Sector Impact: {impact_pct:+.3f}%\n"
        "Solid colored = individual stock impacted path (labeled by ticker)  |  "
        "Black dashed = sector avg impacted trend  |  "
        "Gray dotted = sector avg baseline  |  Normalized to 100 at Day 0",
        fontsize=10,
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized Price (Day 0 = 100)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=35, ha="right")
    ax.legend(fontsize=8, ncol=2, loc="upper left", framealpha=0.88)
    ax.grid(True, alpha=0.18)

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_sector_dashboard(
    dates: pd.DatetimeIndex,
    sector_data: dict,  # sector -> {stocks, sector_impact_pct}
    out_path: str,
) -> None:
    """
    Dashboard grid showing sector-average baseline vs impacted for all sectors.
    Each subplot is one sector; sector-average normalized to 100 at Day 0.
    """
    sectors = sorted(sector_data.keys())
    n = len(sectors)
    if n == 0:
        return

    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(
        nrows, ncols, figsize=(7 * ncols, 5 * nrows), squeeze=False
    )

    for idx, sector in enumerate(sectors):
        row, col = divmod(idx, ncols)
        ax       = axes[row][col]

        info    = sector_data[sector]
        stocks  = info["stocks"]
        imp_pct = info["sector_impact_pct"]

        base_norms, imp_norms = [], []
        for paths in stocks.values():
            b0 = paths["baseline"][0]
            if b0 <= 0:
                continue
            base_norms.append(paths["baseline"] / b0 * 100.0)
            imp_norms.append(paths["impacted"]  / b0 * 100.0)

        if base_norms:
            avg_b = np.mean(base_norms, axis=0)
            avg_i = np.mean(imp_norms,  axis=0)
            ax.plot(dates, avg_b, color="#1565C0", lw=2.0, label="Baseline")
            ax.plot(dates, avg_i, color="#C62828", lw=2.0, linestyle="--",
                    label="Impacted")
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

    # Hide unused subplot cells
    for idx in range(n, nrows * ncols):
        row, col = divmod(idx, ncols)
        axes[row][col].set_visible(False)

    fig.suptitle(
        "Sector Top-10 Representative Stocks -- 90-Day Tariff Impact Dashboard\n"
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
    """
    Save index paths in long format.
    Columns: date, index, baseline_price, impacted_price, total_impact_pct
    """
    rows = []
    for key, res in index_results.items():
        for date, b, i in zip(dates.date, res["baseline"], res["impacted"]):
            rows.append({
                "date":             date,
                "index":            key,
                "baseline_price":   round(float(b), 4),
                "impacted_price":   round(float(i), 4),
                "total_impact_pct": round(res["total_impact_pct"], 6),
            })
    p = Path(out_dir) / "index_paths.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(p, index=False)
    print(f"  Saved: {p}")


def save_sector_csvs(
    dates: pd.DatetimeIndex,
    sector_data: dict,
    out_dir: str,
) -> None:
    """
    Save two sets of outputs:
      1. outputs/sector_paths.csv  -- sector-average paths (long format)
         Columns: date, sector, baseline_proxy_price, impacted_proxy_price,
                  sector_total_impact_pct

      2. outputs/sectors/{sector}_top10.csv  -- per-sector stock paths
         Columns: date, sector, ticker, baseline_price, impacted_price,
                  sector_total_impact_pct
    """
    sector_rows = []
    sectors_dir = Path(out_dir) / "sectors"
    sectors_dir.mkdir(parents=True, exist_ok=True)

    for sector, info in sector_data.items():
        stocks  = info["stocks"]
        imp_pct = info["sector_impact_pct"]

        if not stocks:
            continue

        bases = np.array([v["baseline"] for v in stocks.values()])
        imps  = np.array([v["impacted"]  for v in stocks.values()])
        avg_b = bases.mean(axis=0)
        avg_i = imps.mean(axis=0)

        for date, b, i in zip(dates.date, avg_b, avg_i):
            sector_rows.append({
                "date":                    date,
                "sector":                  sector,
                "baseline_proxy_price":    round(float(b), 4),
                "impacted_proxy_price":    round(float(i), 4),
                "sector_total_impact_pct": round(imp_pct, 6),
            })

        # Per-sector long-format CSV (one row per date x ticker)
        # normalized_impacted_price: each ticker's impacted path scaled so Day 0 = 100
        # (matches the y-axis of the sector plot exactly)
        stock_rows = []
        for ticker, paths in stocks.items():
            day0 = paths["baseline"][0]
            scale = 100.0 / day0 if day0 > 0 else 1.0
            for date, b, i in zip(dates.date, paths["baseline"], paths["impacted"]):
                stock_rows.append({
                    "date":                      date,
                    "sector":                    sector,
                    "ticker":                    ticker,
                    "baseline_price":            round(float(b), 4),
                    "impacted_price":            round(float(i), 4),
                    "normalized_impacted_price": round(float(i) * scale, 4),
                    "sector_total_impact_pct":   round(imp_pct, 6),
                })
        csv_path = sectors_dir / f"{sector.lower()}_top10.csv"
        pd.DataFrame(stock_rows).to_csv(csv_path, index=False)

    if sector_rows:
        p = Path(out_dir) / "sector_paths.csv"
        pd.DataFrame(sector_rows).to_csv(p, index=False)
        print(f"  Saved: {p}")
        print(f"  Per-sector CSVs in: {sectors_dir}/")


def save_stock_paths_csv(
    dates: pd.DatetimeIndex,
    sector_data: dict,
    out_dir: str,
) -> None:
    """
    Save ALL stock paths consolidated in one file.
    Columns: date, sector, ticker, baseline_price, impacted_price,
             sector_total_impact_pct
    """
    rows = []
    for sector, info in sector_data.items():
        imp_pct = info["sector_impact_pct"]
        for ticker, paths in info["stocks"].items():
            day0  = paths["baseline"][0]
            scale = 100.0 / day0 if day0 > 0 else 1.0
            for date, b, i in zip(dates.date, paths["baseline"], paths["impacted"]):
                rows.append({
                    "date":                      date,
                    "sector":                    sector,
                    "ticker":                    ticker,
                    "baseline_price":            round(float(b), 4),
                    "impacted_price":            round(float(i), 4),
                    "normalized_impacted_price": round(float(i) * scale, 4),
                    "sector_total_impact_pct":   round(imp_pct, 6),
                })
    if rows:
        p = Path(out_dir) / "stock_paths.csv"
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
    # Exact match
    if sector in SECTOR_TICKERS:
        return sector, SECTOR_TICKERS[sector]

    # Case-insensitive + underscore-normalized match
    norm = sector.lower().replace("_", "")
    for key in SECTOR_TICKERS:
        if key.lower().replace("_", "") == norm:
            return key, SECTOR_TICKERS[key]

    # Substring match (e.g. "Steel" -> "Steel_Aluminum")
    for key in SECTOR_TICKERS:
        k = key.lower().replace("_", "")
        if norm in k or k in norm:
            return key, SECTOR_TICKERS[key]

    print(f"  WARNING: No ticker mapping for sector '{sector}'; using General fallback.")
    return "General", SECTOR_TICKERS["General"]


# =============================================================================
# Main orchestration
# =============================================================================

def main() -> None:
    args   = parse_args()
    use_yf = args.use_yfinance.lower() in ("true", "1", "yes")

    # Seeded RNG for reproducible Merton JD paths
    rng = np.random.default_rng(args.seed)

    print("=" * 72)
    print("  90-Day Market Impact Projection  --  Tariff Scenario")
    print("=" * 72)
    print(f"  master_csv         : {args.master_csv}")
    print(f"  horizon_days       : {args.horizon_days}")
    print(f"  lookback_days      : {args.lookback_days}")
    print(f"  use_yfinance       : {use_yf}")
    print(f"  seed               : {args.seed}")
    print(f"  jump_lambda        : {args.jump_lambda}  (jumps/year)")
    print(f"  jump_mu            : {args.jump_mu}  (mean log-jump size)")
    print(f"  jump_sigma         : {args.jump_sigma}  (std-dev log-jump)")
    print(f"  bottom_day         : {args.bottom_day}")
    print(f"  recovery_fraction  : {args.recovery_fraction:.0%}")
    print(f"  tau                : {args.tau}d")
    print(f"  out_dir            : {args.out_dir}/")
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
    # 4. Build index paths (Merton JD or deterministic fallback)
    # ------------------------------------------------------------------
    print("\n=== Building Index Price Paths ===")
    index_results: dict = {}

    for key, cfg in INDEX_CFG.items():
        print(f"\n  [{cfg['label']}]  ticker={cfg['ticker']}", end="  ")
        params = get_price_params(
            ticker              = cfg["ticker"],
            lookback_days       = args.lookback_days,
            use_yfinance        = use_yf,
            default_price       = cfg["default_price"],
            default_mu_annual   = cfg["default_mu_annual"],
            default_sigma_annual= cfg["default_sigma_annual"],
        )
        print(
            f"source={params['source']}"
            f"  last_price=${params['last_price']:,.2f}"
            f"  mu_annual={params['mu_annual']:+.3f}"
            f"  sigma_annual={params.get('sigma_annual', 0):.3f}"
        )

        base = build_path(
            params, args.horizon_days,
            args.jump_lambda, args.jump_mu, args.jump_sigma, rng
        )
        imp = impacted_path(
            base, index_impacts[key],
            args.bottom_day, args.recovery_fraction, args.tau
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
    print("\n=== Building Sector & Stock Price Paths (top 10 per sector) ===")
    sector_data: dict = {}
    price_cache: dict = {}  # ticker -> params (avoid re-fetching same ticker)

    for _, row in sector_impacts_df.iterrows():
        sector    = row["Sector"]
        imp_pct   = float(row["sector_impact_pct"])
        _, tickers = resolve_sector_tickers(sector)
        tickers    = tickers[:10]  # top 10 per sector

        print(f"\n  [{sector}]  impact={imp_pct:+.4f}%  tickers={len(tickers)}")

        stocks: dict = {}
        for ticker in tickers:
            if ticker not in price_cache:
                p = _fetch_yfinance(ticker, args.lookback_days) if use_yf else None
                if p is None:
                    p = {
                        "last_price":   _STOCK_FALLBACK["last_price"],
                        "mu_annual":    _STOCK_FALLBACK["mu_annual"],
                        "sigma_annual": _STOCK_FALLBACK["sigma_annual"],
                        "mu_daily_cal": _STOCK_FALLBACK["mu_annual"] / CALENDAR_DAYS_PER_YEAR,
                        "source":       "default",
                        "n_obs":        0,
                    }
                price_cache[ticker] = p

            p = price_cache[ticker]
            b = build_path(
                p, args.horizon_days,
                args.jump_lambda, args.jump_mu, args.jump_sigma, rng
            )
            i = impacted_path(
                b, imp_pct, args.bottom_day, args.recovery_fraction, args.tau
            )
            stocks[ticker] = {"baseline": b, "impacted": i}
            sys.stdout.write(".")
            sys.stdout.flush()

        print()  # newline after dots
        sector_data[sector] = {"stocks": stocks, "sector_impact_pct": imp_pct}

    # ------------------------------------------------------------------
    # 6. Sanity checks
    # ------------------------------------------------------------------
    sanity_checks(index_results, sector_impacts_df)

    # ------------------------------------------------------------------
    # 7. Save CSVs
    # ------------------------------------------------------------------
    print("\n=== Saving CSV Outputs ===")
    save_index_csv(dates, index_results, args.out_dir)
    save_sector_csvs(dates, sector_data, args.out_dir)
    save_stock_paths_csv(dates, sector_data, args.out_dir)

    # ------------------------------------------------------------------
    # 8. Generate plots
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
            res["params"],
            args.jump_lambda,
            args.jump_mu,
            args.jump_sigma,
            str(plots_dir / res["cfg"]["plot_file"]),
        )

    # Per-sector individual plots (filename: {sector}_top10_90d.png)
    sector_plots_dir = plots_dir / "sectors"
    for sector, info in sector_data.items():
        plot_single_sector(
            dates,
            sector,
            info["stocks"],
            info["sector_impact_pct"],
            str(sector_plots_dir / f"{sector.lower()}_top10_90d.png"),
        )

    # Sector overview dashboard
    plot_sector_dashboard(
        dates,
        sector_data,
        str(plots_dir / "sectors_top10_overview.png"),
    )

    # ------------------------------------------------------------------
    # 9. Final 90-day end-point summary
    # ------------------------------------------------------------------
    print("\n=== 90-Day End-Point Summary ===")
    print(
        f"  {'Index':<32} {'Baseline Day-90':>18}"
        f" {'Impacted Day-90':>18} {'Delta':>12}"
    )
    print("  " + "-" * 84)
    for key, res in index_results.items():
        b_end = res["baseline"][-1]
        i_end = res["impacted"][-1]
        delta = i_end - b_end
        sign  = "+" if delta >= 0 else ""
        print(
            f"  {res['cfg']['label']:<32}"
            f"  {_fmt_price(b_end, None):>16}"
            f"  {_fmt_price(i_end, None):>16}"
            f"  {sign}{_fmt_price(delta, None):>10}"
        )

    print(f"\nDone. All outputs written to: {Path(args.out_dir).resolve()}")
    print(f"Plots directory:              {plots_dir.resolve()}")


if __name__ == "__main__":
    main()
