# Neural multi-candidate evaluation

`python scripts/compare-neural-candidates.py` (from repository root with `PYTHONPATH=.`) runs **two real tiny Transformer CPU training experiments** using 10 synthetic question/answer pairs. The deterministic hold-out split is fixed across candidates, and each experiment creates and then deletes its temporary checkpoint. The generated answers are evaluated for exact matches, not subjective conversational quality.

`backend/neural_multi_experiment.py` compares two to five candidates, rejects mismatched training/held-out fingerprints, records elapsed wall-clock seconds and Python heap peak (tracemalloc), and returns an explicit `auto_promoted: false`. Its `python_peak_bytes` is **not** total process RSS, native PyTorch memory or GPU VRAM.

The real GitHub PyTorch workflow runs the two-candidate experiment in addition to the pre-existing train/infer smoke. For a Windows RTX 3050 (4 GB), real GPU memory/speed acceptance remains **not verified**, because the current training and generation paths run on CPU. Do not mark the GPU acceptance task done without actual measurements.
