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


def test_sanitize_neutralizes_mentions_and_refs(demo):
    body = "\n".join(
        [
            "Ping @alice and @org/team, mail a@b.com.",
            "See #123, octo/repo#7 and https://github.com/microsoft/apm/issues/99.",
            "Also [the PR](https://github.com/microsoft/apm/pull/5).",
            "Keep `@code #1` as is.",
            "```",
            "@inside #2",
            "```",
        ]
    )
    out = demo.sanitize_body(body).splitlines()
    assert out[0] == "Ping `@alice` and `@org/team`, mail a@b.com."
    assert out[1] == "See `microsoft/apm#123`, `octo/repo#7` and `microsoft/apm#99`."
    assert out[2] == "Also the PR (`microsoft/apm#5`)."
    assert out[3] == "Keep `@code #1` as is."
    assert out[5] == "@inside #2"


@pytest.mark.parametrize("style", ["clickable", "code"])
def test_demo_issue_is_marked_and_links_original(demo, style):
    issue = {
        "number": 42,
        "title": "Thing",
        "body": "hi @bob",
        "author": {"login": "bob"},
        "createdAt": "2025-01-02T00:00:00Z",
    }
    title, body = demo.build_demo_issue(issue, link_style=style)
    url = "https://github.com/microsoft/apm/issues/42"
    assert title == "[DEMO] Thing"
    assert "Demo copy for the panel-review walkthrough. Not tracked work." in body
    assert "<!-- apm-demo-source: microsoft/apm#42 -->" in body
    assert (f"Original: {url}" in body) == (style == "clickable")
    assert (f"Original: `{url}`" in body) == (style == "code")
    assert "@bob" not in body.replace("`@bob`", "")
