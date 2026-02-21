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
Database assumptions
--------------------
Table: country_tariff_prob
  Columns: country (text), sector (text), probability_percent (numeric)

Table: Index_paths
  Expected wide format: date (date/text) | nasdaq (numeric) | sp500 (numeric) | dowjones (numeric)
  If your table has a different layout (e.g. a single "index_name" / "price" pair) update
  _INDEX_COLUMN_MAP and the query in _fetch_index_series() accordingly.

Tables: {Sector}_top10  (e.g. Technology_top10, Steel_aluminum_top10)
  Expected wide format: date (date/text) | <ticker1> (numeric) | <ticker2> (numeric) | ...
  Every non-date column is treated as a ticker.
"""

from __future__ import annotations

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

# Maps graph_type -> column name in the Index_paths table.
# Adjust column names here if they differ in your Supabase schema.
_INDEX_COLUMN_MAP: dict[str, str] = {
    "nasdaq":   "nasdaq",
    "sp500":    "sp500",
    "dowjones": "dowjones",
}

_VALID_GRAPH_TYPES = set(_INDEX_COLUMN_MAP.keys()) | {"top10_sector_stocks"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_date(raw: object) -> str:
    """Return the first 10 chars of a date string: 'YYYY-MM-DD'."""
    return str(raw)[:10]


def _sample_every_14_days(points: list[DatePricePoint]) -> list[DatePricePoint]:
    """
    Down-sample a list that is already sorted by date ascending,
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

    Rules:
      "Steel and aluminum"  -> "Steel_aluminum_top10"   (special case)
      Everything else       -> capitalize first letter, spaces -> underscores,
                               append "_top10"

    Examples:
      "Technology"          -> "Technology_top10"
      "Consumer Discretionary" -> "Consumer_Discretionary_top10"
    """
    if sector.lower() in ("steel and aluminum", "steel & aluminum"):
        return "Steel_aluminum_top10"

    cleaned = sector.strip()
    if not cleaned:
        raise ValueError("sector must not be empty")

    table = cleaned[0].upper() + cleaned[1:]   # capitalise first letter
    table = table.replace(" ", "_")
    return f"{table}_top10"


def _build_date_price_points(
    rows: list[dict],
    date_col: str,
    price_col: str,
) -> list[DatePricePoint]:
    """Extract (date, price) pairs, skipping rows with null prices."""
    points: list[DatePricePoint] = []
    for row in rows:
        raw_date = row.get(date_col)
        price_val = row.get(price_col)
        if raw_date is None or price_val is None:
            continue
        points.append(DatePricePoint(date=_normalize_date(raw_date), price=float(price_val)))
    return points


def _find_date_column(columns: list[str]) -> str | None:
    """Return the date column name, case-insensitively."""
    for col in columns:
        if col.lower() == "date":
            return col
    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/tariff-prob", response_model=TariffProbResponse)
async def get_tariff_probability(
    country: str = Query(..., description="Country name (e.g. 'China')"),
    sector: str  = Query(..., description="Sector name (e.g. 'Technology')"),
    supabase: Client = Depends(get_supabase),
) -> TariffProbResponse:
    """Return the tariff probability % for a given (country, sector) pair."""
    resp = (
        supabase.table("country_tariff_prob")
        .select("country, sector, probability_percent")
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
        probability_percent=float(row["probability_percent"]),
    )


@router.get("/graph")
async def get_graph_data(
    graph_type: str       = Query(..., description="nasdaq | sp500 | dowjones | top10_sector_stocks"),
    sector: Optional[str] = Query(None, description="Required when graph_type=top10_sector_stocks"),
    supabase: Client      = Depends(get_supabase),
) -> IndexGraphResponse | SectorTop10Response:
    """
    Return time-series graph data sampled at 2-week intervals.

    - For nasdaq / sp500 / dowjones: queries Index_paths, returns {graph_type, points[]}.
    - For top10_sector_stocks:       queries {Sector}_top10, returns {sector, series[]}.
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
    """Fetch a single index column from Index_paths and down-sample."""
    price_col = _INDEX_COLUMN_MAP[graph_type]

    resp = (
        supabase.table("Index_paths")
        .select(f"date, {price_col}")
        .order("date", desc=False)
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No data found in Index_paths for graph_type='{graph_type}' "
                f"(queried column: '{price_col}')."
            ),
        )

    raw_points = _build_date_price_points(resp.data, "date", price_col)
    if not raw_points:
        raise HTTPException(
            status_code=404,
            detail=f"All rows in Index_paths have null values for column '{price_col}'.",
        )

    return IndexGraphResponse(
        graph_type=graph_type,
        points=_sample_every_14_days(raw_points),
    )


async def _fetch_sector_top10(sector: str, supabase: Client) -> SectorTop10Response:
    """
    Fetch all rows from the sector's top-10 table.

    The table is expected to be in wide format:
        date  | AAPL  | MSFT  | GOOGL | ...
    Every column except 'date' is treated as a ticker symbol.
    """
    try:
        table_name = _sector_to_table_name(sector)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        resp = (
            supabase.table(table_name)
            .select("*")
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

    # Identify the date column (case-insensitive)
    all_cols = list(resp.data[0].keys())
    date_col = _find_date_column(all_cols)
    if date_col is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Table '{table_name}' has no 'date' column. "
                f"Columns found: {all_cols}."
            ),
        )

    ticker_cols = [c for c in all_cols if c != date_col]
    if not ticker_cols:
        raise HTTPException(
            status_code=500,
            detail=f"Table '{table_name}' has no ticker columns besides the date column.",
        )

    # Build sorted raw points per ticker, then down-sample
    series: list[TickerSeries] = []
    for ticker in ticker_cols:
        raw_points = _build_date_price_points(resp.data, date_col, ticker)
        sampled = _sample_every_14_days(raw_points)
        if sampled:
            series.append(TickerSeries(ticker=ticker, points=sampled))

    return SectorTop10Response(sector=sector, series=series)
