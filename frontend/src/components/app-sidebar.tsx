import type * as React from "react"
import { Link } from "react-router-dom"
import { CommandIcon } from "lucide-react"

import { navGroups, systemNavItems } from "@/app/routes"
import { NavGroup } from "@/components/layout/nav-group"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const localUser = {
  name: "Local User",
  email: "user@swetrack.local",
  avatar: "",
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="data-[slot=sidebar-menu-button]:p-1.5!"
            >
              <Link to="/">
                <CommandIcon className="size-5!" />
                <span className="text-base font-semibold">SWETrack</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {navGroups.map((group) => (
          <NavGroup key={group.label} label={group.label} items={group.items} />
        ))}
        <NavGroup label="System" items={systemNavItems} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={localUser} />
      </SidebarFooter>
    </Sidebar>
  )
}
