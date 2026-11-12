"""Guards for the panel-review demo setup script (demo/panel-review)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "demo" / "panel-review" / "setup_demo.py"


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("panel_review_demo_setup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("repo", ["microsoft/apm", "Microsoft/APM", "someone/apm", ""])
def test_refuses_non_fork_repositories(demo, repo):
    with pytest.raises(demo.DemoError):
        demo.ensure_fork(repo)
    assert demo.main(["labels", "--repo", repo]) == 1


def test_dry_run_never_calls_gh(demo, monkeypatch, capsys):
    def boom(*_a, **_k):
        raise AssertionError("gh must not run in dry-run label setup")

    monkeypatch.setattr(demo, "_gh", boom)
    assert demo.main(["labels"]) == 0
    assert "dry-run" in capsys.readouterr().out


def test_sanitize_removes_every_source_reference(demo):
    body = "\n".join(
        [
            "Ping @alice and @org/team, mail a@b.com.",
            "See #123, octo/repo#7 and https://github.com/microsoft/apm/issues/99.",
            "Also [the PR](https://github.com/microsoft/apm/pull/5) and [`x.py`](https://github.com/microsoft/apm/blob/v1/x.py).",
            "Reported by `@bob` in `microsoft/apm#2146`; keep `apm install --flag`.",
            "Lives in microsoft/apm and https://github.com/Microsoft/APM.",
            "```",
            "@inside #2",
            "```",
        ]
    )
    out = demo.sanitize_body(body).splitlines()
    assert out[0] == "Ping a user and a user, mail a@b.com."
    assert out[1] == "See a related issue, a related issue and a related issue."
    assert out[2] == "Also the PR and `x.py`."
    assert out[3] == "Reported by a user in a related issue; keep `apm install --flag`."
    assert out[4] == "Lives in the project repository and the project repository."
    assert out[6] == "@inside #2"


def test_demo_issue_has_no_tie_to_source(demo):
    issue = {"number": 42, "title": "Fix #12", "body": "hi @bob, see microsoft/apm#3"}
    title, body = demo.build_demo_issue(issue)
    assert title == "[DEMO] Fix a related issue"
    assert "Demo issue for the panel-review walkthrough. Not tracked work." in body
    for needle in ("microsoft", "github.com", "@bob", "#3", "42", "<!--"):
        assert needle not in title + body


def test_demo_issue_refuses_leftover_source_reference(demo):
    issue = {"title": "T", "body": "```\npip install git+https://github.com/microsoft/apm\n```"}
    with pytest.raises(demo.DemoError):
        demo.build_demo_issue(issue)
