"use client"

import * as React from "react"
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type UniqueIdentifier,
} from "@dnd-kit/core"
import { restrictToVerticalAxis } from "@dnd-kit/modifiers"
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import {
  IconArrowUp,
  IconArrowDown,
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconChevronsLeft,
  IconChevronsRight,
  IconDotsVertical,
  IconGripVertical,
  IconLayoutColumns,
  IconLoader,
  IconTrendingDown,
  IconTrendingUp,
} from "@tabler/icons-react"
import {
  ColumnDef,
  ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  Row,
  SortingState,
  useReactTable,
  VisibilityState,
} from "@tanstack/react-table"
import {
  Area,
  AreaChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { z } from "zod"
import { createClient } from "@/supabase/client"

import { useIsMobile } from '@/hooks/use-mobile'
import { Button } from '@/components/ui/button'
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerTrigger,
} from '@/components/ui/drawer'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent } from '@/components/ui/tabs'

const SECTOR_TABLES = [
  { id: 1,  header: "Aerospace",         tableName: "Aerospace_top10",     accent: "#6366f1" },
  { id: 2,  header: "Agriculture",       tableName: "Agriculture_top10",     accent: "#22c55e" },
  { id: 3,  header: "Automotive",        tableName: "Automotive_top10",     accent: "#f59e0b" },
  { id: 4,  header: "Energy",            tableName: "Energy_top10",       accent: "#eab308" },
  { id: 5,  header: "Lumber",            tableName: "Lumber_top10",     accent: "#a16207" },
  { id: 6,  header: "Maritime",          tableName: "Maritime_top10",       accent: "#0ea5e9" },
  { id: 7,  header: "Metals",            tableName: "Metals_top10",      accent: "#94a3b8" },
  { id: 8,  header: "Minerals",          tableName: "Minerals_top10",       accent: "#a855f7" },
  { id: 9,  header: "Pharmaceuticals",   tableName: "Pharmaceuticals_top10", accent: "#ec4899" },
  { id: 10, header: "Steel & Aluminum",  tableName: "Steel_aluminum_top10",  accent: "#64748b" },
]

export const schema = z.object({
  id: z.number(),
  header: z.string(),
  tableName: z.string(),
  icon: z.string(),
  accent: z.string(),
})

type SectorRow = z.infer<typeof schema>

type ChartDataPoint = {
  date: string
  baseline_price: number
  impacted_price: number
}

type SectorStats = {
  topCompany: string
  avgBaseline: number
  avgImpacted: number
  pctChange: number
  maxImpacted: number
  minBaseline: number
  volatility: number
}

// Cache so we don't re-fetch when rows re-render
const statsCache: Record<string, { stats: SectorStats; chartData: ChartDataPoint[] }> = {}

function useSectorStats(tableName: string) {
  const [stats, setStats] = React.useState<SectorStats | null>(statsCache[tableName]?.stats ?? null)
  const [chartData, setChartData] = React.useState<ChartDataPoint[]>(statsCache[tableName]?.chartData ?? [])
  const [loading, setLoading] = React.useState(!statsCache[tableName])

  React.useEffect(() => {
    if (statsCache[tableName]) return
    const supabase = createClient()
    async function fetch() {
      setLoading(true)
      const { data } = await supabase
        .from(tableName)
        .select("date, baseline_price, impacted_price, ticker")
        .order("date", { ascending: true })

      if (!data) { setLoading(false); return }

      const tickerCount: Record<string, number> = {}
      for (const row of data) {
        if (row.ticker) tickerCount[row.ticker] = (tickerCount[row.ticker] ?? 0) + 1
      }
      const top = Object.entries(tickerCount).sort((a, b) => b[1] - a[1])[0]

      const formatted: ChartDataPoint[] = data.map(row => ({
        date: row.date ? new Date(row.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "",
        baseline_price: Number(row.baseline_price),
        impacted_price: Number(row.impacted_price),
      }))

      const avgB = formatted.reduce((s, r) => s + r.baseline_price, 0) / formatted.length
      const avgI = formatted.reduce((s, r) => s + r.impacted_price, 0) / formatted.length
      const maxI = Math.max(...formatted.map(r => r.impacted_price))
      const minB = Math.min(...formatted.map(r => r.baseline_price))
      const diffs = formatted.map(r => r.impacted_price - r.baseline_price)
      const meanDiff = diffs.reduce((a, b) => a + b, 0) / diffs.length
      const variance = diffs.reduce((s, d) => s + Math.pow(d - meanDiff, 2), 0) / diffs.length
      const volatility = Math.sqrt(variance)

      const result = {
        stats: {
          topCompany: top ? top[0] : "N/A",
          avgBaseline: avgB,
          avgImpacted: avgI,
          pctChange: ((avgI - avgB) / avgB) * 100,
          maxImpacted: maxI,
          minBaseline: minB,
          volatility,
        },
        chartData: formatted,
      }
      statsCache[tableName] = result
      setStats(result.stats)
      setChartData(result.chartData)
      setLoading(false)
    }
    fetch()
  }, [tableName])

  return { stats, chartData, loading }
}

function DragHandle({ id }: { id: number }) {
  const { attributes, listeners } = useSortable({ id })
  return (
    <Button {...attributes} {...listeners} variant="ghost" size="icon" className="text-muted-foreground size-7 hover:bg-transparent">
      <IconGripVertical className="text-muted-foreground size-3" />
      <span className="sr-only">Drag to reorder</span>
    </Button>
  )
}

function SectorDrawerContent({ item }: { item: SectorRow }) {
  const isMobile = useIsMobile()
  const { stats, chartData, loading } = useSectorStats(item.tableName)

  const combinedConfig = {
    baseline_price: { label: "Baseline Price", color: item.accent },
    impacted_price: { label: "Impacted Price", color: "#ef4444" },
  } satisfies ChartConfig

  const pctUp = (stats?.pctChange ?? 0) >= 0

  return (
    <>
      <DrawerHeader className="gap-2 border-b pb-4" style={{ borderColor: `${item.accent}30` }}>
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl text-xl shrink-0"
            style={{ background: `${item.accent}20`, border: `1px solid ${item.accent}40` }}>
            {item.icon}
          </div>
          <div className="flex-1 min-w-0">
            <DrawerTitle className="text-lg">{item.header} Sector</DrawerTitle>
            <DrawerDescription>
              {loading ? "Loading..." : `Lead company: ${stats?.topCompany}`}
            </DrawerDescription>
          </div>
          {!loading && stats && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-bold border shrink-0 ${
              pctUp ? "bg-red-500/10 border-red-500/30 text-red-400" : "bg-green-500/10 border-green-500/30 text-green-400"
            }`}>
              {pctUp ? <IconTrendingUp className="size-3.5" /> : <IconTrendingDown className="size-3.5" />}
              {pctUp ? "+" : ""}{stats.pctChange.toFixed(1)}%
            </div>
          )}
        </div>
      </DrawerHeader>

      <div className="flex flex-col gap-5 overflow-y-auto px-4 py-4 text-sm">
        {loading ? (
          <div className="flex items-center justify-center h-48 text-muted-foreground">
            <IconLoader className="animate-spin mr-2" /> Loading sector data...
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-muted-foreground">No data available</div>
        ) : (
          <>
            {/* Combined chart */}
            {!isMobile && (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold">Baseline vs Tariff-Impacted Price</p>
                    <p className="text-xs text-muted-foreground">Price trajectory comparison over time</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 rounded-full inline-block" style={{ background: item.accent }} />
                      Baseline
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 rounded-full bg-red-500 inline-block" />
                      Impacted
                    </span>
                  </div>
                </div>

                <ChartContainer config={combinedConfig} className="h-56 w-full">
                  <AreaChart data={chartData} margin={{ left: 0, right: 10 }}>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={8} tick={{ fontSize: 10 }} />
                    <YAxis tickLine={false} axisLine={false} tickMargin={8} width={65} tick={{ fontSize: 10 }} />
                    <ChartTooltip content={<ChartTooltipContent indicator="dot" />} />
                    <defs>
                      <linearGradient id={`grad-b-${item.id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={item.accent} stopOpacity={0.25} />
                        <stop offset="95%" stopColor={item.accent} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id={`grad-i-${item.id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area dataKey="baseline_price" type="monotone" fill={`url(#grad-b-${item.id})`} stroke={item.accent} strokeWidth={2} dot={false} />
                    <Area dataKey="impacted_price" type="monotone" fill={`url(#grad-i-${item.id})`} stroke="#ef4444" strokeWidth={2} dot={false} />
                  </AreaChart>
                </ChartContainer>

                <Separator />

                {/* Description */}
                <div className="rounded-xl p-4 text-xs leading-relaxed text-muted-foreground" style={{ background: `${item.accent}08`, border: `1px solid ${item.accent}20` }}>
                  <p className="font-semibold mb-1" style={{ color: item.accent }}>What's happening?</p>
                  The <strong className="text-foreground">{item.header}</strong> sector shows an average tariff-driven price increase of{" "}
                  <strong className={pctUp ? "text-red-400" : "text-green-400"}>
                    {pctUp ? "+" : ""}{stats?.pctChange.toFixed(1)}%
                  </strong>{" "}
                  over the baseline. The lead company by data volume is <strong className="text-foreground">{stats?.topCompany}</strong>.{" "}
                  {pctUp
                    ? `Tariff exposure is pushing costs up with a spread volatility of $${stats?.volatility.toFixed(2)}, indicating ${stats!.volatility > 10 ? "high" : "moderate"} price instability.`
                    : "Tariffs appear to have limited pricing impact in this sector, suggesting strong supply chain resilience or domestic sourcing."
                  }
                </div>

                <Separator />
              </>
            )}

            {/* Metrics grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border p-3 flex flex-col gap-1" style={{ borderColor: `${item.accent}30`, background: `${item.accent}06` }}>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Avg Baseline</p>
                <p className="text-lg font-bold" style={{ color: item.accent }}>${stats?.avgBaseline.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">Pre-tariff avg</p>
              </div>
              <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-3 flex flex-col gap-1">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Avg Impacted</p>
                <p className="text-lg font-bold text-red-400">${stats?.avgImpacted.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">Post-tariff avg</p>
              </div>
              <div className="rounded-xl border border-border/40 p-3 flex flex-col gap-1">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Peak Impacted</p>
                <p className="text-base font-bold">${stats?.maxImpacted.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">Highest recorded</p>
              </div>
              <div className="rounded-xl border border-border/40 p-3 flex flex-col gap-1">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Spread Volatility</p>
                <p className="text-base font-bold">${stats?.volatility.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">Std dev of gap</p>
              </div>
            </div>
          </>
        )}
      </div>

      <DrawerFooter>
        <DrawerClose asChild>
          <Button variant="outline">Close</Button>
        </DrawerClose>
      </DrawerFooter>
    </>
  )
}

function TableCellViewer({ item }: { item: SectorRow }) {
  const isMobile = useIsMobile()
  return (
    <Drawer direction={isMobile ? "bottom" : "right"}>
      <DrawerTrigger asChild>
        <Button variant="link" className="text-foreground w-fit px-0 text-left font-semibold gap-2">
          <span className="text-base">{item.icon}</span>
          {item.header}
        </Button>
      </DrawerTrigger>
      <DrawerContent>
        <SectorDrawerContent item={item} />
      </DrawerContent>
    </Drawer>
  )
}

function TopCompanyCell({ item }: { item: SectorRow }) {
  const { stats, loading } = useSectorStats(item.tableName)
  if (loading) return <span className="text-muted-foreground text-xs animate-pulse">Loading...</span>
  return (
    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md" style={{ background: `${item.accent}15`, color: item.accent }}>
      {stats?.topCompany ?? "N/A"}
    </span>
  )
}

function PriceChangeCell({ item }: { item: SectorRow }) {
  const { stats, loading } = useSectorStats(item.tableName)
  if (loading) return <span className="text-muted-foreground text-xs animate-pulse">—</span>
  if (!stats) return <span className="text-muted-foreground text-xs">N/A</span>
  const up = stats.pctChange >= 0
  return (
    <div className={`flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-md w-fit ${
      up ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"
    }`}>
      {up ? <IconTrendingUp className="size-3" /> : <IconTrendingDown className="size-3" />}
      {up ? "+" : ""}{stats.pctChange.toFixed(1)}%
    </div>
  )
}

type SortOrder = "none" | "asc" | "desc"

const columns: ColumnDef<SectorRow>[] = [
  {
    id: "drag",
    header: () => null,
    cell: ({ row }) => <DragHandle id={row.original.id} />,
  },
  {
    accessorKey: "header",
    header: "Sector",
    cell: ({ row }) => <TableCellViewer item={row.original} />,
    enableHiding: false,
  },
  {
    id: "topCompany",
    header: "Lead Company",
    cell: ({ row }) => <TopCompanyCell item={row.original} />,
  },
  {
    id: "priceChange",
    header: "Tariff Impact",
    cell: ({ row }) => <PriceChangeCell item={row.original} />,
  },
  {
    id: "status",
    header: "Status",
    cell: () => (
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs text-green-400 font-medium">Live</span>
      </div>
    ),
  },
  {
    id: "actions",
    cell: () => (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="data-[state=open]:bg-muted text-muted-foreground flex size-8" size="icon">
            <IconDotsVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-32">
          <DropdownMenuItem>View Data</DropdownMenuItem>
          <DropdownMenuItem>Export</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive">Remove</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
  },
]

function DraggableRow({ row }: { row: Row<SectorRow> }) {
  const { transform, transition, setNodeRef, isDragging } = useSortable({ id: row.original.id })
  return (
    <TableRow
      data-state={row.getIsSelected() && "selected"}
      data-dragging={isDragging}
      ref={setNodeRef}
      className="relative z-0 data-[dragging=true]:z-10 data-[dragging=true]:opacity-80"
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      {row.getVisibleCells().map((cell) => (
        <TableCell key={cell.id}>
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </TableCell>
      ))}
    </TableRow>
  )
}

export function DataTable() {
  const [data, setData] = React.useState<SectorRow[]>(SECTOR_TABLES)
  const [sortOrder, setSortOrder] = React.useState<SortOrder>("none")
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pagination, setPagination] = React.useState({ pageIndex: 0, pageSize: 10 })
  const sortableId = React.useId()
  const sensors = useSensors(
    useSensor(MouseSensor, {}),
    useSensor(TouchSensor, {}),
    useSensor(KeyboardSensor, {})
  )

  // Sort data by pctChange using cached stats
  const sortedData = React.useMemo(() => {
    if (sortOrder === "none") return data
    return [...data].sort((a, b) => {
      const sa = statsCache[a.tableName]?.stats?.pctChange ?? 0
      const sb = statsCache[b.tableName]?.stats?.pctChange ?? 0
      return sortOrder === "asc" ? sa - sb : sb - sa
    })
  }, [data, sortOrder])

  const dataIds = React.useMemo<UniqueIdentifier[]>(() => sortedData.map(({ id }) => id), [sortedData])

  const table = useReactTable({
    data: sortedData,
    columns,
    state: { sorting, columnVisibility, columnFilters, pagination },
    getRowId: (row) => row.id.toString(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
  })

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (active && over && active.id !== over.id) {
      setData((data) => {
        const oldIndex = data.findIndex(d => d.id === active.id)
        const newIndex = data.findIndex(d => d.id === over.id)
        return arrayMove(data, oldIndex, newIndex)
      })
    }
  }

  function cycleSortOrder() {
    setSortOrder(prev => prev === "none" ? "desc" : prev === "desc" ? "asc" : "none")
  }

  return (
    <Tabs defaultValue="outline" className="w-full flex-col justify-start gap-6">
      <div className="flex items-center justify-between px-4 lg:px-6">
        <div>
          <h2 className="text-sm font-semibold">Sector Analysis</h2>
          <p className="text-xs text-muted-foreground">Click any sector to view detailed price impact</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Sort button */}
          <Button
            variant="outline"
            size="sm"
            onClick={cycleSortOrder}
            className={`gap-1.5 ${sortOrder !== "none" ? "border-red-500/40 text-red-400 bg-red-500/5" : ""}`}
          >
            {sortOrder === "none" && <><IconArrowUp className="size-3 opacity-40" /><IconArrowDown className="size-3 opacity-40" /> Sort by Impact</>}
            {sortOrder === "desc" && <><IconArrowDown className="size-3" /> Highest First</>}
            {sortOrder === "asc" && <><IconArrowUp className="size-3" /> Lowest First</>}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <IconLayoutColumns />
                <span className="hidden lg:inline">Columns</span>
                <IconChevronDown />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {table.getAllColumns().filter(c => typeof c.accessorFn !== "undefined" && c.getCanHide()).map((column) => (
                <DropdownMenuCheckboxItem
                  key={column.id}
                  className="capitalize"
                  checked={column.getIsVisible()}
                  onCheckedChange={(value) => column.toggleVisibility(!!value)}
                >
                  {column.id}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <TabsContent value="outline" className="relative flex flex-col gap-4 overflow-auto px-4 lg:px-6">
        <div className="overflow-hidden rounded-lg border border-border/40">
          <DndContext
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis]}
            onDragEnd={handleDragEnd}
            sensors={sensors}
            id={sortableId}
          >
            <Table>
              <TableHeader className="bg-muted/50 sticky top-0 z-10">
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id} colSpan={header.colSpan}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows?.length ? (
                  <SortableContext items={dataIds} strategy={verticalListSortingStrategy}>
                    {table.getRowModel().rows.map((row) => (
                      <DraggableRow key={row.id} row={row} />
                    ))}
                  </SortableContext>
                ) : (
                  <TableRow>
                    <TableCell colSpan={columns.length} className="h-24 text-center">No results.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </DndContext>
        </div>

        <div className="flex items-center justify-between px-2">
          <p className="text-xs text-muted-foreground">
            {sortOrder !== "none" && `Sorted by tariff impact — ${sortOrder === "desc" ? "highest" : "lowest"} first`}
          </p>
          <div className="flex items-center gap-2 ml-auto">
            <Button variant="outline" className="hidden h-8 w-8 p-0 lg:flex" onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()}>
              <IconChevronsLeft />
            </Button>
            <Button variant="outline" className="size-8" size="icon" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
              <IconChevronLeft />
            </Button>
            <span className="text-xs text-muted-foreground">Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}</span>
            <Button variant="outline" className="size-8" size="icon" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
              <IconChevronRight />
            </Button>
            <Button variant="outline" className="hidden size-8 lg:flex" size="icon" onClick={() => table.setPageIndex(table.getPageCount() - 1)} disabled={!table.getCanNextPage()}>
              <IconChevronsRight />
            </Button>
          </div>
        </div>
      </TabsContent>
    </Tabs>
  )
}