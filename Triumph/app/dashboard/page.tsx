"use client"

import { useState } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { ChartAreaInteractive } from '@/components/chart-area-interactive'
import { DataTable } from '@/components/data-table'
import { SectionCards } from '@/components/section-cards'
import { SiteHeader } from '@/components/site-header'
import {
  SidebarInset,
  SidebarProvider,
} from '@/components/ui/sidebar'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  IconWorld,
  IconBuildingFactory2,
  IconMicrophone,
  IconChevronDown,
  IconTrendingUp,
  IconTrendingDown,
  IconChartLine,
  IconX,
} from '@tabler/icons-react'

const COUNTRIES = [
  { code: "CN", name: "China",          flag: "🇨🇳", rate: "145%" },
  { code: "EU", name: "European Union", flag: "🇪🇺", rate: "20%"  },
  { code: "MX", name: "Mexico",         flag: "🇲🇽", rate: "25%"  },
  { code: "CA", name: "Canada",         flag: "🇨🇦", rate: "25%"  },
  { code: "JP", name: "Japan",          flag: "🇯🇵", rate: "24%"  },
  { code: "KR", name: "South Korea",    flag: "🇰🇷", rate: "26%"  },
  { code: "VN", name: "Vietnam",        flag: "🇻🇳", rate: "46%"  },
  { code: "IN", name: "India",          flag: "🇮🇳", rate: "26%"  },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧", rate: "10%"  },
  { code: "TW", name: "Taiwan",         flag: "🇹🇼", rate: "32%"  },
]

const UNIVERSE_OPTIONS = [
  { id: "sp500",        name: "S&P 500"  },
  { id: "dow",          name: "Dow Jones"},
  { id: "nasdaq",       name: "NASDAQ"   },
  { id: "sector_top10", name: "Top 10"   },
]

const SECTORS = [
  { id: "Aerospace",        name: "Aerospace"        },
  { id: "Agriculture",      name: "Agriculture"      },
  { id: "Automotive",       name: "Automotive"       },
  { id: "Energy",           name: "Energy"           },
  { id: "Lumber",           name: "Lumber"           },
  { id: "Maritime",         name: "Maritime"         },
  { id: "Metals",           name: "Metals"           },
  { id: "Minerals",         name: "Minerals"         },
  { id: "Pharmaceuticals",  name: "Pharmaceuticals"  },
  { id: "Steel & Aluminum", name: "Steel & Aluminum" },
]

const MARKETS = [
  { id: "nasdaq", name: "NASDAQ",    value: "17,845.23", change: "+1.24%", up: true,  color: "green"  },
  { id: "sp500",  name: "S&P 500",   value: "5,612.45",  change: "-0.38%", up: false, color: "red"    },
  { id: "dow",    name: "Dow Jones", value: "41,234.67", change: "+0.62%", up: true,  color: "green"  },
  { id: "vix",    name: "VIX",       value: "24.31",     change: "+3.12%", up: true,  color: "orange" },
]

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'elevenlabs-convai': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement> & { 'agent-id'?: string }, HTMLElement>
    }
  }
}

export default function Page() {
  const [sidebarOpen,         setSidebarOpen]         = useState(true)
  const [selectedCountry,     setSelectedCountry]     = useState("CN")
  const [selectedSector,      setSelectedSector]      = useState<string | null>(null)
  const [selectedUniverse,    setSelectedUniverse]    = useState("sp500")
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false)

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
            <div className="@container/main flex flex-1 flex-col">
              <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">

                {/* Section Cards */}
                <SectionCards />

                {/* ── CONTROL TOOLBAR ── */}
                <div className="px-4 lg:px-6 relative z-10">
                  <div className="rounded-xl border border-border/40 bg-card">

                    {/* Row 1: Universe + Country */}
                    <div className="flex items-stretch divide-x divide-border/30">

                      {/* Universe */}
                      <div className="flex flex-col gap-2 px-4 py-3 flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <IconChartLine className="size-3 text-red-500 shrink-0" />
                          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                            Universe
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {UNIVERSE_OPTIONS.map(u => (
                            <button
                              key={u.id}
                              type="button"
                              onClick={() => setSelectedUniverse(u.id)}
                              className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all cursor-pointer ${
                                selectedUniverse === u.id
                                  ? "bg-red-500/20 border-red-500/50 text-red-400"
                                  : "bg-transparent border-border/30 text-muted-foreground hover:border-border/60 hover:text-foreground"
                              }`}
                            >
                              {u.name}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Country */}
                      <div className="flex flex-col gap-2 px-4 py-3 shrink-0">
                        <div className="flex items-center gap-1.5">
                          <IconWorld className="size-3 text-red-500 shrink-0" />
                          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                            Country
                          </span>
                        </div>
                        <div className="relative z-20">
                          <button
                            type="button"
                            onClick={() => setCountryDropdownOpen(p => !p)}
                            className="flex items-center gap-2 px-3 py-1 rounded-lg border border-border/40 bg-muted/10 hover:border-border/60 text-sm font-medium transition-all min-w-44 cursor-pointer"
                          >
                            <span>{activeCountry?.flag}</span>
                            <span className="flex-1 text-left text-xs">{activeCountry?.name}</span>
                            <span className="text-red-400 font-bold text-[10px]">{activeCountry?.rate}</span>
                            <IconChevronDown className={`size-3 text-muted-foreground transition-transform shrink-0 ${countryDropdownOpen ? "rotate-180" : ""}`} />
                          </button>

                          {countryDropdownOpen && (
                            <>
                              {/* backdrop to close */}
                              <div
                                className="fixed inset-0 z-20"
                                onClick={() => setCountryDropdownOpen(false)}
                              />
                              <div className="absolute top-full left-0 mt-1 w-52 rounded-xl border border-border/40 bg-card shadow-xl z-30 overflow-hidden">
                                {COUNTRIES.map(country => (
                                  <button
                                    key={country.code}
                                    type="button"
                                    onClick={() => {
                                      setSelectedCountry(country.code)
                                      setCountryDropdownOpen(false)
                                    }}
                                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs transition-all hover:bg-muted/40 cursor-pointer ${
                                      selectedCountry === country.code
                                        ? "bg-red-500/10 text-red-400"
                                        : "text-foreground"
                                    }`}
                                  >
                                    <span>{country.flag}</span>
                                    <span className="flex-1 text-left">{country.name}</span>
                                    <span className={`font-bold ${selectedCountry === country.code ? "text-red-400" : "text-muted-foreground"}`}>
                                      {country.rate}
                                    </span>
                                  </button>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Divider */}
                    <div className="border-t border-border/20 mx-4" />

                    {/* Row 2: Sector */}
                    <div className="flex items-start gap-3 px-4 py-3">
                      <div className="flex items-center gap-1.5 shrink-0 pt-1">
                        <IconBuildingFactory2 className="size-3 text-red-500" />
                        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                          Sector
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 flex-1">
                        {SECTORS.map(sector => (
                          <button
                            key={sector.id}
                            type="button"
                            onClick={() => setSelectedSector(p => p === sector.id ? null : sector.id)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all cursor-pointer ${
                              selectedSector === sector.id
                                ? "bg-red-500/20 border-red-500/50 text-red-400"
                                : "bg-transparent border-border/30 text-muted-foreground hover:border-border/60 hover:text-foreground"
                            }`}
                          >
                            {sector.name}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Active selection strip */}
                    {selectedSector && (
                      <div className="flex items-center gap-2 px-4 py-2 bg-muted/10 border-t border-border/20">
                        <span className="text-[10px] text-muted-foreground">Viewing:</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 font-medium">
                          {activeCountry?.flag} {activeCountry?.name}
                        </span>
                        <span className="text-[10px] text-muted-foreground">·</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 font-medium">
                          {SECTORS.find(s => s.id === selectedSector)?.name}
                        </span>
                        <button
                          type="button"
                          onClick={() => setSelectedSector(null)}
                          className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                        >
                          <IconX className="size-3" /> Clear
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Chart */}
                <div className="px-4 lg:px-6">
                  {selectedUniverse === 'sector_top10' && !selectedSector ? (
                    <div className="flex flex-col items-center justify-center h-64 rounded-xl border border-border/40 bg-card text-center gap-3">
                      <div className="text-4xl opacity-20">📊</div>
                      <p className="text-sm text-muted-foreground">Select a sector to load the top 10 stocks chart</p>
                      <p className="text-xs text-muted-foreground/50">Use the sector filter above</p>
                    </div>
                  ) : (
                    <ChartAreaInteractive />
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
                        <p className="text-xl font-bold tabular-nums">{market.value}</p>
                        <div className={`flex items-center gap-1 mt-0.5 ${market.up ? "text-green-400" : "text-red-400"}`}>
                          {market.up ? <IconTrendingUp className="size-3" /> : <IconTrendingDown className="size-3" />}
                          <span className="text-xs font-semibold">{market.change}</span>
                          <span className="text-[10px] text-muted-foreground ml-1">today</span>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {/* AI Voice Assistant */}
                <div className="px-4 lg:px-6">
                  <Card className="border border-red-500/20 bg-gradient-to-br from-red-950/20 to-card relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-red-500/5 rounded-full -translate-y-32 translate-x-32 blur-3xl pointer-events-none" />
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
                        Ask your AI advisor about tariff impacts, trade policy, or sector-specific recommendations.
                      </p>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-center py-4">
                        <div className="relative">
                          <div className="absolute inset-0 rounded-full border border-red-500/20 animate-ping scale-150 pointer-events-none" />
                          <elevenlabs-convai agent-id="agent_9701kj0gvhjxegdts9gddt2h4hsv" />
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 justify-center">
                        {["What's the impact on steel?", "Compare China vs EU tariffs", "Recommend trade strategy"].map(s => (
                          <span key={s} className="text-xs px-3 py-1 rounded-full bg-muted/30 border border-border/40 text-muted-foreground">
                            "{s}"
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <DataTable />

              </div>
            </div>
          </div>
        </SidebarInset>
      </div>
      <script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async />
    </SidebarProvider>
  )
}