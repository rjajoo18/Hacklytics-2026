"use client"

import * as React from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import type { ChartDataResponse } from "@/lib/api"

const UNIVERSE_LABELS: Record<string, string> = {
  sp500: "S&P 500",
  dow: "Dow Jones",
  nasdaq: "NASDAQ",
  sector_top10: "Sector Top 10",
}

interface ChartAreaInteractiveProps {
  data?: ChartDataResponse | null
  loading?: boolean
  country?: string
  tariffProb?: number | null
}

export function ChartAreaInteractive({
  data,
  loading,
  country,
  tariffProb,
}: ChartAreaInteractiveProps) {
  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <Card className="@container/card">
        <CardHeader>
          <CardTitle>Loading chart data…</CardTitle>
          <CardDescription>Fetching projected prices from backend</CardDescription>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
          <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm animate-pulse">
            Fetching data…
          </div>
        </CardContent>
      </Card>
    )
  }

  // ── No data ───────────────────────────────────────────────────────────────
  if (!data || data.series.length === 0) {
    return (
      <Card className="@container/card">
        <CardHeader>
          <CardTitle>No data available</CardTitle>
          <CardDescription>
            Could not load chart data. Check that the backend is running.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
          <div className="flex items-center justify-center h-[300px] text-muted-foreground/50 text-sm">
            No chart data
          </div>
        </CardContent>
      </Card>
    )
  }

  // ── Pivot to wide-format for Recharts ─────────────────────────────────────
  const allDates = new Set<string>()
  for (const series of data.series) {
    for (const point of series.points) allDates.add(point.date)
  }

  const lookup: Record<string, Record<string, number>> = {}
  for (const series of data.series) {
    lookup[series.key] = {}
    for (const point of series.points) lookup[series.key][point.date] = point.value
  }

  const chartData = Array.from(allDates)
    .sort()
    .map((date) => {
      const row: Record<string, number | string> = { date }
      for (const series of data.series) {
        const v = lookup[series.key][date]
        if (v !== undefined) row[series.key] = v
      }
      return row
    })

  // ── Y-axis domain ─────────────────────────────────────────────────────────
  const allValues: number[] = []
  for (const row of chartData) {
    for (const [key, val] of Object.entries(row)) {
      if (key !== "date" && typeof val === "number") allValues.push(val)
    }
  }
  const minV = Math.min(...allValues)
  const maxV = Math.max(...allValues)
  const pad = (maxV - minV) * 0.1
  const yDomain: [number, number] = [minV - pad, maxV + pad]

  // ── Series buckets ────────────────────────────────────────────────────────
  const stockSeries = data.series.filter((s) => s.kind === "stock")
  const avgBaseline = data.series.find((s) => s.kind === "sector_avg_baseline")
  const avgAdjusted = data.series.find((s) => s.kind === "sector_avg_adjusted")
  const indexBaseline = data.series.find((s) => s.kind === "baseline")
  const indexAdjusted = data.series.find((s) => s.kind === "adjusted")

  const isSectorMode = data.universe === "sector_top10"

  // ── ChartConfig (only used for tooltip labels) ────────────────────────────
  const chartConfig: ChartConfig = {}

  // stocks: no colors, just labels
  stockSeries.forEach((s) => {
    chartConfig[s.key] = { label: s.label }
  })

  if (avgBaseline) chartConfig[avgBaseline.key] = { label: "Sector baseline" }
  if (avgAdjusted) chartConfig[avgAdjusted.key] = { label: "Sector avg adjusted" }
  if (indexBaseline) chartConfig[indexBaseline.key] = { label: "Baseline (no tariff)" }
  if (indexAdjusted) chartConfig[indexAdjusted.key] = { label: "Tariff-adjusted" }

  // For index universes with a sector selected, append the sector name so
  // users know they're viewing sector-specific (not global) index data.
  const universeLabel = isSectorMode
    ? data.sector ?? "Sector"
    : data.sector
      ? `${UNIVERSE_LABELS[data.universe] ?? data.universe} — ${data.sector}`
      : UNIVERSE_LABELS[data.universe] ?? data.universe

  const chartKey = `${data.universe}|${data.sector ?? ""}|${data.series
    .map((s) => s.key)
    .join(",")}`

  return (
    <Card className="@container/card">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>
              {universeLabel}
              {isSectorMode && " — Top 10 Stocks"}
            </CardTitle>
            <CardDescription className="mt-1">
              {country ? `${country} tariff scenario · ` : ""}
              {isSectorMode
                ? "Gray dashed = sector baseline · Bold white = tariff-adjusted avg"
                : data.sector
                  ? `${data.sector} sector impact · Solid = baseline · Dashed = tariff-adjusted`
                  : "Solid = baseline (no tariff) · Dashed = tariff-adjusted"}
            </CardDescription>
          </div>

          {tariffProb != null && (
            <div className="shrink-0 text-right">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Tariff Risk
              </p>
              <p
                className={`text-2xl font-bold tabular-nums leading-tight ${
                  tariffProb >= 60
                    ? "text-red-400"
                    : tariffProb >= 35
                      ? "text-orange-400"
                      : "text-yellow-400"
                }`}
              >
                {tariffProb.toFixed(1)}%
              </p>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="px-2 pt-2 sm:px-6">
        <ChartContainer
          key={chartKey}
          config={chartConfig}
          className="aspect-auto h-[300px] w-full"
        >
          <LineChart data={chartData} margin={{ left: 8, right: 8 }}>
            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={40}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
              tickFormatter={(v) =>
                new Date(v).toLocaleDateString("en-US", { month: "short", day: "numeric" })
              }
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              domain={yDomain}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
              tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
              width={58}
            />

            <ChartTooltip
              cursor={{ stroke: "rgba(255,255,255,0.1)", strokeWidth: 1 }}
              content={
                <ChartTooltipContent
                  labelFormatter={(v) =>
                    new Date(v).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })
                  }
                  formatter={(value, name) => {
                    const key = String(name)
                    if (key === "sector_avg_baseline") return null
                    const cfg = chartConfig[key]
                    if (!cfg) return null
                    return [`$${Number(value).toFixed(2)}`, cfg.label]
                  }}
                  indicator="line"
                />
              }
            />

            {/* Individual stock lines — neutral */}
            {stockSeries.map((s) => (
              <Line
                key={s.key}
                dataKey={s.key}
                stroke="rgba(255,255,255,0.30)"
                strokeWidth={1.5}
                dot={false}
                type="monotone"
                connectNulls
                isAnimationActive={false}
              />
            ))}

            {/* Sector avg baseline — thin dashed gray */}
            {avgBaseline && (
              <Line
                key={avgBaseline.key}
                dataKey={avgBaseline.key}
                stroke="#9ca3af"
                strokeWidth={1}
                strokeDasharray="5 4"
                dot={false}
                type="monotone"
                connectNulls
                isAnimationActive={false}
              />
            )}

            {/* Sector avg adjusted — thick bold near-white */}
            {avgAdjusted && (
              <Line
                key={avgAdjusted.key}
                dataKey={avgAdjusted.key}
                stroke="#f1f5f9"
                strokeWidth={3.5}
                dot={false}
                type="monotone"
                connectNulls
                isAnimationActive={false}
              />
            )}

            {/* Index baseline — solid slate */}
            {indexBaseline && (
              <Line
                key={indexBaseline.key}
                dataKey={indexBaseline.key}
                stroke="#94a3b8"
                strokeWidth={2}
                dot={false}
                type="monotone"
                connectNulls
                isAnimationActive={false}
              />
            )}

            {/* Index adjusted — dashed orange */}
            {indexAdjusted && (
              <Line
                key={indexAdjusted.key}
                dataKey={indexAdjusted.key}
                stroke="#f97316"
                strokeWidth={2.5}
                strokeDasharray="6 3"
                dot={false}
                type="monotone"
                connectNulls
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}