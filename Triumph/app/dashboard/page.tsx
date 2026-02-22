"use client"

import { useState, useEffect } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { ChartAreaInteractive } from '@/components/chart-area-interactive'
import { DataTable } from '@/components/data-table'
import { SectionCards } from '@/components/section-cards'
import { SiteHeader } from '@/components/site-header'
import tableData from "./data.json"
import {
  SidebarInset,
  SidebarProvider,
} from '@/components/ui/sidebar'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { IconWorld, IconBuildingFactory2, IconMicrophone, IconChevronDown, IconTrendingUp, IconTrendingDown, IconChartLine } from '@tabler/icons-react'
import { fetchTariffProb, fetchIndexGraph, fetchChartData, type ChartDataResponse, type Universe } from '@/lib/api'

const COUNTRIES = [
  { code: "CN", name: "China", flag: "🇨🇳", rate: "145%" },
  { code: "EU", name: "European Union", flag: "🇪🇺", rate: "20%" },
  { code: "MX", name: "Mexico", flag: "🇲🇽", rate: "25%" },
  { code: "CA", name: "Canada", flag: "🇨🇦", rate: "25%" },
  { code: "JP", name: "Japan", flag: "🇯🇵", rate: "24%" },
  { code: "KR", name: "South Korea", flag: "🇰🇷", rate: "26%" },
  { code: "VN", name: "Vietnam", flag: "🇻🇳", rate: "46%" },
  { code: "IN", name: "India", flag: "🇮🇳", rate: "26%" },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧", rate: "10%" },
  { code: "TW", name: "Taiwan", flag: "🇹🇼", rate: "32%" },
]

const UNIVERSE_OPTIONS = [
  { id: "sp500",        name: "S&P 500" },
  { id: "dow",          name: "Dow Jones" },
  { id: "nasdaq",       name: "NASDAQ" },
  { id: "sector_top10", name: "Top 10 Stocks" },
] as const

// Sector IDs are passed directly to the backend API
const SECTORS = [
  { id: "Aerospace",          name: "Aerospace" },
  { id: "Agriculture",        name: "Agriculture" },
  { id: "Automotive",         name: "Automotive" },
  { id: "Energy",             name: "Energy" },
  { id: "Lumber",             name: "Lumber" },
  { id: "Maritime",           name: "Maritime" },
  { id: "Metals",             name: "Metals" },
  { id: "Minerals",           name: "Minerals" },
  { id: "Pharmaceuticals",    name: "Pharmaceuticals" },
  { id: "Steel & Aluminum",   name: "Steel & Aluminum" },
]

const MARKETS = [
  { id: "nasdaq", name: "NASDAQ",    fallback: "17,845.23", change: "+1.24%", up: true,  color: "green"  },
  { id: "sp500",  name: "S&P 500",   fallback: "5,612.45",  change: "-0.38%", up: false, color: "red"    },
  { id: "dow",    name: "Dow Jones", fallback: "41,234.67", change: "+0.62%", up: true,  color: "green"  },
  { id: "vix",    name: "VIX",       fallback: "24.31",     change: "+3.12%", up: true,  color: "orange" },
]

// Maps frontend country codes -> DB country names
const COUNTRY_API_NAMES: Record<string, string> = {
  CN: "CHINA",
  EU: "EUROPEAN UNION",
  MX: "MEXICO",
  CA: "CANADA",
  JP: "JAPAN",
  KR: "SOUTH KOREA",
  VN: "VIETNAM",
  IN: "INDIA",
  GB: "UNITED KINGDOM",
  TW: "TAIWAN",
}


declare global {
  namespace JSX {
    interface IntrinsicElements {
      'elevenlabs-convai': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement> & { 'agent-id'?: string; 'convai-data'?: string }, HTMLElement>
    }
  }
}

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [selectedCountry, setSelectedCountry] = useState<string>("CN")
  const [selectedSector, setSelectedSector] = useState<string | null>(null)
  const [selectedUniverse, setSelectedUniverse] = useState<string>("sp500")
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false)

  // API state
  const [tariffProb, setTariffProb] = useState<number | null>(null)
  const [tariffProbLoading, setTariffProbLoading] = useState(false)
  const [chartData, setChartData] = useState<ChartDataResponse | null>(null)
  const [chartLoading, setChartLoading] = useState(false)
  const [indexPrices, setIndexPrices] = useState<Record<string, number | null>>({
    nasdaq: null,
    sp500: null,
    dow: null,
  })

  // Fetch tariff probability when country + sector change
  useEffect(() => {
    if (!selectedSector) {
      setTariffProb(null)
      return
    }
    const countryApiName = COUNTRY_API_NAMES[selectedCountry]
    if (!countryApiName) return

    setTariffProbLoading(true)
    fetchTariffProb(countryApiName, selectedSector).then(data => {
      setTariffProb(data?.probability_percent ?? null)
      setTariffProbLoading(false)
    })
  }, [selectedCountry, selectedSector])

  // Fetch chart data when universe or sector changes.
  // A sector must always be selected — all index data comes from {Sector}_index tables.
  useEffect(() => {
    if (!selectedSector) {
      setChartData(null)
      setChartLoading(false)
      return
    }
    setChartLoading(true)
    setChartData(null)
    fetchChartData(selectedUniverse as Universe, selectedSector).then(data => {
      setChartData(data)
      setChartLoading(false)
    })
  }, [selectedUniverse, selectedSector])

  // Fetch projected index prices on mount (for market cards)
  useEffect(() => {
    const indices = [
      { type: 'nasdaq'   as const, key: 'nasdaq' },
      { type: 'sp500'    as const, key: 'sp500'  },
      { type: 'dowjones' as const, key: 'dow'    },
    ]
    indices.forEach(({ type, key }) => {
      fetchIndexGraph(type).then(data => {
        if (data?.points?.length) {
          const latest = data.points[data.points.length - 1]
          setIndexPrices(prev => ({ ...prev, [key]: latest.price }))
        }
      })
    })
  }, [])

  const activeCountry = COUNTRIES.find(c => c.code === selectedCountry)

  return (
    <SidebarProvider
      open={sidebarOpen}
      onOpenChange={setSidebarOpen}
      style={{
        "--sidebar-width": "calc(var(--spacing) * 72)",
        "--header-height": "calc(var(--spacing) * 12)",
      } as React.CSSProperties}
    >
      <div className="flex h-screen w-full overflow-hidden">
        {sidebarOpen && <AppSidebar variant="sidebar" />}
        <SidebarInset className="flex flex-col flex-1 min-w-0 overflow-auto">
          <SiteHeader />
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
                <SectionCards tariffProb={tariffProb} tariffProbLoading={tariffProbLoading} />

                {/* Country + Sector controls */}
                <div className="px-4 lg:px-6">
                  <div className="flex flex-col gap-3 p-4 rounded-xl border border-border/40 bg-card">

                      {/* Row 1: Universe */}
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0 w-20">
                        <IconChartLine className="size-3.5 text-red-500" />
                        Universe
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {UNIVERSE_OPTIONS.map(u => (
                          <button
                            key={u.id}
                            onClick={() => setSelectedUniverse(u.id)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                              selectedUniverse === u.id
                                ? "bg-red-500/20 border-red-500/60 text-red-400"
                                : "bg-muted/10 border-border/30 text-muted-foreground hover:border-border hover:text-foreground"
                            }`}
                          >
                            {u.name}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Divider */}
                    <div className="border-t border-border/20" />

                    {/* Row 2: Country dropdown */}
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0 w-20">
                        <IconWorld className="size-3.5 text-red-500" />
                        Country
                      </div>
                      <div className="relative">
                        <button
                          onClick={() => setCountryDropdownOpen(prev => !prev)}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border/40 bg-muted/20 hover:border-border text-sm font-medium transition-all min-w-52"
                        >
                          <span>{activeCountry?.flag}</span>
                          <span className="flex-1 text-left">{activeCountry?.name}</span>
                          <span className="text-red-400 font-bold text-xs">{activeCountry?.rate}</span>
                          <IconChevronDown className={`size-3.5 text-muted-foreground transition-transform ${countryDropdownOpen ? "rotate-180" : ""}`} />
                        </button>
                        {countryDropdownOpen && (
                          <div className="absolute top-full left-0 mt-1 w-56 rounded-xl border border-border/40 bg-card shadow-xl z-20 overflow-hidden">
                            {COUNTRIES.map(country => (
                              <button
                                key={country.code}
                                onClick={() => { setSelectedCountry(country.code); setCountryDropdownOpen(false) }}
                                className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-all hover:bg-muted/40 ${
                                  selectedCountry === country.code ? "bg-red-500/10 text-red-400" : "text-foreground"
                                }`}
                              >
                                <span className="text-base">{country.flag}</span>
                                <span className="flex-1 text-left">{country.name}</span>
                                <span className={`text-xs font-bold ${selectedCountry === country.code ? "text-red-400" : "text-muted-foreground"}`}>
                                  {country.rate}
                                </span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Divider */}
                    <div className="border-t border-border/20" />

                    {/* Row 3: Sector — single select */}
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0 w-20">
                        <IconBuildingFactory2 className="size-3.5 text-red-500" />
                        Sector
                      </div>
                      <div className="grid grid-cols-5 gap-2 flex-1">
                        {SECTORS.map(sector => (
                          <button
                            key={sector.id}
                            onClick={() => setSelectedSector(prev => prev === sector.id ? null : sector.id)}
                            className={`flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                              selectedSector === sector.id
                                ? "bg-red-500/20 border-red-500/60 text-red-400"
                                : "bg-muted/10 border-border/30 text-muted-foreground hover:border-border hover:text-foreground"
                            }`}
                          >
                            <span>{sector.name}</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Selection summary */}
                    {selectedSector && (
                      <div className="flex items-center gap-2 pt-1">
                        <span className="text-[11px] text-muted-foreground">Showing:</span>
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 font-medium">
                          {activeCountry?.flag} {activeCountry?.name}
                        </span>
                        <span className="text-[11px] text-muted-foreground">→</span>
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 font-medium">
                          {SECTORS.find(s => s.id === selectedSector)?.name}
                        </span>
                        {tariffProbLoading && (
                          <span className="text-[11px] text-muted-foreground animate-pulse ml-1">
                            Fetching risk…
                          </span>
                        )}
                        {!tariffProbLoading && tariffProb != null && (
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 font-medium ml-1">
                            {tariffProb.toFixed(1)}% tariff risk
                          </span>
                        )}
                        <button
                          onClick={() => setSelectedSector(null)}
                          className="text-[11px] text-muted-foreground hover:text-foreground ml-auto transition-colors"
                        >
                          Clear
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Chart */}
                <div className="px-4 lg:px-6">
                  {!selectedSector ? (
                    <div className="flex flex-col items-center justify-center h-64 rounded-xl border border-border/40 bg-card text-center gap-3">
                      <div className="text-4xl opacity-30">📊</div>
                      <p className="text-sm text-muted-foreground">Select a sector above to load the chart</p>
                      <p className="text-xs text-muted-foreground/60">
                        Each sector has its own SP500, DOW, and NASDAQ index path
                      </p>
                    </div>
                  ) : (
                    <ChartAreaInteractive
                      data={chartData}
                      loading={chartLoading}
                      country={activeCountry?.name}
                      tariffProb={tariffProb}
                    />
                  )}
                </div>

                {/* Live Markets */}
                <div className="px-4 lg:px-6 grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {MARKETS.map(market => (
                    <Card key={market.id} className="border border-border/40 bg-card relative overflow-hidden">
                      <div
                        className={`absolute top-0 right-0 w-16 h-16 rounded-full blur-2xl pointer-events-none opacity-20 ${
                          market.color === "green" ? "bg-green-500" : market.color === "red" ? "bg-red-500" : "bg-orange-500"
                        }`}
                        style={{ transform: "translate(30%, -30%)" }}
                      />
                      <CardHeader className="pb-1 pt-3 px-4">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-xs font-medium text-muted-foreground">{market.name}</CardTitle>
                          <div className="flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                            <span className="text-[9px] text-green-400 font-medium">LIVE</span>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="px-4 pb-3">
                        <p className="text-xl font-bold tabular-nums">
                          {indexPrices[market.id] != null
                            ? indexPrices[market.id]!.toLocaleString("en-US", { maximumFractionDigits: 2 })
                            : market.fallback}
                        </p>
                        <div className={`flex items-center gap-1 mt-0.5 ${market.up ? "text-green-400" : "text-red-400"}`}>
                          {market.up ? <IconTrendingUp className="size-3" /> : <IconTrendingDown className="size-3" />}
                          <span className="text-xs font-semibold">{market.change}</span>
                          <span className="text-[10px] text-muted-foreground ml-1">today</span>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {/* ElevenLabs AI Voice Assistant */}
                <div className="px-4 lg:px-6">
                  <Card className="border border-red-500/20 bg-gradient-to-br from-red-950/20 to-card relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-red-500/5 rounded-full -translate-y-32 translate-x-32 blur-3xl pointer-events-none" />
                    <div className="absolute bottom-0 left-0 w-48 h-48 bg-red-500/5 rounded-full translate-y-24 -translate-x-24 blur-3xl pointer-events-none" />
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <div className="flex items-center justify-center w-6 h-6 rounded-full bg-red-500/20 border border-red-500/40">
                          <IconMicrophone className="size-3.5 text-red-400" />
                        </div>
                        AI Tariff Advisor
                        <Badge variant="outline" className="ml-2 text-xs border-red-500/30 text-red-400 bg-red-500/10">
                          Voice Enabled
                        </Badge>
                        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                          Live
                        </span>
                      </CardTitle>
                      <p className="text-xs text-muted-foreground mt-1">
                        Ask your AI advisor about tariff impacts, trade policy, or get recommendations for your selected countries and sectors.
                      </p>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-center py-4">
                        <div className="relative">
                          <div className="absolute inset-0 rounded-full border border-red-500/20 animate-ping scale-150 pointer-events-none" />
                          <div className="absolute inset-0 rounded-full border border-red-500/10 animate-ping scale-125 pointer-events-none" />
                          <elevenlabs-convai agent-id="agent_9701kj0gvhjxegdts9gddt2h4hsv" />
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 justify-center">
                        {["What's the impact on steel?", "Compare China vs EU tariffs", "Recommend trade strategy"].map(suggestion => (
                          <span key={suggestion} className="text-xs px-3 py-1 rounded-full bg-muted/30 border border-border/40 text-muted-foreground">
                            "{suggestion}"
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <DataTable data={tableData} />
              </div>
            </div>
          </div>
        </SidebarInset>
      </div>
      <script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async />
    </SidebarProvider>
  )
}
