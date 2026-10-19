# Neural Engine 4 — verified CPU experiment

The experimental neural model is **not** the production chat engine. Its tiny character-level Transformer is a functional demonstration, not a useful conversational model.

## Real CPU acceptance

The dedicated GitHub workflow `Neural Engine real PyTorch smoke` installs CPU PyTorch in an isolated Ubuntu runner and executes:

```powershell
python -m backend.neural_smoke --steps 2
```

This trains only on synthetic phrases, saves its checkpoint to an automatically deleted temporary directory, reloads with `weights_only=True`, and generates eight tokens. The JSON report includes training/inference wall time, checkpoint size and losses. No user profile, Cloud.ru credentials or real chat history is accessed.

To run locally, install PyTorch separately with the wheel recommended for your operating system and hardware. Start with CPU; the current training/inference implementation does not use RTX acceleration. **Do not conclude model quality merely from a successful smoke test or a lower training loss.**

## Safety and scope

- The experimental checkpoint is not automatically activated.
- The GitHub workflow has read-only repository permissions and a 15-minute job timeout.
- The measured results depend on the runner and are **not** a benchmark of an RTX 3050 4 GB.
- Actual response quality, held-out evaluation, GPU memory and production-chat integration remain separate acceptance tasks.
