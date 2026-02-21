"use client"

import * as React from "react"
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts"

import { useIsMobile } from '@/hooks/use-mobile'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ToggleGroup,
  ToggleGroupItem,
} from '@/components/ui/toggle-group'

const chartData = [
  { date: "2024-04-01", imports: 222, exports: 150 },
  { date: "2024-04-02", imports: 97, exports: 180 },
  { date: "2024-04-03", imports: 167, exports: 120 },
  { date: "2024-04-04", imports: 242, exports: 260 },
  { date: "2024-04-05", imports: 373, exports: 290 },
  { date: "2024-04-06", imports: 301, exports: 340 },
  { date: "2024-04-07", imports: 245, exports: 180 },
  { date: "2024-04-08", imports: 409, exports: 320 },
  { date: "2024-04-09", imports: 59, exports: 110 },
  { date: "2024-04-10", imports: 261, exports: 190 },
  { date: "2024-04-11", imports: 327, exports: 350 },
  { date: "2024-04-12", imports: 292, exports: 210 },
  { date: "2024-04-13", imports: 342, exports: 380 },
  { date: "2024-04-14", imports: 137, exports: 220 },
  { date: "2024-04-15", imports: 120, exports: 170 },
  { date: "2024-04-16", imports: 138, exports: 190 },
  { date: "2024-04-17", imports: 446, exports: 360 },
  { date: "2024-04-18", imports: 364, exports: 410 },
  { date: "2024-04-19", imports: 243, exports: 180 },
  { date: "2024-04-20", imports: 89, exports: 150 },
  { date: "2024-04-21", imports: 137, exports: 200 },
  { date: "2024-04-22", imports: 224, exports: 170 },
  { date: "2024-04-23", imports: 138, exports: 230 },
  { date: "2024-04-24", imports: 387, exports: 290 },
  { date: "2024-04-25", imports: 215, exports: 250 },
  { date: "2024-04-26", imports: 75, exports: 130 },
  { date: "2024-04-27", imports: 383, exports: 420 },
  { date: "2024-04-28", imports: 122, exports: 180 },
  { date: "2024-04-29", imports: 315, exports: 240 },
  { date: "2024-04-30", imports: 454, exports: 380 },
  { date: "2024-05-01", imports: 165, exports: 220 },
  { date: "2024-05-02", imports: 293, exports: 310 },
  { date: "2024-05-03", imports: 247, exports: 190 },
  { date: "2024-05-04", imports: 385, exports: 420 },
  { date: "2024-05-05", imports: 481, exports: 390 },
  { date: "2024-05-06", imports: 498, exports: 520 },
  { date: "2024-05-07", imports: 388, exports: 300 },
  { date: "2024-05-08", imports: 149, exports: 210 },
  { date: "2024-05-09", imports: 227, exports: 180 },
  { date: "2024-05-10", imports: 293, exports: 330 },
  { date: "2024-05-11", imports: 335, exports: 270 },
  { date: "2024-05-12", imports: 197, exports: 240 },
  { date: "2024-05-13", imports: 197, exports: 160 },
  { date: "2024-05-14", imports: 448, exports: 490 },
  { date: "2024-05-15", imports: 473, exports: 380 },
  { date: "2024-05-16", imports: 338, exports: 400 },
  { date: "2024-05-17", imports: 499, exports: 420 },
  { date: "2024-05-18", imports: 315, exports: 350 },
  { date: "2024-05-19", imports: 235, exports: 180 },
  { date: "2024-05-20", imports: 177, exports: 230 },
  { date: "2024-05-21", imports: 82, exports: 140 },
  { date: "2024-05-22", imports: 81, exports: 120 },
  { date: "2024-05-23", imports: 252, exports: 290 },
  { date: "2024-05-24", imports: 294, exports: 220 },
  { date: "2024-05-25", imports: 201, exports: 250 },
  { date: "2024-05-26", imports: 213, exports: 170 },
  { date: "2024-05-27", imports: 420, exports: 460 },
  { date: "2024-05-28", imports: 233, exports: 190 },
  { date: "2024-05-29", imports: 78, exports: 130 },
  { date: "2024-05-30", imports: 340, exports: 280 },
  { date: "2024-05-31", imports: 178, exports: 230 },
  { date: "2024-06-01", imports: 178, exports: 200 },
  { date: "2024-06-02", imports: 470, exports: 410 },
  { date: "2024-06-03", imports: 103, exports: 160 },
  { date: "2024-06-04", imports: 439, exports: 380 },
  { date: "2024-06-05", imports: 88, exports: 140 },
  { date: "2024-06-06", imports: 294, exports: 250 },
  { date: "2024-06-07", imports: 323, exports: 370 },
  { date: "2024-06-08", imports: 385, exports: 320 },
  { date: "2024-06-09", imports: 438, exports: 480 },
  { date: "2024-06-10", imports: 155, exports: 200 },
  { date: "2024-06-11", imports: 92, exports: 150 },
  { date: "2024-06-12", imports: 492, exports: 420 },
  { date: "2024-06-13", imports: 81, exports: 130 },
  { date: "2024-06-14", imports: 426, exports: 380 },
  { date: "2024-06-15", imports: 307, exports: 350 },
  { date: "2024-06-16", imports: 371, exports: 310 },
  { date: "2024-06-17", imports: 475, exports: 520 },
  { date: "2024-06-18", imports: 107, exports: 170 },
  { date: "2024-06-19", imports: 341, exports: 290 },
  { date: "2024-06-20", imports: 408, exports: 450 },
  { date: "2024-06-21", imports: 169, exports: 210 },
  { date: "2024-06-22", imports: 317, exports: 270 },
  { date: "2024-06-23", imports: 480, exports: 530 },
  { date: "2024-06-24", imports: 132, exports: 180 },
  { date: "2024-06-25", imports: 141, exports: 190 },
  { date: "2024-06-26", imports: 434, exports: 380 },
  { date: "2024-06-27", imports: 448, exports: 490 },
  { date: "2024-06-28", imports: 149, exports: 200 },
  { date: "2024-06-29", imports: 103, exports: 160 },
  { date: "2024-06-30", imports: 446, exports: 400 },
]

const chartConfig = {
  imports: {
    label: "Tariffed Imports",
    color: "#ef4444",
  },
  exports: {
    label: "US Exports",
    color: "#22c55e",
  },
} satisfies ChartConfig

export function ChartAreaInteractive() {
  const isMobile = useIsMobile()
  const [timeRange, setTimeRange] = React.useState("90d")

  React.useEffect(() => {
    if (isMobile) {
      setTimeRange("7d")
    }
  }, [isMobile])

  const filteredData = chartData.filter((item) => {
    const date = new Date(item.date)
    const referenceDate = new Date("2024-06-30")
    let daysToSubtract = 90
    if (timeRange === "30d") {
      daysToSubtract = 30
    } else if (timeRange === "7d") {
      daysToSubtract = 7
    }
    const startDate = new Date(referenceDate)
    startDate.setDate(startDate.getDate() - daysToSubtract)
    return date >= startDate
  })

  return (
    <Card className="@container/card">
      <CardHeader>
        <CardTitle>Trade Flow Under Tariffs</CardTitle>
        <CardDescription>
          <span className="hidden @[540px]/card:block">
            Tariffed imports (red) vs US exports (green) — last 3 months
          </span>
          <span className="@[540px]/card:hidden">Imports vs Exports</span>
        </CardDescription>
        <CardAction>
          <ToggleGroup
            type="single"
            value={timeRange}
            onValueChange={setTimeRange}
            variant="outline"
            className="hidden *:data-[slot=toggle-group-item]:!px-4 @[767px]/card:flex"
          >
            <ToggleGroupItem value="90d">Last 3 months</ToggleGroupItem>
            <ToggleGroupItem value="30d">Last 30 days</ToggleGroupItem>
            <ToggleGroupItem value="7d">Last 7 days</ToggleGroupItem>
          </ToggleGroup>
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger
              className="flex w-40 **:data-[slot=select-value]:block **:data-[slot=select-value]:truncate @[767px]/card:hidden"
              size="sm"
              aria-label="Select a value"
            >
              <SelectValue placeholder="Last 3 months" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="90d" className="rounded-lg">Last 3 months</SelectItem>
              <SelectItem value="30d" className="rounded-lg">Last 30 days</SelectItem>
              <SelectItem value="7d" className="rounded-lg">Last 7 days</SelectItem>
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        <ChartContainer
          config={chartConfig}
          className="aspect-auto h-[250px] w-full"
        >
          <AreaChart data={filteredData}>
            <defs>
              <linearGradient id="fillImports" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="fillExports" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={32}
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 12 }}
              tickFormatter={(value) => {
                const date = new Date(value)
                return date.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })
              }}
            />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  labelFormatter={(value) => {
                    return new Date(value).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })
                  }}
                  indicator="dot"
                />
              }
            />
            <Area
              dataKey="exports"
              type="natural"
              fill="url(#fillExports)"
              stroke="#22c55e"
              strokeWidth={2}
              stackId="a"
            />
            <Area
              dataKey="imports"
              type="natural"
              fill="url(#fillImports)"
              stroke="#ef4444"
              strokeWidth={2}
              stackId="a"
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}