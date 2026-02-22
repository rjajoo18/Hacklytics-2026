"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  IconLayoutDashboard,
  IconWorld,
  IconTrendingUp,
  IconFileText,
  IconDatabase,
} from "@tabler/icons-react"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

const NAV_ITEMS = [
  { title: "Dashboard", url: "/dashboard", icon: IconLayoutDashboard },
  { title: "Global",    url: "/map",       icon: IconWorld },
  { title: "Trends",    url: "/trends",    icon: IconTrendingUp },
]

export function NavMain({ items }: { items?: typeof NAV_ITEMS }) {
  const pathname = usePathname()
  const navItems = items ?? NAV_ITEMS

  return (
    <SidebarGroup className="px-3 py-2">
      <SidebarGroupContent>
        <SidebarMenu className="gap-0.5">
          {navItems.map((item) => {
            const isActive = pathname === item.url || pathname.startsWith(item.url + "/")
            const Icon = item.icon

            return (
              <SidebarMenuItem key={item.title}>
                <Link
                  href={item.url}
                  className={`
                    relative flex items-center gap-3 w-full h-10 px-3 rounded-xl
                    transition-all duration-300 ease-out group overflow-hidden select-none
                    ${isActive ? "text-white" : "text-white/40 hover:text-white"}
                  `}
                >
                  {/* Active background - Matches your specific "nice red tint" */}
                  {isActive && (
                    <span
                      className="absolute inset-0 rounded-xl pointer-events-none"
                      style={{
                        background: "linear-gradient(135deg, rgba(254, 226, 226, 0.4) 0%, rgba(239, 68, 68, 0.1) 100%)",
                        boxShadow: "0 0 20px rgba(239,68,68,0.2)",
                      }}
                    />
                  )}

                  {/* Icon - Uses your exact color logic */}
                  <Icon 
                    className={`
                      relative z-10 size-4 transition-colors duration-300
                      ${isActive ? "text-red-400" : "text-white/40 group-hover:text-red-400"}
                    `} 
                  />

                  {/* Label */}
                  <span 
                    className="relative z-10 flex-1 text-[13px] font-medium tracking-tight antialiased"
                  >
                    {item.title}
                  </span>

                  {/* Active Indicator (Small Red Dot) */}
                  {isActive && (
                    <span className="relative z-10 w-1 h-1 rounded-full bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]" />
                  )}

                  {/* Hover Chevron for Inactive */}
                  {!isActive && (
                    <span className="relative z-10 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all duration-300 text-red-400/50 text-[10px]">
                      ›
                    </span>
                  )}
                </Link>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}