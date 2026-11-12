// Repository the dashboard reads issues/PRs from and writes panel-review
// labels to. Defaults to the richard-fowles-epam/apm demo fork; override
// with APM_DASHBOARD_REPO=<owner>/<name>. The upstream microsoft/apm
// repository is refused so the demo can never act on it.
export const DEFAULT_DASHBOARD_REPO = "richard-fowles-epam/apm";
export const BLOCKED_DASHBOARD_REPOS = new Set(["microsoft/apm"]);

const REPO_PATTERN = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9._-]{1,100}$/;

export function resolveDashboardRepo(value) {
    const candidate = String(value ?? "").trim();
    if (!REPO_PATTERN.test(candidate) || candidate.includes("..")) {
        return DEFAULT_DASHBOARD_REPO;
    }
    if (BLOCKED_DASHBOARD_REPOS.has(candidate.toLowerCase())) {
        return DEFAULT_DASHBOARD_REPO;
    }
    return candidate;
}

// JSON literal that is safe to embed inside an inline <script> element.
export function toInlineScriptJson(value) {
    return JSON.stringify(value)
        .replace(/</g, "\\u003c")
        .replace(/>/g, "\\u003e")
        .replace(/&/g, "\\u0026")
        .replace(/\u2028/g, "\\u2028")
        .replace(/\u2029/g, "\\u2029");
}
