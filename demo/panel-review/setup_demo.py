#!/usr/bin/env python3
"""Prepare the richard-fowles-epam/apm fork for the panel-review demo.

Dry-run by default. Pass --apply to write. Every write targets the demo
fork only; the script refuses any other repository, including
microsoft/apm. Upstream issues are only read with `gh issue view`.

Subcommands:
  labels     create/update the labels the panel-review flow needs
  issues     create demo issues in the fork from selected upstream issue text,
             with every link, mention and reference to the source removed
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

DEMO_ISSUES: tuple[int, ...] = (2986, 3593, 3351, 3056, 3110)

LABELS: tuple[tuple[str, str, str], ...] = (
    ("panel-review", "5319e7", "Trigger: run the advisory PR review panel"),
    ("status/accepted", "0e8a16", "Maintainer-accepted; required before panel review"),
    (DEMO_LABEL, "fbca04", "Demo issue for the panel-review walkthrough; not tracked work"),
)

DEMO_BANNER = (
    "> [!NOTE]\n"
    "> **Demo issue for the panel-review walkthrough. Not tracked work.**\n"
    "> Created in this fork for demonstration purposes only.\n"
    "\n"
    "---\n"
    "\n"
)

REF_TEXT = "a related issue"
MENTION_TEXT = "a user"
REPO_TEXT = "the project repository"

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
_MD_GH_LINK_RE = re.compile(r"\[([^\]]*)\]\(https?://github\.com/[^)]*\)")
_GH_ISSUE_URL_RE = re.compile(
    r"https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull|discussions)/\d+(?:[\w#/?=&.-]*[\w/=])?"
)
_UPSTREAM_URL_RE = re.compile(
    r"https?://github\.com/microsoft/apm(?:[/?#][\w#/?=&.%-]*[\w/=])?", re.IGNORECASE
)
_QUALIFIED_REF_RE = re.compile(r"(?<![\w/`])[\w.-]+/[\w.-]+#\d+\b")
_BARE_REF_RE = re.compile(r"(?<![\w&/`#])#\d+\b")
_MENTION_RE = re.compile(r"(?<![\w`/.@])@[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:/[\w.-]+)?")
_UPSTREAM_NAME_RE = re.compile(r"\bmicrosoft/apm\b(?!-)", re.IGNORECASE)
_WHOLE_REF_RE = re.compile(r"(?:[\w.-]+/[\w.-]+)?#\d+")
_WHOLE_MENTION_RE = re.compile(r"@[A-Za-z0-9][A-Za-z0-9-]{0,38}(?:/[\w.-]+)?")


class DemoError(RuntimeError):
    """Raised for unsafe or failed demo setup actions."""


def ensure_fork(repo: str) -> str:
    """Return the fork slug if repo is the demo fork; refuse everything else."""
    if repo.strip().lower() != FORK_REPO.lower():
        raise DemoError(f"refusing to write to {repo!r}; only {FORK_REPO} is allowed")
    return FORK_REPO


def _strip_text(segment: str) -> str:
    segment = _GH_ISSUE_URL_RE.sub(REF_TEXT, segment)
    segment = _UPSTREAM_URL_RE.sub(REPO_TEXT, segment)
    segment = _QUALIFIED_REF_RE.sub(REF_TEXT, segment)
    segment = _BARE_REF_RE.sub(REF_TEXT, segment)
    segment = _MENTION_RE.sub(MENTION_TEXT, segment)
    return _UPSTREAM_NAME_RE.sub(REPO_TEXT, segment)


def _strip_code_span(span: str, content: str) -> str:
    if _WHOLE_REF_RE.fullmatch(content):
        return REF_TEXT
    if _WHOLE_MENTION_RE.fullmatch(content):
        return MENTION_TEXT
    return span


def _strip_line(line: str) -> str:
    line = _MD_GH_LINK_RE.sub(lambda m: m.group(1), line)
    out: list[str] = []
    pos = 0
    for match in _INLINE_CODE_RE.finditer(line):
        out.append(_strip_text(line[pos : match.start()]))
        out.append(_strip_code_span(match.group(0), match.group(2)))
        pos = match.end()
    out.append(_strip_text(line[pos:]))
    return "".join(out)


def sanitize_body(body: str) -> str:
    """Remove every link back to the source issue tracker and its people.

    Outside code, @mentions become "a user", issue/PR references and
    issue URLs become "a related issue", other links to the source
    repository keep only their text, and the repository name is replaced.
    Inline code spans that are only a reference or mention are replaced
    the same way. Fenced code is left as-is; build_demo_issue refuses the
    result if anything still names the source repository.
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
        result.append(_strip_line(line))
    return "\n".join(result)


def build_demo_issue(issue: dict) -> tuple[str, str]:
    """Return (title, body) for a demo issue with no tie to its source."""
    title = f"[DEMO] {_strip_line(str(issue['title']))}"
    body = DEMO_BANNER + sanitize_body(issue.get("body") or "")
    if UPSTREAM_REPO.lower() in (title + body).lower():
        raise DemoError(f"demo issue still references the source repository: {title}")
    return title, body


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


def _existing_demo_titles(repo: str) -> set[str]:
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
            "title",
        ]
    )
    return {item.get("title") or "" for item in json.loads(raw or "[]")}


def copy_issues(repo: str, apply: bool) -> None:
    repo = ensure_fork(repo)
    try:
        existing = _existing_demo_titles(repo)
    except DemoError:
        if apply:
            raise
        existing = set()  # label may not exist yet during a dry-run
    for number in DEMO_ISSUES:
        raw = _gh(["issue", "view", str(number), "--repo", UPSTREAM_REPO, "--json", "title,body"])
        title, body = build_demo_issue(json.loads(raw))
        if title in existing:
            print(f"[i] skip: already exists: {title}")
            continue
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
        print(f"[+] created: {title}")


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
    args = parser.parse_args(argv)
    try:
        ensure_fork(args.repo)
        if args.command in ("labels", "all"):
            setup_labels(args.repo, args.apply)
        if args.command in ("issues", "all"):
            copy_issues(args.repo, args.apply)
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
