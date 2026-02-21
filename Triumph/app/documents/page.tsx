"use client"

import { useState } from 'react'
import { AppSidebar } from '@/components/app-sidebar'
import { SiteHeader } from '@/components/site-header'
import {
  SidebarInset,
  SidebarProvider,
} from '@/components/ui/sidebar'
import {
  IconFileText,
  IconWorld,
  IconBuildingBank,
  IconChartBar,
  IconSearch,
  IconExternalLink,
  IconX,
  IconCalendar,
  IconTag,
  IconNews,
  IconScale,
  IconBuildingFactory2,
  IconCurrencyDollar,
} from '@tabler/icons-react'

const CATEGORIES = ["All", "Policy", "Trade Data", "Research", "News", "Legal"]

type Doc = {
  id: number
  title: string
  description: string
  category: string
  date: string
  source: string
  url: string
  icon: React.ElementType
  tags: string[]
  color: "red" | "orange" | "blue" | "green" | "yellow" | "purple"
}

const COLOR_MAP = {
  red:    { bg: "bg-red-500/10",    border: "border-red-500/30",    text: "text-red-400",    icon: "text-red-400",    tag: "bg-red-500/10 border-red-500/20 text-red-400" },
  orange: { bg: "bg-orange-500/10", border: "border-orange-500/30", text: "text-orange-400", icon: "text-orange-400", tag: "bg-orange-500/10 border-orange-500/20 text-orange-400" },
  blue:   { bg: "bg-blue-500/10",   border: "border-blue-500/30",   text: "text-blue-400",   icon: "text-blue-400",   tag: "bg-blue-500/10 border-blue-500/20 text-blue-400" },
  green:  { bg: "bg-green-500/10",  border: "border-green-500/30",  text: "text-green-400",  icon: "text-green-400",  tag: "bg-green-500/10 border-green-500/20 text-green-400" },
  yellow: { bg: "bg-yellow-500/10", border: "border-yellow-500/30", text: "text-yellow-400", icon: "text-yellow-400", tag: "bg-yellow-500/10 border-yellow-500/20 text-yellow-400" },
  purple: { bg: "bg-purple-500/10", border: "border-purple-500/30", text: "text-purple-400", icon: "text-purple-400", tag: "bg-purple-500/10 border-purple-500/20 text-purple-400" },
}

const DOCUMENTS: Doc[] = [
  { id: 1, title: "Executive Order — China 145% Tariffs", description: "Official White House executive order imposing 145% tariffs on all Chinese imports across product categories, effective April 2025.", category: "Policy", date: "Apr 2, 2025", source: "White House", url: "https://www.whitehouse.gov", icon: IconBuildingBank, tags: ["China", "Executive Order", "145%"], color: "red" },
  { id: 2, title: "USTR 2025 Trade Policy Agenda", description: "Annual trade policy agenda outlining US tariff strategy, WTO negotiations, and bilateral trade priorities for 2025.", category: "Policy", date: "Mar 1, 2025", source: "USTR.gov", url: "https://ustr.gov", icon: IconBuildingBank, tags: ["USTR", "Policy", "2025"], color: "orange" },
  { id: 3, title: "US-China Trade Flow Report Q1 2025", description: "Comprehensive analysis of import/export volumes, tariff revenues, and supply chain shifts between the US and China in Q1 2025.", category: "Trade Data", date: "Apr 15, 2025", source: "US Census Bureau", url: "https://census.gov/foreign-trade", icon: IconChartBar, tags: ["China", "Trade Data", "Q1 2025"], color: "blue" },
  { id: 4, title: "Global Supply Chain Disruption Index", description: "World Bank research on how US tariff escalation is reshaping global supply chains, with sector-by-sector impact scores.", category: "Research", date: "Mar 20, 2025", source: "World Bank", url: "https://worldbank.org", icon: IconWorld, tags: ["Supply Chain", "Global", "Research"], color: "green" },
  { id: 5, title: "China MOFCOM Retaliation Notice", description: "Official statement announcing 125% counter-tariffs on US agricultural, automotive, and technology exports.", category: "Policy", date: "Apr 4, 2025", source: "MOFCOM China", url: "https://mofcom.gov.cn", icon: IconBuildingBank, tags: ["China", "Retaliation", "125%"], color: "red" },
  { id: 6, title: "WTO Dispute — US Tariff Complaint Filing", description: "EU and 14 nations file formal WTO dispute against US universal baseline tariffs, citing violations of MFN clauses.", category: "Legal", date: "Apr 10, 2025", source: "WTO", url: "https://wto.org", icon: IconScale, tags: ["WTO", "Legal", "EU", "Dispute"], color: "purple" },
  { id: 7, title: "IMF World Economic Outlook — Tariff Impact", description: "IMF assessment of how current US tariff levels will reduce global GDP growth by 0.5% in 2025.", category: "Research", date: "Apr 22, 2025", source: "IMF", url: "https://imf.org/en/Publications/WEO", icon: IconChartBar, tags: ["IMF", "GDP", "Global Impact"], color: "yellow" },
  { id: 8, title: "US Steel & Aluminum Tariff Schedule", description: "Section 232 tariff schedules updated with 2025 country-specific rates, product classifications, and exemption procedures.", category: "Trade Data", date: "Feb 10, 2025", source: "US Commerce Dept.", url: "https://commerce.gov", icon: IconBuildingFactory2, tags: ["Steel", "Aluminum", "Section 232"], color: "orange" },
  { id: 9, title: "Vietnam Textile Sector Impact Assessment", description: "Industry analysis on how 46% US tariffs are affecting Vietnam's $40B textile export industry.", category: "Research", date: "Apr 18, 2025", source: "Peterson Institute", url: "https://piie.com", icon: IconChartBar, tags: ["Vietnam", "Textiles", "46%"], color: "blue" },
  { id: 10, title: "Reuters — Trade War Escalation Timeline", description: "Detailed timeline of all major tariff announcements, retaliations, pauses, and negotiations from January 2025.", category: "News", date: "Apr 25, 2025", source: "Reuters", url: "https://reuters.com", icon: IconNews, tags: ["Timeline", "News", "Escalation"], color: "green" },
  { id: 11, title: "CBO — Tariff Revenue Forecast", description: "CBO 10-year projection of tariff revenues. Estimates $2.4T in cumulative revenue, offset by $1.9T in economic drag.", category: "Research", date: "Mar 28, 2025", source: "CBO", url: "https://cbo.gov", icon: IconCurrencyDollar, tags: ["CBO", "Revenue", "Fiscal"], color: "yellow" },
  { id: 12, title: "Section 301 Investigation — China Tech Tariffs", description: "Full text of the Section 301 investigation findings used to justify technology-sector tariffs on China.", category: "Legal", date: "Jan 15, 2025", source: "USTR", url: "https://ustr.gov/section301", icon: IconScale, tags: ["Section 301", "China", "Legal", "Tech"], color: "purple" },
  { id: 13, title: "Federal Register — Tariff Exclusion Requests", description: "Process and status of tariff exclusion requests filed by US businesses. Over 14,000 requests pending.", category: "Legal", date: "Apr 1, 2025", source: "Federal Register", url: "https://federalregister.gov", icon: IconFileText, tags: ["Exclusions", "Business", "Federal Register"], color: "orange" },
  { id: 14, title: "BLS Import Price Index — Tariff Effects", description: "Monthly import price index showing consumer price impacts of tariffs across electronics, apparel, and household goods.", category: "Trade Data", date: "Apr 14, 2025", source: "BLS", url: "https://bls.gov", icon: IconChartBar, tags: ["BLS", "Prices", "Consumer Impact"], color: "blue" },
  { id: 15, title: "WSJ — Auto Industry Tariff Fallout", description: "How 25% tariffs on Mexican and Canadian auto parts are raising vehicle prices by an average of $4,200 per car.", category: "News", date: "Apr 20, 2025", source: "Wall Street Journal", url: "https://wsj.com", icon: IconNews, tags: ["Automotive", "Mexico", "Canada"], color: "red" },
  { id: 16, title: "OECD Trade in Value Added Database", description: "Interactive database tracking how tariffs affect global value chains across 45 sectors.", category: "Trade Data", date: "Mar 5, 2025", source: "OECD", url: "https://oecd.org", icon: IconWorld, tags: ["OECD", "Value Chain", "Database"], color: "green" },
]

const glassStyle: React.CSSProperties = {
  background: "rgba(12, 12, 18, 0.70)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
}

export default function DocumentsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [search, setSearch] = useState("")
  const [activeCategory, setActiveCategory] = useState("All")
  const [selectedDoc, setSelectedDoc] = useState<Doc | null>(null)

  const filtered = DOCUMENTS.filter(doc => {
    const matchesCategory = activeCategory === "All" || doc.category === activeCategory
    const matchesSearch =
      doc.title.toLowerCase().includes(search.toLowerCase()) ||
      doc.source.toLowerCase().includes(search.toLowerCase()) ||
      doc.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
    return matchesCategory && matchesSearch
  })

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
          <div className="flex flex-col gap-6 px-4 lg:px-6 py-6">
            <div className="flex flex-col gap-1">
              <h1 className="text-xl font-semibold flex items-center gap-2">
                <IconFileText className="size-5 text-red-500" />
                Sources & Documents
              </h1>
              <p className="text-sm text-muted-foreground">
                Official references, research papers, and trade data sources powering TariffOS.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative w-full sm:w-72">
                <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search sources, tags..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-2 text-sm bg-muted/30 border border-border/40 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/20"
                />
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <IconTag className="size-3.5 text-muted-foreground shrink-0" />
                {CATEGORIES.map(cat => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                      activeCategory === cat
                        ? "bg-red-500/20 border-red-500/50 text-red-400"
                        : "bg-muted/20 border-border/30 text-muted-foreground hover:border-border hover:text-foreground"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {filtered.map(doc => {
                const colors = COLOR_MAP[doc.color]
                const Icon = doc.icon
                return (
                  <button
                    key={doc.id}
                    onClick={() => setSelectedDoc(doc)}
                    className={`text-left p-4 rounded-xl border transition-all hover:scale-[1.02] hover:shadow-lg group ${colors.border} ${colors.bg}`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div className={`p-2 rounded-lg border ${colors.border} ${colors.bg}`}>
                        <Icon className={`size-4 ${colors.icon}`} />
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${colors.tag}`}>
                        {doc.category}
                      </span>
                    </div>
                    <p className="text-sm font-semibold leading-snug mb-1 group-hover:text-white transition-colors">
                      {doc.title}
                    </p>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mb-3">
                      {doc.description}
                    </p>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                        <IconCalendar className="size-3" />
                        {doc.date}
                      </span>
                      <span className={`text-[10px] font-medium ${colors.text}`}>{doc.source}</span>
                    </div>
                  </button>
                )
              })}
            </div>

            {filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                <IconSearch className="size-8 mb-3 opacity-30" />
                <p className="text-sm">No documents match your search.</p>
              </div>
            )}
          </div>
        </SidebarInset>
      </div>

      {/* Modal */}
      {selectedDoc && (() => {
        const colors = COLOR_MAP[selectedDoc.color]
        const Icon = selectedDoc.icon  // 👈 assign to capitalized variable first
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)" }}
            onClick={() => setSelectedDoc(null)}
          >
            <div
              className={`relative w-full max-w-md rounded-2xl border p-6 flex flex-col gap-4 ${colors.border}`}
              style={glassStyle}
              onClick={e => e.stopPropagation()}
            >
              <button
                onClick={() => setSelectedDoc(null)}
                className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors"
              >
                <IconX className="size-4" />
              </button>

              <div className="flex items-center gap-3">
                <div className={`p-3 rounded-xl border ${colors.border} ${colors.bg}`}>
                  <Icon className={`size-5 ${colors.icon}`} />
                </div>
                <div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${colors.tag}`}>
                    {selectedDoc.category}
                  </span>
                  <p className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                    <IconCalendar className="size-3" /> {selectedDoc.date} · {selectedDoc.source}
                  </p>
                </div>
              </div>

              <h2 className="text-base font-semibold leading-snug">{selectedDoc.title}</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">{selectedDoc.description}</p>

              <div className="flex flex-wrap gap-1.5">
                {selectedDoc.tags.map(tag => (
                  <span key={tag} className={`text-[10px] px-2 py-0.5 rounded-full border ${colors.tag}`}>
                    {tag}
                  </span>
                ))}
              </div>

              
                href={selectedDoc.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center justify-center gap-2 w-full py-2.5 rounded-xl border font-medium text-sm transition-all hover:opacity-90 ${colors.border} ${colors.bg} ${colors.text}`}
              >
                <IconExternalLink className="size-4" />
                Open Source — {selectedDoc.source}
              <a></a>
            </div>
          </div>
        )
      })()}
    </SidebarProvider>
  )
}