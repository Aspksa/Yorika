"""Real CPU PyTorch proof of exact continuation including AdamW moments."""
import tempfile
from pathlib import Path
import torch
from backend.training_engine import train
from backend.neural_exact_resume import exact_resume


def main():
    examples = [("Привет", "Здравствуйте"), ("Как дела", "Нормально")]
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        full, first, resumed = (folder / name for name in ("full.pt", "first.pt", "resumed.pt"))
        train(examples, full, steps=4, width=32, heads=4, context=32)
        train(examples, first, steps=2, width=32, heads=4, context=32)
        result = exact_resume(examples, first, resumed, additional_steps=2)
        whole = torch.load(full, map_location="cpu", weights_only=True)
        restored = torch.load(resumed, map_location="cpu", weights_only=True)
        assert result["steps"] == 4 and result["optimizer_reinitialized"] is False
        assert all(torch.equal(value, restored["state_dict"][key])
                   for key, value in whole["state_dict"].items()), "Model weights diverged"
        assert whole["data_position"] == restored["data_position"]
        assert torch.equal(whole["torch_rng_state"], restored["torch_rng_state"])
        assert first.is_file()
        print({"exact_weights_match": True, "steps": 4, "source_preserved": True})


if __name__ == "__main__":
    main()
