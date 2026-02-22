"use client"

import { useState, useMemo } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { SiteHeader } from '@/components/site-header'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { IconWorld } from '@tabler/icons-react'

type TariffRow = {
  country: string
  tariff_risk_pct: string
}

type SectorRow = {
  country: string
  sector: string
  tariff_risk_prob: number
}

interface Props {
  tariffData: TariffRow[]
  sectorData: SectorRow[]
}

const NAME_TO_CODE: Record<string, string> = {
  "china": "CN",
  "european union": "EU",
  "eu": "EU",
  "mexico": "MX",
  "canada": "CA",
  "japan": "JP",
  "south korea": "KR",
  "korea, republic of": "KR",
  "vietnam": "VN",
  "india": "IN",
  "united kingdom": "GB",
  "uk": "GB",
  "taiwan": "TW",
  "brazil": "BR",
  "australia": "AU",
  "russia": "RU",
  "russian federation": "RU",
  "saudi arabia": "SA",
  "south africa": "ZA",
  "turkey": "TR",
  "indonesia": "ID",
  "thailand": "TH",
  "philippines": "PH",
  "malaysia": "MY",
  "singapore": "SG",
  "switzerland": "CH",
  "argentina": "AR",
  "nigeria": "NG",
}

const SECTOR_ICONS: Record<string, string> = {
  "semiconductors": "💾",
  "steel & aluminum": "⚙️",
  "textiles": "🧵",
  "consumer goods": "📦",
  "automotive": "🚗",
  "agriculture": "🌾",
  "pharmaceuticals": "💊",
  "energy": "⚡",
}

function formatRate(val: string | number): string {
  if (typeof val === "string") return val
  const pct = val < 1 ? val * 100 : val
  return `${Math.round(pct)}%`
}

const COUNTRIES = [
  { code: "CN", name: "China", flag: "🇨🇳", zoom: "4/35/105" },
  { code: "EU", name: "EU", flag: "🇪🇺", zoom: "4/51/10" },
  { code: "MX", name: "Mexico", flag: "🇲🇽", zoom: "4/24/-102" },
  { code: "CA", name: "Canada", flag: "🇨🇦", zoom: "3/60/-96" },
  { code: "JP", name: "Japan", flag: "🇯🇵", zoom: "5/36/138" },
  { code: "KR", name: "S. Korea", flag: "🇰🇷", zoom: "6/36/128" },
  { code: "VN", name: "Vietnam", flag: "🇻🇳", zoom: "5/16/108" },
  { code: "IN", name: "India", flag: "🇮🇳", zoom: "4/21/79" },
  { code: "GB", name: "UK", flag: "🇬🇧", zoom: "5/55/-3" },
  { code: "TW", name: "Taiwan", flag: "🇹🇼", zoom: "7/24/121" },
  { code: "BR", name: "Brazil", flag: "🇧🇷", zoom: "4/-10/-55" },
  { code: "AU", name: "Australia", flag: "🇦🇺", zoom: "4/-25/134" },
  { code: "RU", name: "Russia", flag: "🇷🇺", zoom: "3/62/90" },
  { code: "SA", name: "Saudi Arabia", flag: "🇸🇦", zoom: "5/24/45" },
  { code: "ZA", name: "S. Africa", flag: "🇿🇦", zoom: "5/-29/25" },
  { code: "TR", name: "Turkey", flag: "🇹🇷", zoom: "6/39/35" },
  { code: "ID", name: "Indonesia", flag: "🇮🇩", zoom: "5/-2/118" },
  { code: "TH", name: "Thailand", flag: "🇹🇭", zoom: "6/13/101" },
  { code: "PH", name: "Philippines", flag: "🇵🇭", zoom: "6/13/122" },
  { code: "MY", name: "Malaysia", flag: "🇲🇾", zoom: "6/4/109" },
  { code: "SG", name: "Singapore", flag: "🇸🇬", zoom: "8/1/104" },
  { code: "CH", name: "Switzerland", flag: "🇨🇭", zoom: "7/47/8" },
  { code: "AR", name: "Argentina", flag: "🇦🇷", zoom: "4/-34/-64" },
  { code: "NG", name: "Nigeria", flag: "🇳🇬", zoom: "5/9/8" },
]

const STATUS_COLORS = {
  critical: { bar: "bg-red-500",    text: "text-red-400",    dot: "bg-red-500" },
  high:     { bar: "bg-orange-500", text: "text-orange-400", dot: "bg-orange-500" },
  medium:   { bar: "bg-yellow-500", text: "text-yellow-400", dot: "bg-yellow-500" },
  low:      { bar: "bg-green-500",  text: "text-green-400",  dot: "bg-green-500" },
}

const MAP_BASE = `https://api.mapbox.com/styles/v1/shashankshaga/cmkrizwmr002n01r9govs70ma.html?title=false&access_token=pk.eyJ1Ijoic2hhc2hhbmtzaGFnYSIsImEiOiJjbWtyOTNlNXAwdnhtM2RweTZsd3lyZW9sIn0.2fQFrzvDoCmWxqsMftdCTA&zoomwheel=false`

const glassStyle: React.CSSProperties = {
  background: "rgba(8, 8, 12, 0.62)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
}

export default function GlobalView({ tariffData, sectorData }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mapCountry, setMapCountry] = useState<string | null>(null)

  const rateByCode = useMemo(() => {
    const map: Record<string, string> = {}
    for (const row of tariffData) {
      const code = NAME_TO_CODE[row.country.toLowerCase().trim()]
      if (code) map[code] = formatRate(row.tariff_risk_pct)
    }
    return map
  }, [tariffData])

  const dynamicSectorImpacts = useMemo(() => {
    const map: Record<string, { sector: string; icon: string; impact: number; change: string; status: "critical" | "high" | "medium" | "low" }[]> = {}
    for (const row of sectorData) {
      const code = NAME_TO_CODE[row.country.toLowerCase().trim()]
      if (!code) continue
      if (!map[code]) map[code] = []

      const impact = Math.round(row.tariff_risk_prob * 100)
      const status =
        impact >= 80 ? "critical" :
        impact >= 60 ? "high" :
        impact >= 40 ? "medium" : "low"

      const icon = SECTOR_ICONS[row.sector.toLowerCase()] ?? "📊"

      map[code].push({
        sector: row.sector,
        icon,
        impact,
        change: `${impact}%`,
        status,
      })
    }
    for (const code of Object.keys(map)) {
      map[code].sort((a, b) => b.impact - a.impact)
    }
    return map
  }, [sectorData])

  const selectedCountryData = COUNTRIES.find(c => c.code === mapCountry)
  const sectors = mapCountry ? dynamicSectorImpacts[mapCountry] ?? null : null

  const mapSrc = selectedCountryData
    ? `${MAP_BASE}#${selectedCountryData.zoom}`
    : `${MAP_BASE}#0.4/0/0`

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
        <SidebarInset className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <SiteHeader />

          <div className="relative flex-1 overflow-hidden">
            <iframe
              key={mapSrc}
              width="100%"
              height="100%"
              src={mapSrc}
              title="Tariff Map"
              style={{ border: "none", display: "block", position: "absolute", inset: 0 }}
            />

            {/* Country pill selector */}
            <div className="absolute top-4 left-0 right-0 z-10 flex justify-center px-4">
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-2xl border border-white/10 overflow-x-auto"
                style={{ ...glassStyle, maxWidth: "100%", scrollbarWidth: "none" }}
              >
                <div className="flex items-center gap-1 text-[10px] font-semibold text-white/40 uppercase tracking-wider pr-2 border-r border-white/10 shrink-0">
                  <IconWorld className="size-3 text-red-500" />
                  Focus
                </div>
                {COUNTRIES.map(country => (
                  <button
                    key={country.code}
                    onClick={() => setMapCountry(prev => prev === country.code ? null : country.code)}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-all shrink-0 ${
                      mapCountry === country.code
                        ? "bg-red-500/30 border-red-500/70 text-red-300"
                        : "bg-white/5 border-white/10 text-white/50 hover:text-white/80 hover:border-white/25"
                    }`}
                  >
                    <span>{country.flag}</span>
                    <span>{country.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Tariff rate card */}
            {selectedCountryData && (
              <div
                className="absolute top-20 left-4 z-10 flex items-center gap-3 px-4 py-3 rounded-2xl border border-white/10"
                style={glassStyle}
              >
                <span className="text-3xl">{selectedCountryData.flag}</span>
                <div>
                  <p className="text-[10px] text-white/40 font-medium uppercase tracking-wider">{selectedCountryData.name}</p>
                  <p className="text-2xl font-bold text-red-400 leading-tight">
                    {rateByCode[selectedCountryData.code] ?? "N/A"}
                  </p>
                  <p className="text-[10px] text-white/30">US Tariff Rate</p>
                </div>
              </div>
            )}

            {/* Sector impact panel */}
            {selectedCountryData && sectors && (
              <div
                className="absolute bottom-4 left-4 z-10 rounded-2xl border border-white/10 w-80"
                style={glassStyle}
              >
                <div className="px-4 pt-3 pb-2 border-b border-white/5 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-white/80">Sector Impact</p>
                    <p className="text-[10px] text-white/30">Tariff severity by industry</p>
                  </div>
                  <button
                    onClick={() => setMapCountry(null)}
                    className="text-[10px] text-white/30 hover:text-white/60 transition-colors px-2 py-0.5 rounded-full border border-white/10 hover:border-white/20"
                  >
                    reset
                  </button>
                </div>
                <div className="p-3 grid grid-cols-1 gap-2">
                  {sectors.map(s => {
                    const colors = STATUS_COLORS[s.status]
                    return (
                      <div key={s.sector} className="flex items-center gap-2">
                        <span className="text-sm w-5 text-center shrink-0">{s.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-[11px] font-medium text-white/65 truncate">{s.sector}</span>
                            <span className={`text-[10px] font-bold ml-2 shrink-0 ${colors.text}`}>{s.change}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <div className="flex-1 h-1 bg-white/8 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${colors.bar}`} style={{ width: `${s.impact}%` }} />
                            </div>
                            <span className={`text-[9px] font-semibold w-6 text-right shrink-0 ${colors.text}`}>{s.impact}%</span>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Default hint */}
            {!mapCountry && (
              <div
                className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 px-5 py-2.5 rounded-full border border-white/10 flex items-center gap-2 whitespace-nowrap"
                style={glassStyle}
              >
                <IconWorld className="size-3.5 text-red-400" />
                <p className="text-xs text-white/40">Select a country above to zoom in and view sector impact</p>
              </div>
            )}
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}