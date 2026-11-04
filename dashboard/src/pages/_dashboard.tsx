import { Footer } from '@/components/layout/footer'
import { AppSidebar } from '@/components/layout/sidebar'
import PageTransition from '@/components/layout/page-transition'
import RouteGuard from '@/components/layout/route-guard'
import { TopLoadingBar } from '@/components/layout/top-loading-bar'
import { VersionUpdateBanner } from '@/components/layout/version-update-banner'
import DonationPopup from '@/components/common/donation-popup'
import TopbarAd from '@/components/common/topbar-ad'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { getCurrentAdmin } from '@/service/api'
import { isAuthenticationError } from '@/utils/error-utils'
import { Outlet } from 'react-router'
import { CommandPalette } from '@/components/layout/command-palette'
import ManubisTopbar from '@/components/layout/manubis-topbar'

export const clientLoader = async () => {
  try {
    const response = await getCurrentAdmin()
    return response
  } catch (error) {
    if (isAuthenticationError(error)) {
      throw Response.redirect('/login')
    }

    throw error
  }
}

export default function DashboardLayout() {
  return (
    <SidebarProvider className="mg-shell-provider">
      <RouteGuard>
        <TopLoadingBar />
        <DonationPopup />
        <CommandPalette />
        <div className="mg-app-frame flex min-h-0 w-full min-w-0 flex-col lg:flex-row">
          <AppSidebar />
          <SidebarInset className="dashboard-scroll min-h-0 min-w-0 flex-1 scroll-smooth bg-background/95">
            <ManubisTopbar />
            <TopbarAd />
            <VersionUpdateBanner />
            <div className="mg-page-flow flex min-h-full w-full min-w-0 flex-col gap-y-4">
              <PageTransition duration={180} className="mg-page-content flex min-w-0 flex-col">
                <Outlet />
              </PageTransition>
              <Footer />
            </div>
          </SidebarInset>
        </div>
      </RouteGuard>
    </SidebarProvider>
  )
}
