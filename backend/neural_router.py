"""Opt-in experimental model adapter. Never overrides production chat by default."""
from pathlib import Path
from backend.neural_inference import generate


def experimental_answer(query, *, checkpoint=None, enabled=False, max_tokens=64,
                        generator=generate):
    if enabled is not True:
        raise PermissionError("Experimental neural engine requires explicit opt-in")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Invalid query")
    if checkpoint is None or not isinstance(checkpoint, (str, Path)):
        raise ValueError("Trusted local checkpoint must be supplied")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 128:
        raise ValueError("Invalid generation bound")
    result = generator(checkpoint, query, max_tokens=max_tokens)
    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise RuntimeError("Invalid experimental response")
    return {"answer": result["answer"], "provider": "experimental-local-transformer",
            "experimental": True, "checkpoint": Path(checkpoint).name,
            "quality_verified": False}


def route_answer(query, *, experimental=False, checkpoint=None, fallback=None,
                 generator=generate):
    """Use experiment on explicit request; recover via existing provider on failures."""
    if not callable(fallback):
        raise ValueError("An explicit fallback responder is required")
    if experimental is not True:
        return fallback(query)
    try:
        return experimental_answer(query, checkpoint=checkpoint, enabled=True,
                                   generator=generator)
    except (RuntimeError, ValueError, OSError):
        return fallback(query)
