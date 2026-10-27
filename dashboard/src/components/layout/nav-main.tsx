import { Fragment } from 'react'
import { ChevronRight, type LucideIcon } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from '@/components/ui/sidebar'
import { NavLink, useLocation } from 'react-router'
import { useTranslation } from 'react-i18next'

type NavItem = {
  title: string
  url: string
  icon: LucideIcon
  isActive?: boolean
  section?: string
  items?: { title: string; url: string; icon: LucideIcon; matchPrefix?: boolean }[]
}

type NavSection = { title: string; items: NavItem[] }

export function NavMain({ items }: { items: NavItem[] }) {
  const location = useLocation()
  const { t } = useTranslation()
  const { setOpenMobile } = useSidebar()
  const handleNavigation = () => setOpenMobile(false)

  const sections = items.reduce<NavSection[]>((groups, item) => {
    const title = item.section ?? 'platform'
    const last = groups[groups.length - 1]
    if (last?.title === title) last.items.push(item)
    else groups.push({ title, items: [item] })
    return groups
  }, [])

  return (
    <SidebarGroup>
      {sections.map(section => (
        <Fragment key={section.title}>
          <SidebarGroupLabel className="mt-4 px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/45 first:mt-0">
            {t(section.title)}
          </SidebarGroupLabel>
          <SidebarMenu className="gap-1">
            {section.items.map(item => {
              const hasActiveChild = item.items?.some(sub => {
                const base = sub.url.replace(/\/$/, '')
                return location.pathname === sub.url || Boolean(sub.matchPrefix && location.pathname.startsWith(`${base}/`))
              }) ?? false
              const isItemActive = Boolean(item.isActive || location.pathname === item.url || hasActiveChild)

              return (
                <Collapsible key={item.title} defaultOpen={isItemActive}>
                  <SidebarMenuItem>
                    <NavLink to={item.url} onClick={handleNavigation}>
                      <SidebarMenuButton
                        tooltip={t(item.title)}
                        isActive={isItemActive}
                        className="relative h-10 rounded-xl border border-transparent px-3 transition-all duration-200 data-[active=true]:border-primary/20 data-[active=true]:bg-primary/10 data-[active=true]:text-primary data-[active=true]:shadow-[0_8px_24px_hsl(var(--primary)/.08)] hover:border-border/60 hover:bg-sidebar-accent/70"
                      >
                        <item.icon />
                        <span>{t(item.title)}</span>
                      </SidebarMenuButton>
                    </NavLink>

                    {item.items?.length ? (
                      <>
                        <CollapsibleTrigger asChild>
                          <SidebarMenuAction className="data-[state=open]:rotate-90 rtl:data-[state=open]:-rotate-90">
                            <ChevronRight className="rtl:rotate-180" />
                            <span className="sr-only">Toggle</span>
                          </SidebarMenuAction>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <SidebarMenuSub>
                            {item.items.map(subItem => {
                              const base = subItem.url.replace(/\/$/, '')
                              const subActive = location.pathname === subItem.url || Boolean(subItem.matchPrefix && (location.pathname === base || location.pathname.startsWith(`${base}/`)))
                              return (
                                <SidebarMenuSubItem key={subItem.title}>
                                  <SidebarMenuSubButton
                                    asChild
                                    isActive={subActive}
                                    className="flex h-9 items-center gap-2 rounded-lg px-3 transition-all data-[active=true]:bg-primary/10 data-[active=true]:text-primary data-[active=true]:shadow-[inset_2px_0_0_hsl(var(--primary))]"
                                  >
                                    <NavLink to={subItem.url} end={!subItem.matchPrefix} onClick={handleNavigation}>
                                      <subItem.icon />
                                      <span>{t(subItem.title)}</span>
                                    </NavLink>
                                  </SidebarMenuSubButton>
                                </SidebarMenuSubItem>
                              )
                            })}
                          </SidebarMenuSub>
                        </CollapsibleContent>
                      </>
                    ) : null}
                  </SidebarMenuItem>
                </Collapsible>
              )
            })}
          </SidebarMenu>
        </Fragment>
      ))}
    </SidebarGroup>
  )
}
