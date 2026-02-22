"use client"

import * as React from "react"
import {
  CartesianGrid,
  Area,
  AreaChart,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts"

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
  const [animationKey, setAnimationKey] = React.useState(0)

  React.useEffect(() => {
    setAnimationKey((k) => k + 1)
  }, [data])

  const tariffColor =
    tariffProb == null
      ? "#6b7280"
      : tariffProb >= 60
      ? "#ef4444"
      : tariffProb >= 35
      ? "#f97316"
      : "#22c55e"

  const tariffRgb =
    tariffProb == null
      ? "107,114,128"
      : tariffProb >= 60
      ? "239,68,68"
      : tariffProb >= 35
      ? "249,115,22"
      : "34,197,94"

  const tariffLabel =
    tariffProb == null
      ? "—"
      : tariffProb >= 60
      ? "High Exposure"
      : tariffProb >= 35
      ? "Moderate Risk"
      : "Low Risk"

  const tariffBar =
    tariffProb == null ? 0 : Math.min(100, tariffProb)

  if (loading) {
    return (
      <Card className="@container/card border border-white/[0.06] bg-[#0d0d0f]">
        <CardHeader>
          <CardTitle className="text-white/80">Loading chart data…</CardTitle>
          <CardDescription>Fetching projected prices from backend</CardDescription>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
          <div className="flex items-center justify-center h-[320px] text-muted-foreground text-sm">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-t-transparent border-blue-500 animate-spin" />
              <span className="animate-pulse text-xs">Fetching data…</span>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data || data.series.length === 0) {
    return (
      <Card className="@container/card border border-white/[0.06] bg-[#0d0d0f]">
        <CardHeader>
          <CardTitle>No data available</CardTitle>
          <CardDescription>
            Could not load chart data. Check that the backend is running.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
          <div className="flex items-center justify-center h-[320px] text-muted-foreground/50 text-sm">
            No chart data
          </div>
        </CardContent>
      </Card>
    )
  }

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

  const allValues: number[] = []
  for (const row of chartData) {
    for (const [key, val] of Object.entries(row)) {
      if (key !== "date" && typeof val === "number") allValues.push(val)
    }
  }
  const minV = Math.min(...allValues)
  const maxV = Math.max(...allValues)
  const pad = (maxV - minV) * 0.12
  const yDomain: [number, number] = [minV - pad, maxV + pad]

  const stockSeries = data.series.filter((s) => s.kind === "stock")
  const avgBaseline = data.series.find((s) => s.kind === "sector_avg_baseline")
  const avgAdjusted = data.series.find((s) => s.kind === "sector_avg_adjusted")
  const indexBaseline = data.series.find((s) => s.kind === "baseline")
  const indexAdjusted = data.series.find((s) => s.kind === "adjusted")

  const isSectorMode = data.universe === "sector_top10"

  // Find peak value for each key series (for peak reference lines)
  const getPeak = (points: { date: string; value: number }[]) => {
    if (!points.length) return null
    return points.reduce((best, p) => (p.value > best.value ? p : best), points[0])
  }

  const baselinePeak = indexBaseline ? getPeak(indexBaseline.points) : null
  const adjustedPeak = indexAdjusted ? getPeak(indexAdjusted.points) : null
  const avgAdjustedPeak = avgAdjusted ? getPeak(avgAdjusted.points) : null

  // Reference line at midpoint of baseline
  const refSeries = indexBaseline ?? avgBaseline
  const refValue = refSeries
    ? (() => {
        const pts = refSeries.points
        return pts.length ? pts[Math.floor(pts.length / 2)].value : undefined
      })()
    : undefined

  const chartConfig: ChartConfig = {}
  stockSeries.forEach((s) => { chartConfig[s.key] = { label: s.label } })
  if (avgBaseline) chartConfig[avgBaseline.key] = { label: "Sector baseline" }
  if (avgAdjusted) chartConfig[avgAdjusted.key] = { label: "Sector avg adjusted" }
  if (indexBaseline) chartConfig[indexBaseline.key] = { label: "Baseline (no tariff)" }
  if (indexAdjusted) chartConfig[indexAdjusted.key] = { label: "Tariff-adjusted" }

  const universeLabel = isSectorMode
    ? data.sector ?? "Sector"
    : data.sector
      ? `${UNIVERSE_LABELS[data.universe] ?? data.universe} — ${data.sector}`
      : UNIVERSE_LABELS[data.universe] ?? data.universe

  const chartKey = `${animationKey}|${data.universe}|${data.sector ?? ""}|${data.series.map((s) => s.key).join(",")}`

  const LiveDot = (props: any) => {
    const { cx, cy, index, points, dataKey } = props
    const total = points?.length ?? 0
    if (!total || index !== total - 1) return null
    return (
      <g key={`live-${dataKey}`}>
        <circle cx={cx} cy={cy} r={5} fill={props.stroke} opacity={0.9} />
        <circle cx={cx} cy={cy} r={9} fill={props.stroke} opacity={0.2} />
      </g>
    )
  }

  return (
    <Card className="@container/card border border-white/[0.06] bg-[#0d0d0f] relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-32 bg-blue-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-32 bg-green-500/5 rounded-full blur-3xl" />
      </div>

      <CardHeader className="relative z-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-white font-semibold tracking-tight">
              {universeLabel}
              {isSectorMode && " — Top 10 Stocks"}
            </CardTitle>
            <CardDescription className="mt-1 text-white/40 text-xs">
              {country ? `${country} · ` : ""}
              {isSectorMode
                ? "Dashed = sector baseline · Bright = tariff-adjusted"
                : data.sector
                  ? `${data.sector} · Green = baseline · Red = tariff impact`
                  : "Green = no-tariff baseline · Red = tariff-adjusted projection"}
            </CardDescription>
          </div>

          {/* Tariff Risk Widget */}
          {tariffProb != null && (
            <div className="shrink-0 min-w-[140px]">
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <span className="text-[9px] text-white/30 uppercase tracking-widest font-medium">
                  Tariff Risk
                </span>
                <span
                  className="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded"
                  style={{
                    color: tariffColor,
                    backgroundColor: `rgba(${tariffRgb},0.12)`,
                  }}
                >
                  {tariffLabel}
                </span>
              </div>

              {/* Big number */}
              <div className="flex items-end gap-1.5 mb-2">
                <span
                  className="text-4xl font-black tabular-nums leading-none"
                  style={{
                    color: tariffColor,
                    textShadow: `0 0 20px rgba(${tariffRgb},0.8), 0 0 40px rgba(${tariffRgb},0.4)`,
                  }}
                >
                  {tariffProb.toFixed(1)}
                </span>
                <span
                  className="text-lg font-bold mb-0.5"
                  style={{ color: `rgba(${tariffRgb},0.6)` }}
                >
                  %
                </span>
              </div>

              {/* Progress bar */}
              <div className="relative h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
                  style={{
                    width: `${tariffBar}%`,
                    backgroundColor: tariffColor,
                    boxShadow: `0 0 8px 1px rgba(${tariffRgb},0.7)`,
                  }}
                />
              </div>

              {/* Tick marks */}
              <div className="flex justify-between mt-1">
                {[0, 35, 60, 100].map((tick) => (
                  <span key={tick} className="text-[8px] text-white/20 font-mono">
                    {tick}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="px-2 pt-2 sm:px-6 relative z-10">
        <ChartContainer
          key={chartKey}
          config={chartConfig}
          className="aspect-auto h-[320px] w-full"
        >
          <AreaChart data={chartData} margin={{ left: 8, right: 8, top: 8, bottom: 4 }}>
            <defs>
              <linearGradient id="greenFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3}>
                  <animate attributeName="stopOpacity" values="0.3;0.18;0.3" dur="3s" repeatCount="indefinite" />
                </stop>
                <stop offset="100%" stopColor="#22c55e" stopOpacity={0.01} />
              </linearGradient>

              <linearGradient id="redFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.28}>
                  <animate attributeName="stopOpacity" values="0.28;0.14;0.28" dur="3.5s" repeatCount="indefinite" />
                </stop>
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0.01} />
              </linearGradient>

              <linearGradient id="whiteFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.01} />
              </linearGradient>

              <linearGradient id="stockFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.06} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={10}
              minTickGap={48}
              tick={{ fill: "rgba(255,255,255,0.25)", fontSize: 11, fontFamily: "monospace" }}
              tickFormatter={(v) =>
                new Date(v).toLocaleDateString("en-US", { month: "short", day: "numeric" })
              }
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              domain={yDomain}
              tick={{ fill: "rgba(255,255,255,0.25)", fontSize: 11, fontFamily: "monospace" }}
              tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
              width={60}
            />

            {/* Mid reference line */}
            {refValue !== undefined && (
              <ReferenceLine
                y={refValue}
                stroke="rgba(255,255,255,0.08)"
                strokeDasharray="4 4"
                label={{
                  value: `$${refValue.toFixed(0)}`,
                  position: "insideTopRight",
                  fill: "rgba(255,255,255,0.2)",
                  fontSize: 10,
                  fontFamily: "monospace",
                }}
              />
            )}

            {/* Peak reference line — green baseline peak */}
            {baselinePeak && (
              <ReferenceLine
                y={baselinePeak.value}
                stroke="rgba(34,197,94,0.5)"
                strokeDasharray="3 3"
                strokeWidth={1.5}
                label={{
                  value: `⬆ Peak $${baselinePeak.value.toFixed(0)}`,
                  position: "insideTopLeft",
                  fill: "rgba(34,197,94,0.7)",
                  fontSize: 10,
                  fontFamily: "monospace",
                }}
              />
            )}

            {/* Peak reference line — red adjusted peak */}
            {adjustedPeak && adjustedPeak.value !== baselinePeak?.value && (
              <ReferenceLine
                y={adjustedPeak.value}
                stroke="rgba(239,68,68,0.5)"
                strokeDasharray="3 3"
                strokeWidth={1.5}
                label={{
                  value: `⬆ Peak $${adjustedPeak.value.toFixed(0)}`,
                  position: "insideTopRight",
                  fill: "rgba(239,68,68,0.7)",
                  fontSize: 10,
                  fontFamily: "monospace",
                }}
              />
            )}

            {/* Peak reference line — purple avg adjusted peak */}
            {avgAdjustedPeak && (
              <ReferenceLine
                y={avgAdjustedPeak.value}
                stroke="rgba(167,139,250,0.5)"
                strokeDasharray="3 3"
                strokeWidth={1.5}
                label={{
                  value: `⬆ Peak $${avgAdjustedPeak.value.toFixed(0)}`,
                  position: "insideTopLeft",
                  fill: "rgba(167,139,250,0.7)",
                  fontSize: 10,
                  fontFamily: "monospace",
                }}
              />
            )}

            <ChartTooltip
              cursor={{ stroke: "rgba(255,255,255,0.08)", strokeWidth: 1 }}
              content={
                <ChartTooltipContent
                  className="bg-[#141416] border border-white/10 shadow-2xl rounded-xl text-xs font-mono"
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

            {/* Stock lines */}
            {stockSeries.map((s) => (
              <Area
                key={s.key}
                dataKey={s.key}
                stroke="rgba(99,130,255,0.35)"
                strokeWidth={1}
                fill="url(#stockFill)"
                dot={false}
                activeDot={{ r: 3, fill: "#6382ff", strokeWidth: 0 }}
                type="monotone"
                connectNulls
                isAnimationActive={true}
                animationDuration={800}
                animationEasing="ease-out"
              />
            ))}

            {/* Sector avg baseline */}
            {avgBaseline && (
              <Area
                key={avgBaseline.key}
                dataKey={avgBaseline.key}
                stroke="rgba(156,163,175,0.5)"
                strokeWidth={1}
                strokeDasharray="5 4"
                fill="none"
                dot={false}
                type="monotone"
                connectNulls
                isAnimationActive={true}
                animationDuration={900}
              />
            )}

            {/* Sector avg adjusted — purple glow */}
            {avgAdjusted && (
              <Area
                key={avgAdjusted.key}
                dataKey={avgAdjusted.key}
                stroke="#a78bfa"
                strokeWidth={3}
                fill="url(#whiteFill)"
                dot={<LiveDot stroke="#a78bfa" />}
                activeDot={{ r: 5, fill: "#a78bfa", strokeWidth: 0 }}
                type="monotone"
                connectNulls
                isAnimationActive={true}
                animationDuration={1000}
                style={{ filter: "drop-shadow(0 0 6px rgba(167,139,250,0.7))" }}
              />
            )}

            {/* Index baseline — green glow */}
            {indexBaseline && (
              <Area
                key={indexBaseline.key}
                dataKey={indexBaseline.key}
                stroke="#22c55e"
                strokeWidth={2.5}
                fill="url(#greenFill)"
                dot={<LiveDot stroke="#22c55e" />}
                activeDot={{ r: 5, fill: "#22c55e", strokeWidth: 0 }}
                type="monotone"
                connectNulls
                isAnimationActive={true}
                animationDuration={1000}
                animationEasing="ease-out"
                style={{ filter: "drop-shadow(0 0 8px rgba(34,197,94,0.8))" }}
              />
            )}

            {/* Index adjusted — red glow */}
            {indexAdjusted && (
              <Area
                key={indexAdjusted.key}
                dataKey={indexAdjusted.key}
                stroke="#ef4444"
                strokeWidth={2.5}
                strokeDasharray="6 3"
                fill="url(#redFill)"
                dot={<LiveDot stroke="#ef4444" />}
                activeDot={{ r: 5, fill: "#ef4444", strokeWidth: 0 }}
                type="monotone"
                connectNulls
                isAnimationActive={true}
                animationDuration={1200}
                animationEasing="ease-out"
                style={{ filter: "drop-shadow(0 0 8px rgba(239,68,68,0.8))" }}
              />
            )}
          </AreaChart>
        </ChartContainer>

        {/* Legend */}
        <div className="flex items-center gap-4 mt-3 px-1 flex-wrap">
          {indexBaseline && (
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 rounded-full bg-green-500" style={{ boxShadow: "0 0 6px rgba(34,197,94,0.8)" }} />
              <span className="text-[10px] text-white/40 font-mono">Baseline</span>
            </div>
          )}
          {indexAdjusted && (
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 rounded-full bg-red-500" style={{ boxShadow: "0 0 6px rgba(239,68,68,0.8)" }} />
              <span className="text-[10px] text-white/40 font-mono">Tariff-adjusted</span>
            </div>
          )}
          {avgAdjusted && (
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 rounded-full bg-violet-400" style={{ boxShadow: "0 0 6px rgba(167,139,250,0.8)" }} />
              <span className="text-[10px] text-white/40 font-mono">Sector avg</span>
            </div>
          )}
          {stockSeries.length > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-0.5 rounded-full bg-blue-400/50" />
              <span className="text-[10px] text-white/40 font-mono">Individual stocks</span>
            </div>
          )}
          {(baselinePeak || adjustedPeak) && (
            <div className="flex items-center gap-1.5 ml-auto">
              <div className="w-3 h-px bg-white/20" style={{ borderTop: "1px dashed rgba(255,255,255,0.3)" }} />
              <span className="text-[10px] text-white/25 font-mono">— peak shock</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}