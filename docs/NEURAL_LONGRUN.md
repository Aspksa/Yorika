# Yorika long-running training and recovery

The `backend.neural_longrun.run_long_training` function executes a bounded training schedule of the **same own Transformer** in checkpoint-sized segments. It saves a unique, immutable checkpoint after each segment and atomically advances `training-progress.json` after syncing the manifest file. A restart verifies the checkpoint's SHA-256 before continuing with the exact AdamW/CPU-RNG/data-cursor restore mechanism.

Configuration is capped at 10,000 total training steps, at most 24 hours of wall-clock time per invocation and a 100 MB per-checkpoint disk budget. These are **budgets at checkpoints**, not an operating-system-enforced RAM or VRAM cap; a single training interval can exceed the requested time. Checkpoints accumulate and must be reviewed for storage use.

This is cooperative restart, **not** an always-running watchdog. Crashes during a checkpoint write may produce an orphan `.pt` requiring operator inspection. Existing checkpoints and the active brain selection are never replaced automatically. The current exact-resume proof and live CI run on CPU, not RTX 3050. Ollama is excluded.
