/**
 * Typed fetch helpers for the FastAPI backend (http://localhost:8000).
 * All functions return null on any error — callers handle the fallback.
 *
 * Override the URL with NEXT_PUBLIC_BACKEND_URL in .env.local.
 */

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

// ── Shared types ──────────────────────────────────────────────────────────────

export type DatePrice = {
  date: string          // "YYYY-MM-DD"
  price: number         // impacted_price (with tariff effect)
  baseline_price?: number  // pre-tariff baseline (sector top-10 only)
}

export type TariffProbResponse = {
  country: string
  sector: string
  probability_percent: number
}

export type IndexGraphResponse = {
  graph_type: string
  points: DatePrice[]
}

export type TickerSeries = {
  ticker: string
  points: DatePrice[]
}

export type SectorTop10Response = {
  sector: string
  series: TickerSeries[]
}

export type CountrySectorsResponse = {
  country: string
  sectors: { sector: string; probability_percent: number }[]
}

// ── Chart-data endpoint ────────────────────────────────────────────────────────

export type SeriesPoint = {
  date: string
  value: number
}

export type SeriesKind =
  | 'baseline'
  | 'adjusted'
  | 'sector_avg_baseline'
  | 'sector_avg_adjusted'
  | 'stock'

export type ChartSeries = {
  key: string
  label: string
  kind: SeriesKind
  points: SeriesPoint[]
}

export type Universe = 'sp500' | 'dow' | 'nasdaq' | 'sector_top10'

export type ChartDataResponse = {
  universe: string
  sector: string | null
  series: ChartSeries[]
}

// ── Fetch helpers ─────────────────────────────────────────────────────────────

/** GET /api/dashboard/tariff-prob */
export async function fetchTariffProb(
  country: string,
  sector: string,
): Promise<TariffProbResponse | null> {
  try {
    const res = await fetch(
      `${BACKEND}/api/dashboard/tariff-prob` +
        `?country=${encodeURIComponent(country)}&sector=${encodeURIComponent(sector)}`,
      { cache: "no-store" },
    )
    if (!res.ok) return null
    return (await res.json()) as TariffProbResponse
  } catch {
    return null
  }
}

/** GET /api/dashboard/graph  (index variant: nasdaq | sp500 | dowjones) */
export async function fetchIndexGraph(
  graphType: "nasdaq" | "sp500" | "dowjones",
): Promise<IndexGraphResponse | null> {
  try {
    const res = await fetch(
      `${BACKEND}/api/dashboard/graph?graph_type=${graphType}`,
      { cache: "no-store" },
    )
    if (!res.ok) return null
    return (await res.json()) as IndexGraphResponse
  } catch {
    return null
  }
}

/** GET /api/dashboard/graph  (sector top-10 variant) */
export async function fetchSectorTop10(
  sector: string,
): Promise<SectorTop10Response | null> {
  try {
    const res = await fetch(
      `${BACKEND}/api/dashboard/graph` +
        `?graph_type=top10_sector_stocks&sector=${encodeURIComponent(sector)}`,
      { cache: "no-store" },
    )
    if (!res.ok) return null
    return (await res.json()) as SectorTop10Response
  } catch {
    return null
  }
}

/** GET /api/dashboard/chart-data */
export async function fetchChartData(
  universe: Universe,
  sector?: string,
): Promise<ChartDataResponse | null> {
  try {
    const params = new URLSearchParams({ universe })
    if (sector) params.set('sector', sector)
    const res = await fetch(
      `${BACKEND}/api/dashboard/chart-data?${params}`,
      { cache: 'no-store' },
    )
    if (!res.ok) return null
    return (await res.json()) as ChartDataResponse
  } catch {
    return null
  }
}

/** GET /api/map/country-sectors */
export async function fetchCountrySectors(
  country: string,
): Promise<CountrySectorsResponse | null> {
  try {
    const res = await fetch(
      `${BACKEND}/api/map/country-sectors?country=${encodeURIComponent(country)}`,
      { cache: "no-store" },
    )
    if (!res.ok) return null
    return (await res.json()) as CountrySectorsResponse
  } catch {
    return null
  }
}
