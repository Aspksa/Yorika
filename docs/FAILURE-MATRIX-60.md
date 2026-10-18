# Yorika — 60 failure-scenario checklist

Status legend: **Covered** = specific mitigation exists in code (not a Windows-tested guarantee); **Unverified** = needs device/integration test; **Future** = not implemented. All scenarios require Windows integration validation before release.

## Windows & process

| # | Failure scenario | Status |
|---:|---|---|
| 1 | BAT missing | Unverified |
| 2 | PowerShell missing | Unverified |
| 3 | execution policy | Unverified |
| 4 | PowerShell non-STA | Unverified |
| 5 | WinForms load failure | Unverified |
| 6 | Windows update changes | Unverified |
| 7 | duplicate same-folder process | Covered |
| 8 | different-folder process | Covered |
| 9 | process exit during bootstrap | Unverified |
| 10 | console hides fatal error | Covered |

## Paths & media

| # | Failure scenario | Status |
|---:|---|---|
| 11 | Cyrillic directory | Covered |
| 12 | path with spaces | Covered |
| 13 | OneDrive sync folder | Covered |
| 14 | external SSD/USB drive | Covered |
| 15 | drive-letter change | Covered |
| 16 | long path | Unverified |
| 17 | read-only location | Unverified |
| 18 | offline/network mapped drive | Unverified |
| 19 | missing www files | Covered |
| 20 | media unplugged during run | Unverified |

## HTTP server

| # | Failure scenario | Status |
|---:|---|---|
| 21 | occupied fixed port avoided | Covered |
| 22 | port released on exit | Covered |
| 23 | TCP bind permission denied | Unverified |
| 24 | HTTP response readiness | Covered |
| 25 | stale ready.url | Covered |
| 26 | wrong service on old port | Covered |
| 27 | partial HTTP request | Unverified |
| 28 | invalid encoded URI | Unverified |
| 29 | directory traversal | Unverified |
| 30 | simultaneous client requests | Unverified |

## Browser & tray

| # | Failure scenario | Status |
|---:|---|---|
| 31 | no default browser | Unverified |
| 32 | browser launch failure | Unverified |
| 33 | browser runs but 404 | Unverified |
| 34 | icon under overflow chevron | Unverified |
| 35 | tray icon fails to initialize | Unverified |
| 36 | Windows Explorer restarts | Future |
| 37 | tray double-click handler | Unverified |
| 38 | copy address operation | Unverified |
| 39 | exit menu releases socket | Unverified |
| 40 | reopen running server | Covered |

## Data foundation

| # | Failure scenario | Status |
|---:|---|---|
| 41 | IndexedDB blocked | Unverified |
| 42 | private browsing storage | Unverified |
| 43 | random-port origin change | Future |
| 44 | browser profile switch | Unverified |
| 45 | site data wiped | Unverified |
| 46 | quota exceeded | Future |
| 47 | schema upgrade | Future |
| 48 | bad record ID | Covered |
| 49 | interrupted database write | Unverified |
| 50 | backup restore unavailable | Future |

## Resilience & security

| # | Failure scenario | Status |
|---:|---|---|
| 51 | logs not writable | Future |
| 52 | log file grows indefinitely | Future |
| 53 | firewall interference | Unverified |
| 54 | localhost-only binding | Covered |
| 55 | unexpected HTTP method | Covered |
| 56 | malformed file extensions | Unverified |
| 57 | resource exhaustion | Future |
| 58 | process recovery policy | Future |
| 59 | portable permissions | Unverified |
| 60 | manual recovery instructions | Unverified |

## Release gates

1. Run `Yorika.bat` from a directory with Cyrillic and spaces, from OneDrive, and from a removable volume.
2. Confirm `127.0.0.1` response carries `X-Yorika-App: Yorika`, and the browser is opened only after this check.
3. Test a second launch, a moved folder, a stale `ready.url`, and immediate exit through tray.
4. Test error paths through `Yorika-Debug.bat` and inspect `.yorika/yorika.log`.
5. Do not use IndexedDB with rotating ports as durable data. Implement stable storage before saving important user content.

No claim is made that all 60 checks have passed. This file is a forward-looking verification inventory.
