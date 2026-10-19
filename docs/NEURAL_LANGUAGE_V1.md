# Yorika Language Brain v1 — first genuine language-learning slice

The new versioned experimental core uses a **lossless UTF-8 byte tokenizer** (261 tokens including special tokens), a randomly initialized two-layer causal Transformer, masked assistant-token cross-entropy, independent heldout negative log-likelihood (NLL), and text generation. This is a separate `yorika-language-v1` checkpoint format; existing legacy checkpoints and the single active model remain unchanged. No Ollama.

`backend.neural_language_corpus.prepare_corpus` requires explicit consent, source and allowed licensing values for accepted records, deduplicates/splits by prompt, and records train/evaluation fingerprints. It is a validation foundation, **not** a complete personal-data, license or secret scanner; use only data specifically authorized for experiments.

The CI exercises actual CPU PyTorch on **synthetic Russian data**: train one model, measure heldout NLL, generate a bounded response. Do not interpret this as demonstration of useful dialogue. Byte tokens are lossless but relatively inefficient for Russian; future tokenizer experiments may introduce learned BPE with a new explicit version and migration policy. The current v1 weights are still a tiny architecture, not the 5–10M parameter goal and not CUDA/RTX 3050 validated.

Future gates: increase data quality/size, train with validation curves, model selection on validation and one untouched test corpus, incorporate checkpointed optimizer/RNG for v1, show human-evaluated answers, and run genuine Windows GPU benchmarks. Do not change active-brain manifest until human-reviewed quality gates pass.
