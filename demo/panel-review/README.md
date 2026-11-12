# Panel-review demo on the richard-fowles-epam/apm fork

This folder prepares the fork `richard-fowles-epam/apm` for a live demo of
the advisory **PR Review Panel** (`.github/workflows/pr-review-panel.md`).
Everything here targets the fork only. Nothing writes to `microsoft/apm`.

What was adapted on this branch:

| Area | Change |
|------|--------|
| Workflow | Only runs when `github.repository == 'richard-fowles-epam/apm'`. Imports skills from `richard-fowles-epam/apm#main`. Safe outputs limited to the fork. Lock recompiled with gh-aw v0.89.15. |
| Scheduler, worker, comment skills | Every `gh` call uses `--repo richard-fowles-epam/apm`. Still advisory only: one comment, no verdict labels, no merge. |
| Personas | `apm-ceo` and `oss-growth-hacker` query the fork, never upstream. |
| CODEOWNERS | `* @richard-fowles-epam` |
| Dashboard | Defaults to the fork. Override with `APM_DASHBOARD_REPO`; `microsoft/apm` is refused. |
| `setup_demo.py` | Creates the labels and demo issues and disables other workflows. Dry-run by default; refuses any repo other than the fork. |

## Before the demo (one-time setup)

Run every command from the repo root. Each step writes to GitHub, so run
it only when you mean to.

### 1. Confirm the target

```bash
gh repo view richard-fowles-epam/apm --json nameWithOwner,isFork,parent
```

Expect `isFork: true` with parent `microsoft/apm`.

### 2. Land this branch on the fork's `main`

`pull_request_target` runs the workflow from the **base branch**, and the
workflow imports skills from `richard-fowles-epam/apm#main`. So the
changes must be on the fork's `main`. Always pass `--repo` so the PR
does not default to upstream:

```bash
git push -u origin HEAD
gh pr create --repo richard-fowles-epam/apm --base main \
  --head richard-fowles-epam-panel-review-demo-fork \
  --title "Demo: retarget panel-review to fork" --body "Fork-only demo setup."
gh pr merge --repo richard-fowles-epam/apm --merge <PR_NUMBER>
```

### 3. Keep only the panel workflow enabled

The fork has about 26 workflows. Disable all of them except
`pr-review-panel.lock.yml`:

```bash
python3 demo/panel-review/setup_demo.py workflows           # dry-run
python3 demo/panel-review/setup_demo.py workflows --apply
gh workflow list --all --repo richard-fowles-epam/apm       # verify
```

If Actions are still off for the fork, open
<https://github.com/richard-fowles-epam/apm/actions> and select
**I understand my workflows, go ahead and enable them**. Then re-run the
`workflows --apply` step, because enabling Actions can re-activate workflows.

### 4. Labels and demo issues

```bash
python3 demo/panel-review/setup_demo.py all                 # dry-run
python3 demo/panel-review/setup_demo.py all --apply
```

This creates `panel-review`, `status/accepted` and `demo`. It then copies
five upstream issues as `[DEMO] ...` issues: microsoft/apm #2986, #3593,
#3351, #3056 and #3110. Each copy has a demo banner, the original link and
a hidden source marker, so re-running the script skips issues it already
copied. Comments, labels and assignees are not copied. Mentions and
cross-references are shown as code, so nobody is notified.

A clickable original link can add a "mentioned" event on the upstream
issue. Use `--link-style code` to avoid that.

### 5. Copilot authentication (secret)

The workflow needs the repository secret `COPILOT_GITHUB_TOKEN`. Use a
**fine-grained personal access token**:

1. Open the pre-filled form:
   <https://github.com/settings/personal-access-tokens/new?name=COPILOT_GITHUB_TOKEN&description=GitHub+Agentic+Workflows+-+Copilot+engine+authentication&user_copilot_requests=read>
2. Set **Resource owner** to your user account.
3. Under Account permissions, keep **Copilot Requests: Read**. Add nothing
   else. Set a short expiry.
4. Store it without echoing it to your shell history:

   ```bash
   gh secret set COPILOT_GITHUB_TOKEN --repo richard-fowles-epam/apm
   ```

   `gh` prompts for the value with hidden input. You can also use
   Settings > Secrets and variables > Actions > New repository secret.

Never use `--value`, never commit the token, and never paste it into a
chat. `gho_` OAuth tokens are rejected. A classic PAT does not work.

Verify that the secret exists (the value is never shown):

```bash
gh secret list --repo richard-fowles-epam/apm
```

### 6. Dashboard (optional)

```bash
apm experimental enable canvas
apm approve richard-fowles-epam/apm/packages/apm-contributor-dashboard
apm install richard-fowles-epam/apm/packages/apm-contributor-dashboard
```

This resolves from the fork, so run it after step 2.

Then ask Copilot CLI: "Open the APM Contributor Dashboard". It shows the
fork's issues and PRs by default. To change that, set
`APM_DASHBOARD_REPO=<owner>/<name>` before starting Copilot CLI.

## Demo script

1. Show the `[DEMO]` issues in the fork (dashboard Issues tab or
   `gh issue list --repo richard-fowles-epam/apm --label demo`).
2. Pick one, for example the docs one copied from microsoft/apm#2986.
   Fix it on a branch and open a PR **in the fork**:

   ```bash
   git switch -c demo/fix-docs
   # ...edit, commit...
   git push -u origin HEAD
   gh pr create --repo richard-fowles-epam/apm --base main \
     --title "docs: ..." --body "Fixes #<DEMO_ISSUE_NUMBER>"
   ```

3. Accept the work. The scheduler requires `status/accepted` on the PR or
   on its linked fork issue ("no accepted, no review"). Labelling the PR
   is the most direct option:

   ```bash
   gh pr edit <PR> --repo richard-fowles-epam/apm --add-label status/accepted
   ```

4. Trigger the panel. Use any one of these:
   - `gh pr edit <PR> --repo richard-fowles-epam/apm --add-label panel-review`
   - The dashboard **Run Panel** button on the PR
   - `gh workflow run pr-review-panel.lock.yml --repo richard-fowles-epam/apm -f pr_number=<PR>`
5. Watch the run:
   `gh run list --repo richard-fowles-epam/apm --workflow pr-review-panel.lock.yml`
6. Expect **one** advisory comment on the PR, and the `panel-review` label
   removed. The panel does not add verdict labels, merge, assign or
   request reviewers. You decide whether to merge.

To re-run, remove and re-add `panel-review`.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Run shows Skipped | The label was not `panel-review`, or the repository is not the fork. |
| Activation fails with a missing secret | `COPILOT_GITHUB_TOKEN` is not set, has expired, or lacks Copilot Requests. |
| Run waits for approval | The fork requires approval for outside actors. Approve it in the Actions tab or use the dashboard. |
| Panel posts "no review" | `status/accepted` is missing, or the last CODEOWNERS comment has unmet conditions. Don't leave conditional comments on the demo PR. |
| Old behaviour or wrong repo | The fork's `main` does not have this branch yet (step 2). |
| Run fails with a Copilot quota error | Your Copilot plan has no premium requests left. |

## Known limits

- The run downloads `microsoft/apm-action` and the APM CLI from public
  upstream releases. These are read-only and never write upstream.
- Syncing the fork with upstream can conflict with or revert this
  retargeting. Check the workflow guard and lock after any sync.
- Each panel run uses Copilot premium requests from your account.
