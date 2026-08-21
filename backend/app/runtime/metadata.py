import hashlib
from typing import Any, Dict, Optional


RENDERER_VERSION = "1.0.0"
PHASER_VERSION = "3.88.2"
DSL_SCHEMA_VERSION = "1.0"


def generate_seed_from_input(seed_source: str) -> int:
    """Generate a deterministic 32-bit positive integer seed from a string identifier."""
    h = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def generate_runtime_metadata(
    seed_source: str,
    custom_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate deterministic runtime metadata for prototype reproducibility.
    
    This records the exact engine, renderer, and schema versions alongside
    a deterministic seed to guarantee identical prototype execution.
    """
    seed = custom_seed if custom_seed is not None else generate_seed_from_input(seed_source)
    return {
        "rendererVersion": RENDERER_VERSION,
        "phaserVersion": PHASER_VERSION,
        "dslSchemaVersion": DSL_SCHEMA_VERSION,
        "seed": seed,
    }
