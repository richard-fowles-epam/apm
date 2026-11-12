#!/usr/bin/env python3
"""Prepare the richard-fowles-epam/apm fork for the panel-review demo.

Dry-run by default. Pass --apply to write. Every write targets the demo
fork only; the script refuses any other repository, including
microsoft/apm. Upstream issues are only read with `gh issue view`.

Subcommands:
  labels     create/update the labels the panel-review flow needs
  issues     copy the selected upstream issues into the fork as demo issues
  workflows  disable every fork workflow except pr-review-panel.lock.yml
  all        labels + issues (workflows stays a separate, explicit step)

Authentication comes from your existing `gh auth login` session. This
script never reads, prints, or stores tokens.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys

FORK_REPO = "richard-fowles-epam/apm"
UPSTREAM_REPO = "microsoft/apm"
PANEL_WORKFLOW = "pr-review-panel.lock.yml"
DEMO_LABEL = "demo"
SOURCE_MARKER = "<!-- apm-demo-source: {repo}#{number} -->"

DEMO_ISSUES: tuple[int, ...] = (2986, 3593, 3351, 3056, 3110)

LABELS: tuple[tuple[str, str, str], ...] = (
    ("panel-review", "5319e7", "Trigger: run the advisory PR review panel"),
    ("status/accepted", "0e8a16", "Maintainer-accepted; required before panel review"),
    (DEMO_LABEL, "fbca04", "Demo copy of an upstream issue; not tracked work"),
)

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
_MD_LINK_RE = re.compile(
    r"\[([^\]]*)\]\(https?://github\.com/([\w.-]+)/([\w.-]+)/"
    r"(?:issues|pull|discussions)/(\d+)[^)]*\)"
)
_GH_URL_RE = re.compile(
    r"https?://github\.com/([\w.-]+)/([\w.-]+)/(?:issues|pull|discussions)/(\d+)(?:[\w#/?=&.-]*[\w/=])?"
)
_QUALIFIED_REF_RE = re.compile(r"(?<![\w/`])([\w.-]+/[\w.-]+)#(\d+)\b")
_BARE_REF_RE = re.compile(r"(?<![\w&/`#])#(\d+)\b")
_MENTION_RE = re.compile(r"(?<![\w`/.@])@([A-Za-z0-9][A-Za-z0-9-]{0,38}(?:/[\w.-]+)?)")


class DemoError(RuntimeError):
    """Raised for unsafe or failed demo setup actions."""


def ensure_fork(repo: str) -> str:
    """Return the fork slug if repo is the demo fork; refuse everything else."""
    if repo.strip().lower() != FORK_REPO.lower():
        raise DemoError(f"refusing to write to {repo!r}; only {FORK_REPO} is allowed")
    return FORK_REPO


def _neutralize_text(segment: str) -> str:
    segment = _MD_LINK_RE.sub(
        lambda m: f"{m.group(1)} (`{m.group(2)}/{m.group(3)}#{m.group(4)}`)", segment
    )
    segment = _GH_URL_RE.sub(lambda m: f"`{m.group(1)}/{m.group(2)}#{m.group(3)}`", segment)
    segment = _QUALIFIED_REF_RE.sub(lambda m: f"`{m.group(1)}#{m.group(2)}`", segment)
    segment = _BARE_REF_RE.sub(lambda m: f"`{UPSTREAM_REPO}#{m.group(1)}`", segment)
    return _MENTION_RE.sub(lambda m: f"`@{m.group(1)}`", segment)


def _neutralize_line(line: str) -> str:
    out: list[str] = []
    pos = 0
    for match in _INLINE_CODE_RE.finditer(line):
        out.append(_neutralize_text(line[pos : match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(_neutralize_text(line[pos:]))
    return "".join(out)


def sanitize_body(body: str) -> str:
    """Stop notifications and cross-repo backlinks from a copied issue body.

    @mentions and issue/PR references outside code are wrapped in inline
    code so GitHub neither notifies users nor links back to upstream
    threads. Bare #N refs are qualified to microsoft/apm because in the
    fork they would point at unrelated issues. Fenced code is untouched.
    """
    result: list[str] = []
    fence: str | None = None
    for line in (body or "").splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            result.append(line)
            if fence_match and fence_match.group(1) == fence:
                fence = None
            continue
        if fence_match:
            fence = fence_match.group(1)
            result.append(line)
            continue
        result.append(_neutralize_line(line))
    return "\n".join(result)


def build_demo_issue(issue: dict, *, link_style: str = "clickable") -> tuple[str, str]:
    """Return (title, body) for the demo copy of an upstream issue."""
    number = int(issue["number"])
    url = f"https://github.com/{UPSTREAM_REPO}/issues/{number}"
    original = url if link_style == "clickable" else f"`{url}`"
    author = (issue.get("author") or {}).get("login") or "unknown"
    created = str(issue.get("createdAt") or "")[:10] or "unknown date"
    banner = [
        "> [!NOTE]",
        "> **Demo copy for the panel-review walkthrough. Not tracked work.**",
        f"> Copied from `{UPSTREAM_REPO}#{number}` (original author: `{author}`,",
        f"> opened {created}). Comments, labels, and assignees were not copied.",
        "> Mentions and cross-references are shown as code so nobody is notified.",
        "> The original issue remains the source of truth.",
        ">",
        f"> Original: {original}",
        "",
        SOURCE_MARKER.format(repo=UPSTREAM_REPO, number=number),
        "",
        "---",
        "",
    ]
    return f"[DEMO] {issue['title']}", "\n".join(banner) + sanitize_body(issue.get("body") or "")


def _gh(args: list[str]) -> str:
    gh = shutil.which("gh")
    if gh is None:
        raise DemoError("GitHub CLI 'gh' not found on PATH; install it and run 'gh auth login'")
    # Arguments are built from constants and validated inputs; no shell is used.
    proc = subprocess.run([gh, *args], capture_output=True, text=True, check=False)  # noqa: S603
    if proc.returncode != 0:
        raise DemoError(f"gh {' '.join(args[:3])} failed: {(proc.stderr or '').strip()}")
    return proc.stdout or ""


def _run_write(args: list[str], apply: bool) -> None:
    shown = " ".join(args)
    if not apply:
        print(f"[i] dry-run: gh {shown}")
        return
    _gh(args)
    print(f"[+] gh {shown}")


def setup_labels(repo: str, apply: bool) -> None:
    repo = ensure_fork(repo)
    for name, color, description in LABELS:
        _run_write(
            [
                "label",
                "create",
                name,
                "--repo",
                repo,
                "--color",
                color,
                "--description",
                description,
                "--force",
            ],
            apply,
        )


def _existing_demo_sources(repo: str) -> set[int]:
    raw = _gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--label",
            DEMO_LABEL,
            "--limit",
            "200",
            "--json",
            "body",
        ]
    )
    pattern = re.compile(r"apm-demo-source: " + re.escape(UPSTREAM_REPO) + r"#(\d+)")
    found: set[int] = set()
    for item in json.loads(raw or "[]"):
        found.update(int(n) for n in pattern.findall(item.get("body") or ""))
    return found


def copy_issues(repo: str, apply: bool, link_style: str) -> None:
    repo = ensure_fork(repo)
    try:
        existing = _existing_demo_sources(repo)
    except DemoError:
        if apply:
            raise
        existing = set()  # label may not exist yet during a dry-run
    for number in DEMO_ISSUES:
        if number in existing:
            print(f"[i] skip: {UPSTREAM_REPO}#{number} already copied")
            continue
        raw = _gh(
            [
                "issue",
                "view",
                str(number),
                "--repo",
                UPSTREAM_REPO,
                "--json",
                "number,title,body,author,createdAt",
            ]
        )
        title, body = build_demo_issue(json.loads(raw), link_style=link_style)
        if not apply:
            print(f"[i] dry-run: would create in {repo} with label '{DEMO_LABEL}': {title}")
            continue
        _gh(
            [
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body",
                body,
                "--label",
                DEMO_LABEL,
            ]
        )
        print(f"[+] created demo copy of {UPSTREAM_REPO}#{number}: {title}")


def disable_other_workflows(repo: str, apply: bool) -> None:
    repo = ensure_fork(repo)
    raw = _gh(["workflow", "list", "--repo", repo, "--all", "--json", "id,name,path,state"])
    for wf in json.loads(raw or "[]"):
        path = wf.get("path") or ""
        if path.endswith("/" + PANEL_WORKFLOW):
            print(f"[i] keep: {path} ({wf.get('state')})")
            continue
        if wf.get("state") != "active":
            print(f"[i] already {wf.get('state')}: {path}")
            continue
        _run_write(["workflow", "disable", str(wf["id"]), "--repo", repo], apply)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=("labels", "issues", "workflows", "all"))
    parser.add_argument(
        "--repo", default=FORK_REPO, help=f"target fork (only {FORK_REPO} is accepted)"
    )
    parser.add_argument("--apply", action="store_true", help="perform writes (default: dry-run)")
    parser.add_argument(
        "--link-style",
        choices=("clickable", "code"),
        default="clickable",
        help="clickable original links may add a 'mentioned' event on the upstream issue; 'code' avoids it",
    )
    args = parser.parse_args(argv)
    try:
        ensure_fork(args.repo)
        if args.command in ("labels", "all"):
            setup_labels(args.repo, args.apply)
        if args.command in ("issues", "all"):
            copy_issues(args.repo, args.apply, args.link_style)
        if args.command == "workflows":
            disable_other_workflows(args.repo, args.apply)
    except DemoError as exc:
        print(f"[x] {exc}", file=sys.stderr)
        return 1
    if not args.apply:
        print("[i] dry-run only; re-run with --apply to write to the fork")
    return 0


if __name__ == "__main__":
    sys.exit(main())
