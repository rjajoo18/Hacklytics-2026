const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

export type Universe = "sp500" | "dow" | "nasdaq" | "sector_top10"

export async function fetchChartData(
  universe: Universe,
  country: string,
  sector: string,
) {
  try {
    const params = new URLSearchParams({
      universe,
      country,
      sector,
    })

    const res = await fetch(
      `${BACKEND}/api/dashboard/chart-data?${params}`,
      { cache: "no-store" },
    )

    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export async function fetchIndexGraph(
  graphType: "nasdaq" | "sp500" | "dowjones",
  country: string,
  sector: string,
) {
  try {
    const params = new URLSearchParams({
      graph_type: graphType,
      country,
      sector,
    })

    const res = await fetch(
      `${BACKEND}/api/dashboard/graph?${params}`,
      { cache: "no-store" },
    )

    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export async function fetchSectorTop10(
  country: string,
  sector: string,
) {
  try {
    const params = new URLSearchParams({
      graph_type: "top10_sector_stocks",
      country,
      sector,
    })

    const res = await fetch(
      `${BACKEND}/api/dashboard/graph?${params}`,
      { cache: "no-store" },
    )

    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}