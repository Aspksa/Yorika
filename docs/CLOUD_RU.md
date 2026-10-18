# Cloud.ru — подключение и безопасное хранение ключей

**Status:** planned, no provider connection or secret vault implemented yet. Work items: `CLOUD-002` through `CLOUD-006`, then `CLOUD-001`.

## Provider authentication — verify by target service

Cloud.ru has multiple auth mechanisms:

- IAM access key pair: `keyId` (Key ID) and `secret` (Key Secret), preferably for a least-privilege **service account**. For services using IAM, exchange them via official IAM token endpoint `POST https://iam.api.cloud.ru/api/v2/auth/token` (v1 may still exist for some services). Present resulting token as `Authorization: Bearer ...` and refresh when required.
- Some services use a **service-account static API key** as `Authorization: Api-Key ...`. Do not automatically treat this as an IAM key pair; verify the selected service's API documentation before any request.
- Official sources: https://cloud.ru/docs/console_api/ug/topics/guides__auth_api and https://cloud.ru/docs/administration/ug/topics/api-ref__authentication

## Credential storage: Windows 10+, per user

1. UI collects credentials using password inputs. Never include secrets in URL, diagnostics, telemetry, JavaScript-readable persistent storage or HTML page state after saving.
2. Server accepts the secret through a same-origin protected operation, validates request origin and requires a session protection mechanism; no unauthenticated secret retrieval endpoint, even on localhost.
3. Encrypt the secret bytes via **Windows DPAPI CurrentUser** and save encrypted blob under `%LOCALAPPDATA%\\Yorika\\secrets` with user-only NTFS permissions; keep outside update releases. Use atomic file replacement and inspect ACLs on Windows.
4. On restart decrypt only within the designated local backend user context. Never reveal full secrets to the website; only return connection state, credential type and masked identifier.
5. Provide explicit `Check connection`, `Delete local credentials`, `Rotate` operations. Deleting local file does **not** revoke keys at Cloud.ru: clearly distinguish local deletion from provider revocation.
6. Do not add secrets to SQLite export, manual browser export, backup archives, Git commits, screenshots or logs. Backups of protected secrets require separate opt-in and restore instructions; DPAPI user/machine context is not necessarily portable.
7. Support missing Python, offline mode, invalid credentials, expired/revoked tokens, denied project permissions, multiple Cloud.ru services and user-initiated disconnect.

## Optional training integration

- Disabled by default. No background paid cloud training.
- Show target project/service, minimum permissions, estimate, maximum runtime and budget **before** execution.
- User confirms each billable job; add stop controls and post-run cost reporting when reliable. Default monthly spending goal 1,000 RUB is a *local guard*, not a guaranteed external account hard limit. Recommend provider-side billing alerts/quotas where available.
- Store job IDs and sanitized statuses only, never credentials or tokens.
- No upload of private memories/conversation history/training corpora without explicit separate consent.
- Do not mark job complete until remote shutdown/deallocation is verified to prevent running charges.

## Acceptance test matrix

| Task | Testable acceptance |
|---|---|
| CLOUD-003 | DPAPI encryption/decryption for current Windows user, user-only file ACL, no plaintext on disk/logs, delete/rotate, backup behavior |
| CLOUD-002 | connect/disconnect account and masked status, no Python start regression |
| CLOUD-004 | valid/invalid key, token expiry, service auth variant, network timeout and revoked permissions |
| CLOUD-005 | UI settings state, update/restart persistence, accessibility, passwords never re-displayed |
| CLOUD-006 | independent consent for billable runs, local budget accounting, negative cases, cancel/stop |
| CLOUD-001 | representative sandbox cloud training/checkpoint retrieval, resource shutdown and cost verification |

Until all applicable tests pass, these remain unchecked in `docs/ROADMAP.md` and `planning/tasks.json`. No user secret is requested in chat or stored in the repository.
