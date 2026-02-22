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
    DatePricePoint,
    IndexGraphResponse,
    SectorTop10Response,
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
            .select("date, ticker, impacted_price")
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
        raw_date  = row.get("date")
        ticker    = row.get("ticker")
        price_val = row.get("impacted_price")
        if raw_date is None or ticker is None or price_val is None:
            continue
        ticker_map[ticker].append(
            DatePricePoint(date=_normalize_date(raw_date), price=float(price_val))
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
