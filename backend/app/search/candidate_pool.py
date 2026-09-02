from enum import Enum
from typing import Dict, Set,Optional


class DiscoveryCandidatePool(str, Enum):
    """Supported candidate populations for Discovery retrieval."""
    POPULAR_20K = "20k"
    REVIEWED_ONLY = "reviewed_only"
    FULL_CATALOG = "full"


# Mode -> Candidate Pool Policy
# BEST_MATCH / POPULAR: 20k acclaimed head for precision search
# DISCOVER: 20k acclaimed head (retaining high-signal universe pending dedicated validation)
# HIDDEN_GEMS: 87,890 reviewed-only long tail for discovery with 0% unreviewed noise
MODE_CANDIDATE_POOLS: Dict[str, DiscoveryCandidatePool] = {
    "BEST_MATCH": DiscoveryCandidatePool.POPULAR_20K,
    "POPULAR": DiscoveryCandidatePool.POPULAR_20K,
    "DISCOVER": DiscoveryCandidatePool.POPULAR_20K,
    "HIDDEN_GEMS": DiscoveryCandidatePool.REVIEWED_ONLY,
}


DESIGNATED_POOL_SIZES: Dict[DiscoveryCandidatePool, int] = {
    DiscoveryCandidatePool.POPULAR_20K: 20000,
    DiscoveryCandidatePool.REVIEWED_ONLY: 87890,
    DiscoveryCandidatePool.FULL_CATALOG: 121625,
}


def get_candidate_pool_for_mode(mode: Optional[str]) -> DiscoveryCandidatePool:
    """Retrieve the designated candidate population policy for a given DiscoveryMode.primary"""
    clean_mode = (mode or "").strip().upper()
    return MODE_CANDIDATE_POOLS.get(clean_mode, DiscoveryCandidatePool.POPULAR_20K)
