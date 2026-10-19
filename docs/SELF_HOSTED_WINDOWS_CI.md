# Yorika self-hosted Windows acceptance (manual / trusted main only)

## Purpose

Run Python, SQLite concurrency/restore, PowerShell, DPAPI and updater tests on the
registered `yorika-home` or `yorika-work` machine, without using paid GitHub-hosted
minutes. Workflow: `.github/workflows/selfhosted-windows-acceptance.yml`.

## Security conditions — important

- Only a dedicated, non-admin, unprivileged Windows user should run this agent.
  Do not use an account with Cloud.ru secrets, browser profiles, work documents,
  corporate VPN credentials, SSH keys, or access to production Yorika data.
- On an employer-owned machine, require explicit authorization.
- Treat self-hosted runners as persistent execution environments, **not** as
  isolated VMs; repository test code can read everything available to the agent.
- Do not assign `yorika-ci` to runners handling untrusted repos or workflows.
- This new workflow is manual-only (`workflow_dispatch`) and its job only
  executes on `main` in `Aspksa/Yorika`. Existing push/PR workflows remain
  on GitHub-hosted runners; do not blanket-convert them to self-hosted.
- Ensure repository administration / branch protections prevent untrusted
  changes to `main` before dispatch. Manual `main` gating is **not** a
  substitute for review and a restricted Windows account.
- All steps require only `contents: read`; checkout disables persisted
  GitHub credentials. Secrets are not passed through the workflow.

## Local prerequisites

1. Register runner on the PC with labels `self-hosted`, `Windows`, `X64`
   and `yorika-ci`. Confirm status **Idle**.
2. Install Python 3.12 (on PATH) and Node.js 22; PowerShell 7 is required
   for `pwsh`. Allow runner access to GitHub and official actions downloads.
3. Start `run.cmd` from a dedicated local runner directory, not USB.
4. Verify the checkout location is disposable. Do **not** keep production
   SQLite files or credentials under runner's working directories.

## Running checks

GitHub → Aspksa/Yorika → Actions → **Yorika trusted Windows self-hosted acceptance**
→ **Run workflow** → select `main` → **Run workflow**.

Report: `yorika-acceptance.json` attached as
`yorika-selfhosted-acceptance` artifact when the runner executes its steps.

Passing tests demonstrate local automated test coverage only. Manual Windows
browser multitab and end-to-end recovery acceptance still require evidence.

## If the run stays queued

Confirm the runner is online (Idle) and has exactly the selected custom label
`yorika-ci`; standard Windows/X64 labels are added by GitHub registration.
Check local Python/Node/pwsh paths. Read job logs on the run page.

## Running locally without Actions

Inside the repository checkout:
```powershell
python scripts/run-acceptance.py --report yorika-acceptance.json
```
