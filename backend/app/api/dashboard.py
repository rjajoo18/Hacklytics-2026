"""
Dashboard API router.

Endpoints
---------
GET /api/dashboard/tariff-prob?country=...&sector=...
    Returns tariff probability % for a (country, sector) pair.

GET /api/dashboard/graph?graph_type=...&sector=...
    Returns time-series data sampled at 2-week intervals.
    graph_type: "nasdaq" | "sp500" | "dowjones" | "top10_sector_stocks"
    sector:     required only when graph_type == "top10_sector_stocks"

---
Actual Supabase schema (verified against live DB)
--------------------------------------------------
Table: country_tariff_prob
  id, country, sector, sector_base_prob, country_multiplier,
  tariff_risk_prob (float 0-1), tariff_risk_pct (text "21.70%")

Table: Index_paths
  id, date, index (text: "nasdaq"|"sp500"|"dow"), baseline_price,
  impacted_price, total_impact_pct
  -> long format; filter by `index` column, use `impacted_price`

Tables: {Sector}_top10  (e.g. Energy_top10, Agriculture_top10, Steel_aluminum_top10)
  id, date, sector, ticker, baseline_price, impacted_price,
  normalized_impacted_price, sector_total_impact_pct
  -> long format; group by ticker, use `impacted_price`
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from ..core.supabase import get_supabase
from ..models.responses import (
    ChartDataResponse,
    ChartSeries,
    DatePricePoint,
    IndexGraphResponse,
    SectorTop10Response,
    SeriesPoint,
    TariffProbResponse,
    TickerSeries,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── Constants ─────────────────────────────────────────────────────────────────

# Maps graph_type (frontend name) -> value stored in Index_paths.index column.
_INDEX_VALUE_MAP: dict[str, str] = {
    "nasdaq":   "nasdaq",
    "sp500":    "sp500",
    "dowjones": "dow",   # DB stores "dow", not "dowjones"
}

_VALID_GRAPH_TYPES = set(_INDEX_VALUE_MAP.keys()) | {"top10_sector_stocks"}

# Maps universe key (chart-data endpoint) -> value stored in Index_paths.index column.
_UNIVERSE_INDEX_MAP: dict[str, str] = {
    "nasdaq": "nasdaq",
    "sp500":  "sp500",
    "dow":    "dow",
}

_VALID_UNIVERSES = set(_UNIVERSE_INDEX_MAP.keys()) | {"sector_top10"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_date(raw: object) -> str:
    """Return the first 10 chars of any date value: 'YYYY-MM-DD'."""
    return str(raw)[:10]


def _sample_every_14_days(points: list[DatePricePoint]) -> list[DatePricePoint]:
    """
    Down-sample a list already sorted by date ascending,
    keeping one point every >= 14 calendar days.
    """
    if not points:
        return []

    result: list[DatePricePoint] = [points[0]]
    last = _date.fromisoformat(points[0].date)

    for p in points[1:]:
        current = _date.fromisoformat(p.date)
        if (current - last).days >= 14:
            result.append(p)
            last = current

    return result


def _sample_pairs_every_14_days(
    pairs: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Down-sample (date, value) pairs, keeping one every >= 14 calendar days."""
    if not pairs:
        return []
    result = [pairs[0]]
    last = _date.fromisoformat(pairs[0][0])
    for d, v in pairs[1:]:
        current = _date.fromisoformat(d)
        if (current - last).days >= 14:
            result.append((d, v))
            last = current
    return result


def _sector_to_table_name(sector: str) -> str:
    """
    Convert a sector display name to the corresponding Supabase table name.

    Special case:
      "Steel and aluminum" / "Steel & aluminum"  -> "Steel_aluminum_top10"

    All other sectors:
      Capitalise first letter, replace spaces with underscores, append "_top10".

    Examples:
      "Energy"      -> "Energy_top10"
      "Agriculture" -> "Agriculture_top10"
    """
    if sector.lower() in ("steel and aluminum", "steel & aluminum"):
        return "Steel_aluminum_top10"

    cleaned = sector.strip()
    if not cleaned:
        raise ValueError("sector must not be empty")

    table = cleaned[0].upper() + cleaned[1:]
    table = table.replace(" ", "_")
    return f"{table}_top10"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/tariff-prob", response_model=TariffProbResponse)
async def get_tariff_probability(
    country: str     = Query(..., description="Country name (e.g. 'CHINA')"),
    sector: str      = Query(..., description="Sector name (e.g. 'Energy')"),
    supabase: Client = Depends(get_supabase),
) -> TariffProbResponse:
    """Return the tariff probability % for a given (country, sector) pair."""
    resp = (
        supabase.table("country_tariff_prob")
        .select("country, sector, tariff_risk_prob")
        .eq("country", country)
        .eq("sector", sector)
        .limit(1)
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No tariff probability found for country='{country}', sector='{sector}'. "
                "Check that both values match rows in country_tariff_prob."
            ),
        )

    row = resp.data[0]
    return TariffProbResponse(
        country=row["country"],
        sector=row["sector"],
        # tariff_risk_prob is stored as 0–1 float; convert to percentage
        probability_percent=round(float(row["tariff_risk_prob"]) * 100, 2),
    )


@router.get("/graph")
async def get_graph_data(
    graph_type: str       = Query(..., description="nasdaq | sp500 | dowjones | top10_sector_stocks"),
    sector: Optional[str] = Query(None, description="Required when graph_type=top10_sector_stocks"),
    supabase: Client      = Depends(get_supabase),
) -> IndexGraphResponse | SectorTop10Response:
    """
    Return time-series graph data sampled at 2-week intervals.

    - nasdaq / sp500 / dowjones  -> { graph_type, points: [{date, price}] }
    - top10_sector_stocks        -> { sector, series: [{ticker, points}] }
    """
    if graph_type not in _VALID_GRAPH_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid graph_type '{graph_type}'. "
                f"Must be one of: {sorted(_VALID_GRAPH_TYPES)}."
            ),
        )

    if graph_type == "top10_sector_stocks":
        if not sector:
            raise HTTPException(
                status_code=400,
                detail="'sector' query parameter is required when graph_type=top10_sector_stocks.",
            )
        return await _fetch_sector_top10(sector, supabase)

    return await _fetch_index_series(graph_type, supabase)


# ── Private fetchers ──────────────────────────────────────────────────────────

async def _fetch_index_series(graph_type: str, supabase: Client) -> IndexGraphResponse:
    """
    Query Index_paths (long format) filtered by the `index` column.
    Returns impacted_price sampled every 14 days.
    """
    index_value = _INDEX_VALUE_MAP[graph_type]

    resp = (
        supabase.table("Index_paths")
        .select("date, impacted_price")
        .eq("index", index_value)
        .order("date", desc=False)
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No data found in Index_paths for graph_type='{graph_type}' "
                f"(index='{index_value}')."
            ),
        )

    raw_points: list[DatePricePoint] = []
    for row in resp.data:
        raw_date = row.get("date")
        price_val = row.get("impacted_price")
        if raw_date is None or price_val is None:
            continue
        raw_points.append(
            DatePricePoint(date=_normalize_date(raw_date), price=float(price_val))
        )

    if not raw_points:
        raise HTTPException(
            status_code=404,
            detail=f"All rows for index='{index_value}' have null impacted_price.",
        )

    return IndexGraphResponse(
        graph_type=graph_type,
        points=_sample_every_14_days(raw_points),
    )


async def _fetch_sector_top10(sector: str, supabase: Client) -> SectorTop10Response:
    """
    Query a sector's top-10 table (long format: one row per ticker per date).
    Groups rows by ticker, returns impacted_price sampled every 14 days.
    """
    try:
        table_name = _sector_to_table_name(sector)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        resp = (
            supabase.table(table_name)
            .select("date, ticker, baseline_price, impacted_price")
            .order("date", desc=False)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Could not query table '{table_name}' for sector='{sector}'. "
                f"Verify the table exists in Supabase. Error: {exc}"
            ),
        )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' exists but contains no rows.",
        )

    # Group rows by ticker -> sorted list of DatePricePoints
    ticker_map: dict[str, list[DatePricePoint]] = defaultdict(list)
    for row in resp.data:
        raw_date     = row.get("date")
        ticker       = row.get("ticker")
        impacted_val = row.get("impacted_price")
        baseline_val = row.get("baseline_price")

        if raw_date is None or ticker is None:
            continue

        # impacted_price is required for this endpoint
        if impacted_val is None:
            continue

        ticker_map[ticker].append(
            DatePricePoint(
                date=_normalize_date(raw_date),
                price=float(impacted_val),
                baseline_price=float(baseline_val) if baseline_val is not None else None,
            )
        )

    if not ticker_map:
        raise HTTPException(
            status_code=404,
            detail=f"No valid (date, ticker, impacted_price) rows found in '{table_name}'.",
        )

    # Down-sample each ticker's series independently
    series: list[TickerSeries] = [
        TickerSeries(ticker=ticker, points=_sample_every_14_days(pts))
        for ticker, pts in sorted(ticker_map.items())
        if pts
    ]

    return SectorTop10Response(sector=sector, series=series)


# ── /chart-data endpoint ───────────────────────────────────────────────────────

@router.get("/chart-data", response_model=ChartDataResponse)
async def get_chart_data(
    universe: str         = Query(..., description="sp500 | dow | nasdaq | sector_top10"),
    sector: Optional[str] = Query(None, description="Required when universe=sector_top10"),
    supabase: Client      = Depends(get_supabase),
) -> ChartDataResponse:
    """
    Unified chart-data endpoint consumed by the frontend LineChart.

    - sp500 / dow / nasdaq  -> two series: baseline + tariff-adjusted index prices
    - sector_top10          -> sector avg baseline, sector avg adjusted, + one series per ticker
    """
    if universe not in _VALID_UNIVERSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid universe '{universe}'. "
                f"Must be one of: {sorted(_VALID_UNIVERSES)}."
            ),
        )

    if universe == "sector_top10":
        if not sector:
            raise HTTPException(
                status_code=400,
                detail="'sector' query parameter is required when universe=sector_top10.",
            )
        return await _fetch_sector_chart_data(sector, supabase)

    return await _fetch_index_chart_data(universe, supabase)


async def _fetch_index_chart_data(universe: str, supabase: Client) -> ChartDataResponse:
    """Return baseline + tariff-adjusted index price series, sampled every 14 days."""
    index_value = _UNIVERSE_INDEX_MAP[universe]

    resp = (
        supabase.table("Index_paths")
        .select("date, baseline_price, impacted_price")
        .eq("index", index_value)
        .order("date", desc=False)
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"No data found in Index_paths for universe='{universe}' (index='{index_value}').",
        )

    baseline_raw: list[tuple[str, float]] = []
    adjusted_raw: list[tuple[str, float]] = []

    for row in resp.data:
        raw_date = row.get("date")
        baseline = row.get("baseline_price")
        impacted = row.get("impacted_price")
        if raw_date is None:
            continue
        date_str = _normalize_date(raw_date)
        if baseline is not None:
            baseline_raw.append((date_str, float(baseline)))
        if impacted is not None:
            adjusted_raw.append((date_str, float(impacted)))

    if not adjusted_raw:
        raise HTTPException(
            status_code=404,
            detail=f"All rows for index='{index_value}' have null impacted_price.",
        )

    series: list[ChartSeries] = []
    if baseline_raw:
        series.append(ChartSeries(
            key="baseline",
            label="Baseline (no tariff)",
            kind="baseline",
            points=[SeriesPoint(date=d, value=v) for d, v in _sample_pairs_every_14_days(baseline_raw)],
        ))
    series.append(ChartSeries(
        key="adjusted",
        label="Tariff-adjusted",
        kind="adjusted",
        points=[SeriesPoint(date=d, value=v) for d, v in _sample_pairs_every_14_days(adjusted_raw)],
    ))

    return ChartDataResponse(universe=universe, series=series)


async def _fetch_sector_chart_data(sector: str, supabase: Client) -> ChartDataResponse:
    """
    Return per-ticker series + sector-average baseline/adjusted, sampled every 14 days.

    - Individual stock series = impacted_price ONLY
    - Sector avg baseline     = baseline_price
    - Sector avg adjusted     = impacted_price
    """
    try:
        table_name = _sector_to_table_name(sector)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        resp = (
            supabase.table(table_name)
            .select("date, ticker, baseline_price, impacted_price")
            .order("date", desc=False)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Could not query table '{table_name}' for sector='{sector}'. "
                f"Error: {exc}"
            ),
        )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' exists but contains no rows.",
        )

    # ─────────────────────────────────────────────
    # Group by ticker
    # ─────────────────────────────────────────────

    ticker_baseline: dict[str, list[tuple[str, float]]] = defaultdict(list)
    ticker_adjusted: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for row in resp.data:
        raw_date = row.get("date")
        ticker   = row.get("ticker")

        if raw_date is None or ticker is None:
            continue

        date_str = _normalize_date(raw_date)

        # ✅ STOCK LINES: impacted_price ONLY
        impacted = row.get("impacted_price")
        if impacted is not None:
            ticker_adjusted[ticker].append((date_str, float(impacted)))

        # Baseline is used ONLY for sector baseline average
        baseline = row.get("baseline_price")
        if baseline is not None:
            ticker_baseline[ticker].append((date_str, float(baseline)))

    if not ticker_adjusted:
        raise HTTPException(
            status_code=404,
            detail=f"No valid impacted_price rows found in '{table_name}'.",
        )

    # ─────────────────────────────────────────────
    # Compute per-date sector averages
    # ─────────────────────────────────────────────

    date_baseline_vals: dict[str, list[float]] = defaultdict(list)
    date_adjusted_vals: dict[str, list[float]] = defaultdict(list)

    for pairs in ticker_baseline.values():
        for d, v in pairs:
            date_baseline_vals[d].append(v)

    for pairs in ticker_adjusted.values():
        for d, v in pairs:
            date_adjusted_vals[d].append(v)

    avg_baseline_raw = sorted(
        [(d, sum(vals) / len(vals)) for d, vals in date_baseline_vals.items()],
        key=lambda x: x[0],
    )

    avg_adjusted_raw = sorted(
        [(d, sum(vals) / len(vals)) for d, vals in date_adjusted_vals.items()],
        key=lambda x: x[0],
    )

    # ─────────────────────────────────────────────
    # Build ChartSeries
    # ─────────────────────────────────────────────

    series: list[ChartSeries] = []

    # Sector baseline average (thin dashed gray line in frontend)
    if avg_baseline_raw:
        series.append(ChartSeries(
            key="sector_avg_baseline",
            label="Sector avg (baseline)",
            kind="sector_avg_baseline",
            points=[
                SeriesPoint(date=d, value=v)
                for d, v in _sample_pairs_every_14_days(avg_baseline_raw)
            ],
        ))

    # Sector adjusted average (bold white line in frontend)
    if avg_adjusted_raw:
        series.append(ChartSeries(
            key="sector_avg_adjusted",
            label="Sector avg (tariff-adjusted)",
            kind="sector_avg_adjusted",
            points=[
                SeriesPoint(date=d, value=v)
                for d, v in _sample_pairs_every_14_days(avg_adjusted_raw)
            ],
        ))

    # Individual stock series (10 colored lines) — impacted only
    for ticker in sorted(ticker_adjusted.keys()):
        sampled = _sample_pairs_every_14_days(ticker_adjusted[ticker])
        series.append(ChartSeries(
            key=f"stock_{ticker}",
            label=ticker,
            kind="stock",
            points=[
                SeriesPoint(date=d, value=v)
                for d, v in sampled
            ],
        ))

    return ChartDataResponse(
        universe="sector_top10",
        sector=sector,
        series=series,
    )