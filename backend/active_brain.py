"""Single active Yorika brain: an explicit immutable pointer, never auto-promoted."""
import json
from pathlib import Path


def select_brain(directory, checkpoint):
    root = Path(directory).resolve()
    candidate = Path(checkpoint).resolve()
    if not candidate.is_file() or candidate.suffix != ".pt" or candidate.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Trusted local .pt checkpoint required")
    if candidate == root or root not in candidate.parents:
        raise ValueError("Checkpoint must live inside private model directory")
    pointer = root / "active-brain.json"
    if pointer.exists():
        raise FileExistsError("Brain already selected; explicit offline replacement required")
    with pointer.open("x", encoding="utf-8") as output:
        json.dump({"schema": 1, "checkpoint": str(candidate.relative_to(root)),
                   "engine": "yorika-own-transformer", "automatic": False}, output)
    return pointer


def active_brain(directory):
    root = Path(directory).resolve()
    pointer = root / "active-brain.json"
    if not pointer.is_file() or pointer.stat().st_size > 4096:
        raise RuntimeError("Yorika brain is not selected")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema", "checkpoint", "engine", "automatic"}:
        raise ValueError("Invalid active brain manifest")
    if data["schema"] != 1 or data["engine"] != "yorika-own-transformer" or data["automatic"] is not False:
        raise ValueError("Invalid active brain mode")
    relative = Path(data["checkpoint"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe checkpoint path")
    checkpoint = (root / relative).resolve()
    if root not in checkpoint.parents or not checkpoint.is_file() or checkpoint.suffix != ".pt":
        raise ValueError("Missing or unsafe active checkpoint")
    return checkpoint
