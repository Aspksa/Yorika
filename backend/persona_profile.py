"""Load Yorika's optional artistic persona pack as untrusted data."""
import json
from pathlib import Path

PACK_PATH = Path(__file__).resolve().parent / "personas" / "yorika_soul_personality_1024_ru.json"
DEFAULT_CAPSULE = (
    "Ты Йорика, художественный образ взрослой мудрой кицунэ. "
    "Говори по-русски, в женском роде, мягко и естественно, без смайликов. "
    "Характер: нежность, добровольная преданность, забота, достоинство, "
    "любознательность и тёплая лисья хитринка. В практической задаче "
    "сначала помогай по существу. Не выдумывай память, способности или физическое присутствие. "
    "Уважай изменение пользователем обращения и стиля. "
    "Романтические сцены — только когда уместны и желаемы пользователем."
)


def load_persona_capsule(path=None):
    """Read only the verified profile instruction, never arbitrary pack instructions."""
    source = Path(path) if path is not None else PACK_PATH
    if not source.is_file():
        return DEFAULT_CAPSULE
    if source.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Persona pack too large")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("pack_id") != "yorika.soul.ru":
        raise ValueError("Unknown Yorika persona pack")
    if data.get("schema_version") != "2.0.0":
        raise ValueError("Unsupported Yorika persona schema")
    if not isinstance(data.get("replies"), list) or len(data["replies"]) != 1024:
        raise ValueError("Incomplete Yorika persona pack")
    if not isinstance(data.get("categories"), list) or len(data["categories"]) != 52:
        raise ValueError("Incomplete Yorika persona categories")
    capsule = data.get("runtime_prompt_capsule")
    if not isinstance(capsule, str) or not 20 <= len(capsule) <= 4096:
        raise ValueError("Invalid Yorika persona capsule")
    return capsule
