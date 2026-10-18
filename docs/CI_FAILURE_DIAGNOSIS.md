# GitHub Actions failure diagnosis — 2026-10-19

Checked workflow runs on main at `4ce65306cb8f605fd13715660d789491e24d22bd`:

- Chat memory safety: https://github.com/Aspksa/Yorika/actions/runs/39177847582
- Windows PowerShell validation: https://github.com/Aspksa/Yorika/actions/runs/39177847487

Both Windows and Ubuntu job records report `conclusion=failure` with `steps=null`. Job log retrieval for jobs `117824112958`, `117824113189`, and `117824112642` returned HTTP 404 with `BlobNotFound`. No runner step log or traceback is available. **The root cause is not proven.** Do not change test code merely to silence these infrastructure-level results.

## Actions to check in GitHub settings

1. Check repository Settings → Actions → General: enabled workflows and allowed actions.
2. Check repository Settings → Actions → Runners: availability and GitHub-hosted runner permissions.
3. Inspect billing, spending limits, account restrictions, and repository Actions notices; ask repository admin / GitHub Support for server-side job scheduling failure detail if no notices are shown.
4. Start an explicit `workflow_dispatch` after resolving any setting/account restriction; require jobs to show checkout/test steps before interpreting results.
5. Only after actual runner execution verify both Python unittest and PowerShell/Windows acceptance. Never mark Windows acceptance complete from Linux runs.

## Reproducible offline tests

```sh
python -m unittest discover -s tests -p 'test_chat_memory_regressions.py' -v
python -m unittest discover -s tests -v
python scripts/check-plan.py
```

These tests are repository instructions, not recorded passing test executions.
