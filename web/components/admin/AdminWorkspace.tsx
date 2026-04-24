"use client"

import AdminWorkspaceHeader from "@/components/admin/AdminWorkspaceHeader"
import AdminWorkspaceContent from "@/components/admin/AdminWorkspaceContent"
import { useAdminWorkspace } from "@/components/admin/useAdminWorkspace"

export default function AdminWorkspace() {
  const controller = useAdminWorkspace()

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminWorkspaceHeader
        view={controller.view}
        currentSurface={controller.currentSurface}
        activeWorkstream={controller.activeWorkstream}
        workstreamViews={controller.workstreamViews}
        activeSurfaceId={controller.activeSurfaceId}
        drawerOpen={controller.drawerOpen}
        toggleButtonRef={controller.toggleButtonRef}
        onToggleDrawer={controller.toggleDrawer}
        onNavigate={controller.navigate}
        onSelectWorkstream={controller.selectWorkstream}
      />
      <AdminWorkspaceContent
        view={controller.view}
        sessionParam={controller.sessionParam}
        trackParam={controller.trackParam}
        currentSurface={controller.currentSurface}
        activeWorkstream={controller.activeWorkstream}
        drawerOpen={controller.drawerOpen}
        toggleButtonRef={controller.toggleButtonRef}
        health={controller.health}
        healthError={controller.healthError}
        healthLoading={controller.healthLoading}
        refreshKey={controller.refreshKey}
        onToggleDrawer={controller.toggleDrawer}
        onNavigate={controller.navigate}
        onRefresh={() => controller.setRefreshKey((value) => value + 1)}
      />
    </div>
  )
}
