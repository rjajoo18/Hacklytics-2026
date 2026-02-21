"use client"

import { useState } from 'react'
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
import { IconWorld, IconBuildingFactory2, IconPlus, IconX, IconMicrophone } from '@tabler/icons-react'

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

const SECTORS = [
  { id: "steel", name: "Steel & Aluminum", icon: "⚙️" },
  { id: "semis", name: "Semiconductors", icon: "💾" },
  { id: "auto", name: "Automotive", icon: "🚗" },
  { id: "pharma", name: "Pharmaceuticals", icon: "💊" },
  { id: "agri", name: "Agriculture", icon: "🌾" },
  { id: "textiles", name: "Textiles", icon: "🧵" },
  { id: "energy", name: "Energy", icon: "⚡" },
  { id: "consumer", name: "Consumer Goods", icon: "📦" },
]

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'elevenlabs-convai': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement> & { 'agent-id'?: string; 'convai-data'?: string }, HTMLElement>
    }
  }
}

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [selectedCountries, setSelectedCountries] = useState<string[]>(["CN", "EU"])
  const [selectedSectors, setSelectedSectors] = useState<string[]>(["steel", "semis"])
  const [tariffNote, setTariffNote] = useState("")
  const [notes, setNotes] = useState<{ id: number; text: string; country: string; sector: string }[]>([])

  const toggleCountry = (code: string) => {
    setSelectedCountries(prev =>
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    )
  }

  const toggleSector = (id: string) => {
    setSelectedSectors(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  const addNote = () => {
    if (!tariffNote.trim()) return
    setNotes(prev => [...prev, {
      id: Date.now(),
      text: tariffNote,
      country: selectedCountries.map(c => COUNTRIES.find(x => x.code === c)?.name).join(", ") || "All",
      sector: selectedSectors.map(s => SECTORS.find(x => x.id === s)?.name).join(", ") || "All",
    }])
    setTariffNote("")
  }

  const removeNote = (id: number) => {
    setNotes(prev => prev.filter(n => n.id !== id))
  }

  return (
    <SidebarProvider
      open={sidebarOpen}
      onOpenChange={setSidebarOpen}
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <div className="flex h-screen w-full overflow-hidden">
        {sidebarOpen && <AppSidebar variant="sidebar" />}
        <SidebarInset className="flex flex-col flex-1 min-w-0 overflow-auto">
          <SiteHeader />
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
                <SectionCards />
                <div className="px-4 lg:px-6">
                  <ChartAreaInteractive />
                </div>

                {/* Country & Sector Selection */}
                <div className="px-4 lg:px-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Card className="border border-border/40 bg-card">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <IconWorld className="size-4 text-red-500" />
                        Target Countries
                        <Badge variant="outline" className="ml-auto text-xs">{selectedCountries.length} selected</Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        {COUNTRIES.map(country => (
                          <button
                            key={country.code}
                            onClick={() => toggleCountry(country.code)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                              selectedCountries.includes(country.code)
                                ? "bg-red-500/20 border-red-500/60 text-red-400"
                                : "bg-muted/30 border-border/40 text-muted-foreground hover:border-border hover:text-foreground"
                            }`}
                          >
                            <span>{country.flag}</span>
                            <span>{country.name}</span>
                            <span className={`font-bold ${selectedCountries.includes(country.code) ? "text-red-400" : "text-muted-foreground"}`}>
                              {country.rate}
                            </span>
                          </button>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border border-border/40 bg-card">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <IconBuildingFactory2 className="size-4 text-red-500" />
                        Affected Sectors
                        <Badge variant="outline" className="ml-auto text-xs">{selectedSectors.length} selected</Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        {SECTORS.map(sector => (
                          <button
                            key={sector.id}
                            onClick={() => toggleSector(sector.id)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                              selectedSectors.includes(sector.id)
                                ? "bg-red-500/20 border-red-500/60 text-red-400"
                                : "bg-muted/30 border-border/40 text-muted-foreground hover:border-border hover:text-foreground"
                            }`}
                          >
                            <span>{sector.icon}</span>
                            <span>{sector.name}</span>
                          </button>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Policy Notes */}
                <div className="px-4 lg:px-6">
                  <Card className="border border-border/40 bg-card">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <IconPlus className="size-4 text-red-500" />
                        Policy Notes
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-3">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={tariffNote}
                          onChange={e => setTariffNote(e.target.value)}
                          onKeyDown={e => e.key === "Enter" && addNote()}
                          placeholder={`Add a note for ${selectedCountries.length ? selectedCountries.map(c => COUNTRIES.find(x => x.code === c)?.flag).join(" ") : "selected countries"}...`}
                          className="flex-1 bg-muted/30 border border-border/40 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/20"
                        />
                        <button
                          onClick={addNote}
                          className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-400 text-sm font-medium rounded-lg transition-all flex items-center gap-1.5"
                        >
                          <IconPlus className="size-3.5" />
                          Add
                        </button>
                      </div>
                      {notes.length === 0 ? (
                        <p className="text-xs text-muted-foreground text-center py-4">
                          No policy notes yet. Select countries and sectors above, then add a note.
                        </p>
                      ) : (
                        <div className="flex flex-col gap-2">
                          {notes.map(note => (
                            <div key={note.id} className="flex items-start gap-3 p-3 rounded-lg bg-muted/20 border border-border/30">
                              <div className="flex-1">
                                <p className="text-sm text-foreground">{note.text}</p>
                                <div className="flex gap-2 mt-1.5 flex-wrap">
                                  <span className="text-xs text-muted-foreground">🌍 {note.country}</span>
                                  <span className="text-xs text-muted-foreground">•</span>
                                  <span className="text-xs text-muted-foreground">⚙️ {note.sector}</span>
                                </div>
                              </div>
                              <button onClick={() => removeNote(note.id)} className="text-muted-foreground hover:text-red-400 transition-colors mt-0.5">
                                <IconX className="size-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* ElevenLabs AI Voice Assistant */}
                <div className="px-4 lg:px-6">
                  <Card className="border border-red-500/20 bg-gradient-to-br from-red-950/20 to-card relative overflow-hidden">
                    {/* Decorative glow */}
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
                          {/* Animated ring behind widget */}
                          <div className="absolute inset-0 rounded-full border border-red-500/20 animate-ping scale-150 pointer-events-none" />
                          <div className="absolute inset-0 rounded-full border border-red-500/10 animate-ping scale-125 delay-150 pointer-events-none" />
                          <elevenlabs-convai agent-id="agent_9701kj0gvhjxegdts9gddt2h4hsv" />
                        </div>
                      </div>

                      <div className="mt-2 flex flex-wrap gap-2 justify-center">
                        {["What's the impact on steel?", "Compare China vs EU tariffs", "Recommend trade strategy"].map(suggestion => (
                          <span
                            key={suggestion}
                            className="text-xs px-3 py-1 rounded-full bg-muted/30 border border-border/40 text-muted-foreground"
                          >
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

      {/* ElevenLabs script */}
      <script src="https://unpkg.com/@elevenlabs/convai-widget-embed" async />
    </SidebarProvider>
  )
}