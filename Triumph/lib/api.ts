const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

// ── Chatbot ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface ChatResponse {
  response: string
}

export interface ChatError {
  error: string
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[] = [],
): Promise<ChatResponse | ChatError> {
  try {
    const res = await fetch(`${BACKEND}/api/chatbot/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
      cache: "no-store",
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      return { error: body.detail ?? `Server error ${res.status}` }
    }
    return await res.json()
  } catch {
    return { error: "Network error — is the backend running on port 8000?" }
  }
}

export type Universe = "sp500" | "dow" | "nasdaq" | "sector_top10"

export interface ChartDataPoint {
  date: string
  value: number
}

export interface ChartSeries {
  key: string
  label: string
  kind: "stock" | "sector_avg_baseline" | "sector_avg_adjusted" | "baseline" | "adjusted"
  points: ChartDataPoint[]
}

export interface ChartDataResponse {
  universe: string
  sector?: string
  series: ChartSeries[]
}

export async function fetchChartData(
  universe: Universe,
  sector: string,
) {
  try {
    const params = new URLSearchParams({
      universe,
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
) {
  try {
    const params = new URLSearchParams({
      graph_type: graphType,
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

export async function fetchTariffProb(
  country: string,
  sector: string,
): Promise<{ probability_percent: number } | null> {
  try {
    const params = new URLSearchParams({
      country,
      sector,
    })

    const res = await fetch(
      `${BACKEND}/api/dashboard/tariff-prob?${params}`,
      { cache: "no-store" },
    )

    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}