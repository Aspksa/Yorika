# Yorika AI architecture: verified baseline and growth design

## Historical snapshot warning

This document's initial baseline describes an earlier commit. For up-to-date capabilities read current code and [YORIKA_VISION.md](YORIKA_VISION.md). Current main already contains experimental SQLite/PowerShell chat integration (PR #16), but Windows end-to-end behavior is not verified. Never interpret historical text below as live status.

## Verified baseline
As of 2026-10-18, main head f3b2efca11ec10b979f61eff175ef313fe7d8588: a PowerShell static localhost site via Yorika.bat → scripts/start.ps1 → scripts/yorika-tray.ps1; updater, settings, floating fox avatar and shared chat UI. IndexedDB in www/core/database.js contains settings/projects/memories/conversations/messages/tasks. www/avatar.js stores last 200 messages in localStorage and exposes window.YorikaChat.setResponder(...). **No local AI inference, model training, SQLite or proactive engine is installed.** Windows end-to-end runtime needs real-device tests.

## Technical approach: one stable application, replaceable brains

```text
Yorika.bat -> tray + loopback HTTP -> static www/
                             | same-origin /api/*
                             v
                     Local Python supervisor (optional)
                         | SQLite stable data dir
                         | Memory retrieval + provenance
                         | Task scheduler + initiative policy
                         | Inference engine (own checkpoint)
                         | Experiment runner (isolated)
                         v
                   Registry of model generations
```

### Data
Choose stable per-user application data dir (e.g. Windows LocalAppData/Yorika; exact path must be documented and tested), never inside updater release folders. Write atomic migration from browser data: discover/export accessible old ports, deduplicate by stable IDs, reversible conversion and user confirmation. Keep original export snapshots. Schema changes versioned and tested with restore. SQLite FTS5, event log, chronological facts and sources; embedding/vector index is disposable/rebuildable. File archival with integrity hashes, encryption when appropriate, consent/privacy controls and retention.

### Neural model
Separate tokenizer, from-random-init small Transformer, inference, trainer, checkpointing, evaluation. Target 5–10M parameters initially on RTX 3050 4GB, 16GB RAM. PyTorch behind optional dependencies; never break no-Python launcher. Snapshot git revision, config, data provenance, seed and model hash for experiments. Quality measured with held-out corpus and safety/consistency tests. Big models and spiking/liquid/world-model experiments only after reproducible baseline.

### Living-like behavior, not literal life
Persistent **event-driven** cognitive state: `idle`, `responding`, `researching`, `training`, `consolidating`, `paused`, with task owner, budgets and checkpoint. A proactive message requires: opt-in; confirmed real trigger; duplicate-suppression; no quiet-hours breach; clear provenance; no fabricated completed work. Never run GPU endlessly just to simulate thinking. Windows notifications while browser closed only if the local tray process actually runs. Voice must be explicit opt-in, clear mic indication and shutoff.

### Learning loop
1. Collect opt-in allowed data/event.
2. Preserve immutable source and derived hypothesis separately.
3. Construct candidate examples, filter PII/license/quality.
4. Run bounded offline experiment; record checkpoint and exact metrics.
5. Regression-test skills and memory, approve/reject candidate.
6. Promote model generation only with human approval; preserve rollback.
7. New model reads long-term memory through a stable schema; not through imaginary neuron continuity.

### Security
Loopback-only does not prevent cross-site requests to localhost. Validate Origin/Host, protect state-changing endpoints, authenticate local UI when needed, whitelist paths and isolate agent processes; no unrestricted plugin JavaScript on same origin. External/cloud execution needs per-run informed approval and budget cap.

### Persona source (user upload)
`kitsune_love_loyalty_526_ru.json`: 526 replies, 27 categories, ru-RU, adult fictional fox-girl; optional `хозяин` form of address with consent; feminine narration, warmth, honesty, varied context-sensitive phrases, no emoji. This is a **style dataset**, not 526 true memories or trained neural abilities. Use only appropriately and never claim actual romantic emotion. Do not assume the uploaded file automatically exists in GitHub.

### Future research bets, not features already present
Continual learning with replay; testable neural structural adaptation; world models learned inside bounded virtual environments; small specialist model routing; objective evaluation of self-improvement. Maintaining 50-year compatibility requires migrations and periodic backups/tests, not a guarantee.
