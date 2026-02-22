"""
Pydantic response models shared across routers.
"""

from pydantic import BaseModel


# ── Dashboard: tariff probability ────────────────────────────────────────────

class TariffProbResponse(BaseModel):
    country: str
    sector: str
    probability_percent: float


# ── Dashboard: index line graphs (Nasdaq / S&P 500 / Dow Jones) ───────────────

class DatePricePoint(BaseModel):
    date: str    # "YYYY-MM-DD"
    price: float
    baseline_price: float | None = None


class IndexGraphResponse(BaseModel):
    graph_type: str
    points: list[DatePricePoint]


# ── Dashboard: sector top-10 stock graphs ────────────────────────────────────

class TickerSeries(BaseModel):
    ticker: str
    points: list[DatePricePoint]


class SectorTop10Response(BaseModel):
    sector: str
    series: list[TickerSeries]   # one entry per stock / ticker


# ── Map page ─────────────────────────────────────────────────────────────────

class SectorProbability(BaseModel):
    sector: str
    probability_percent: float


class CountrySectorsResponse(BaseModel):
    country: str
    sectors: list[SectorProbability]


# ── Dashboard: unified chart-data endpoint ───────────────────────────────────

class SeriesPoint(BaseModel):
    date: str    # "YYYY-MM-DD"
    value: float


class ChartSeries(BaseModel):
    key: str    # unique dataKey used by Recharts
    label: str  # human-readable label
    kind: str   # "baseline" | "adjusted" | "sector_avg_baseline" | "sector_avg_adjusted" | "stock"
    points: list[SeriesPoint]


class ChartDataResponse(BaseModel):
    universe: str
    sector: str | None = None
    series: list[ChartSeries]
