import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
    DEFAULT_DASHBOARD_REPO,
    resolveDashboardRepo,
    toInlineScriptJson,
} from "../.apm/extensions/issue-monitor/repo-config.mjs";

describe("dashboard repository configuration", () => {
    it("defaults to the demo fork", () => {
        assert.equal(DEFAULT_DASHBOARD_REPO, "richard-fowles-epam/apm");
        assert.equal(resolveDashboardRepo(undefined), DEFAULT_DASHBOARD_REPO);
        assert.equal(resolveDashboardRepo(""), DEFAULT_DASHBOARD_REPO);
    });

    it("accepts a valid owner/name override", () => {
        assert.equal(resolveDashboardRepo(" octo/demo-repo.js "), "octo/demo-repo.js");
    });

    it("refuses upstream microsoft/apm in any case", () => {
        assert.equal(resolveDashboardRepo("microsoft/apm"), DEFAULT_DASHBOARD_REPO);
        assert.equal(resolveDashboardRepo("Microsoft/APM"), DEFAULT_DASHBOARD_REPO);
    });

    it("rejects malformed values", () => {
        for (const bad of ["apm", "a/b/c", "../x", "o/..", "o/r;rm", "o/r\"</script>", "-o/r"]) {
            assert.equal(resolveDashboardRepo(bad), DEFAULT_DASHBOARD_REPO, bad);
        }
    });

    it("escapes script-breaking characters for inline injection", () => {
        assert.equal(toInlineScriptJson("</script>&"), '"\\u003c/script\\u003e\\u0026"');
    });
});
