/**
 * ManubisGuard is versioned and released independently from PasarGuard.
 * Automatic upstream release checks are intentionally disabled: only a future
 * ManubisGuard-owned release feed may enable update notifications.
 */
interface VersionCheckResult {
  hasUpdate: boolean
  latestVersion: string | null
  currentVersion: string | null
  releaseUrl: string | null
  isLoading: boolean
}

interface UseVersionCheckOptions {
  enabled?: boolean
}

export function useVersionCheck(
  currentVersion: string | null,
  _options: UseVersionCheckOptions = {},
): VersionCheckResult {
  return {
    hasUpdate: false,
    latestVersion: null,
    currentVersion: currentVersion?.replace(/^v/i, '') || null,
    releaseUrl: null,
    isLoading: false,
  }
}
