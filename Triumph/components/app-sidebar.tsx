"use client"

import * as React from "react"
import {
  IconChartBar,
  IconDashboard,
  IconDatabase,
  IconFileAi,
  IconGlobe,
  IconHelp,
  IconListDetails,
  IconReport,
  IconScale,
  IconSettings,
  IconShield,
} from "@tabler/icons-react"

import { NavDocuments } from '@/components/nav-documents'
import { NavMain } from '@/components/nav-main'
import { NavSecondary } from '@/components/nav-secondary'
import { NavUser } from '@/components/nav-user'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

const data = {
  user: {
    name: "shashank.shaga",
    email: "shashankshaga.reddy@gmail.com",
    avatar: "/avatars/shadcn.jpg",
  },
  navMain: [
    { title: "Dashboard", url: "/dashboard", icon: IconDashboard },
    { title: "Global",    url: "/global",       icon: IconGlobe },
    { title: "Trends",    url: "/trends",    icon: IconChartBar },
  ],
  navSecondary: [
    { title: "Settings", url: "/settings", icon: IconSettings },
    { title: "Get Help", url: "/help",     icon: IconHelp },
  ],
  documents: [
    { name: "Documents", url: "/documents",      icon: IconDatabase },
    { name: "Data Library",      url: "/data", icon: IconReport },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar
      collapsible="none"
      className="h-screen shrink-0 border-r border-white/5"
      style={{
        background: "rgba(10, 10, 15, 0.85)",
        WebkitBackdropFilter: "blur(24px)",
      }}
      {...props}
    >
      <SidebarHeader className="border-b border-white/5 pb-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="hover:bg-white/5 transition-colors rounded-lg"
            >
              <a href="#" className="flex items-center gap-2.5 px-1">
                <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-red-500/20 border border-red-500/30">
                  <IconScale className="size-4 text-red-400" />
                </div>
                <div className="flex flex-col leading-none">
                  <span className="text-sm font-semibold text-foreground">Quantara</span>
                  <span className="text-[10px] text-muted-foreground">Tariff Intelligence</span>
                </div>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="px-2 py-3">


        <NavMain items={data.navMain} />
        <NavDocuments items={data.documents} />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>

      <SidebarFooter className="border-t border-white/5 pt-2">
        {/* Live indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 mb-1 rounded-lg bg-green-500/5 border border-green-500/10 mx-1">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-[10px] text-green-400 font-medium">Markets Live</span>
          <span className="ml-auto text-[10px] text-muted-foreground">NYSE Open</span>
        </div>
        <NavUser user={data.user} />
      </SidebarFooter>
    </Sidebar>
  )
}