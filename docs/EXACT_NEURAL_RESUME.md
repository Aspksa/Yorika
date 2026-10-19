# Exact CPU training continuation — Yorika

For checkpoints trained with the new schema, `backend.neural_exact_resume.exact_resume(examples, source, output, additional_steps=N)` restores **model weights, AdamW optimizer state, PyTorch CPU RNG state, training step and dataset cursor**. The SHA-256 of the ordered training examples must match exactly. The original checkpoint and single active-brain pointer are unchanged.

The real PyTorch CI acceptance compares a four-step uninterrupted training run with a two-step run followed by two resumed steps, requiring identical weight tensors and RNG state.

Restrictions: CPU-only reproducibility for current deterministic architecture; no CUDA RNG state, no optimizer-independent cross-version reproducibility guarantee, no automatic best-model promotion. Old checkpoint versions lacking optimizer state cannot exact-resume; use legacy weight continuation. Checkpoint must be locally generated and trusted, not downloaded. Ollama is excluded.
