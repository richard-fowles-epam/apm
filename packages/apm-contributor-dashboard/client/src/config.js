const DEFAULT_REFRESH_INTERVAL_MS = 15 * 60 * 1000;
const DEFAULT_DASHBOARD_REPO = "richard-fowles-epam/apm";

const configuredRepo = typeof window !== "undefined"
  ? window.__APM_DASHBOARD_REPO__
  : undefined;

export const dashboardRepo = typeof configuredRepo === "string" && /^[A-Za-z0-9-]+\/[A-Za-z0-9._-]+$/.test(configuredRepo)
  ? configuredRepo
  : DEFAULT_DASHBOARD_REPO;

const configuredInterval = typeof window !== "undefined"
  ? Number(window.__APM_DASHBOARD_REFRESH_INTERVAL_MS__)
  : NaN;

export const refreshIntervalMs = Number.isFinite(configuredInterval) && configuredInterval > 0
  ? configuredInterval
  : DEFAULT_REFRESH_INTERVAL_MS;

export function formatRefreshInterval(intervalMs) {
  const minutes = intervalMs / (60 * 1000);
  if (Number.isInteger(minutes) && minutes < 60) return `${minutes}m`;
  const hours = minutes / 60;
  if (Number.isInteger(hours)) return `${hours}h`;
  return `${minutes.toFixed(1)}m`;
}
