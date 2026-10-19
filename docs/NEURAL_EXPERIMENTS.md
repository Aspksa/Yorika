# Neural Experiment Suite — Yorika native model only

`backend/neural_experiment.py` builds a deterministic disjoint training/held-out split, trains a local experimental checkpoint and evaluates it **only** on held-out prompts. A SHA-256 fingerprint binds the result to the precise evaluation examples; a mismatch is rejected. Temporary checkpoints are discarded and no candidate is automatically promoted. No external LLM or Ollama is used.

The experiment needs optional PyTorch when the real trainer is used. The unit suite uses injected trainers to verify isolation without requiring GPU libraries. The existing PyTorch CPU smoke verifies execution on synthetic training examples, not general conversational quality.

`run_experiment(examples, steps=2, seed=42)` requires five or more approved prompt-answer pairs. Its exact-match score is narrow and does not establish semantic quality or safety. Compare results only for the same held-out corpus with `compare_runs(baseline, candidate)`. Do not use real private chats without explicit consent or upload datasets/checkpoints to source control.

The following remain unverified: useful held-out performance, CUDA training, RTX 3050 4 GB resource limits and Windows GUI acceptance.
