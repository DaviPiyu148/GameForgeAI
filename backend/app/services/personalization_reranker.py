"""
GameForge Personalization V1 — Offline Personalization Re-Ranker
================================================================
Deterministic, bounded, additive re-ranking component for evaluating personalization offline.

Core Invariants:
- Additive Formula: personalized_score = base_score + (lambda_ * personalization_score).
- Bounded Score: personalization_score is strictly in [0.0, 1.0].
- Identity at Lambda = 0.0: Exactly matches baseline Discovery ordering (zero movement).
- Cold-Start Identity: Returns exactly baseline ordering when profile is absent or cold.
- Absolute Avoidance Safety: Candidates matching explicit avoidances receive 0.0 personalization.
- Suppressed Game Safety: Suppressed/disliked games receive 0.0 personalization.
- Fully Traceable: Emits PersonalizationTrace capturing components, before/after ranks, and delta.
- Production Invariant: OFFLINE ONLY — ranking integration is DISABLED in production.
"""

import copy
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.developer_profile import (
    EffectivePreferenceProfile,
    PersonalizationTrace,
)
from app.services.personalization_explanation_service import (
    PersonalizationExplanationService,
)


class PersonalizationReRanker:
    """
    Offline re-ranking engine applying conservative additive personalization boosts.
    """

    # Dimension weights for categorical preference matching
    W_GENRE: float = 0.35
    W_MECHANIC: float = 0.30
    W_THEME: float = 0.25
    W_MODE: float = 0.10

    # Hybrid blend between categorical features and semantic vector similarity
    W_CATEGORICAL: float = 0.70
    W_VECTOR: float = 0.30

    def compute_personalization_score(
        self,
        candidate: Any,
        effective_profile: Optional[EffectivePreferenceProfile],
        candidate_vector: Optional[List[float]] = None,
        saved_discovery_similarities: Optional[List[Tuple[str, float]]] = None,
        signal_mask: Optional[Set[str]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compute bounded deterministic personalization_score in [0.0, 1.0].
        
        signal_mask: Optional set of allowed signals for ablation studies:
                     {'genre', 'mechanic', 'theme', 'mode', 'project', 'saved_game'}
        """
        trace_meta: Dict[str, Any] = {
            "sources": [],
            "dimensions": [],
            "matched_features": {},
            "raw_categorical": 0.0,
            "vector_similarity": 0.0,
        }

        if effective_profile is None:
            return 0.0, trace_meta

        # Check for cold profile (zero affinities across all dimensions and no vector)
        has_affinities = bool(
            effective_profile.genres
            or effective_profile.mechanics
            or effective_profile.themes
            or effective_profile.modes
        )
        has_vector = effective_profile.preference_vector is not None
        # Only short-circuit when there is truly nothing to evaluate.
        # If saved_discovery_similarities are provided they must still be scored
        # even for a cold categorical profile.
        if not has_affinities and not has_vector and not saved_discovery_similarities:
            return 0.0, trace_meta

        # Extract normalized candidate features
        c_id, c_title, c_genres, c_mechanics, c_themes, c_modes = (
            PersonalizationExplanationService._extract_candidate_features(candidate)
        )

        # 1. Suppressed Game Guard: Never personalize suppressed games
        if c_id and c_id in effective_profile.suppressed_game_ids:
            return 0.0, trace_meta

        # 2. Explicit Avoidance Guard: Never personalize games matching avoided categories
        avoid_set = {a.lower() for a in effective_profile.explicit_avoidances}
        if any(g.lower() in avoid_set for g in c_genres):
            return 0.0, trace_meta
        if any(m.lower() in avoid_set for m in c_mechanics):
            return 0.0, trace_meta
        if any(t.lower() in avoid_set for t in c_themes):
            return 0.0, trace_meta
        if any(md.lower() in avoid_set for md in c_modes):
            return 0.0, trace_meta

        # 3. Categorical Affinity Matching
        score_genre = 0.0
        best_genre = None
        if not signal_mask or "genre" in signal_mask:
            for g in c_genres:
                s = effective_profile.genres.get(g, 0.0)
                if s > score_genre:
                    score_genre = s
                    best_genre = g

        score_mech = 0.0
        best_mech = None
        if not signal_mask or "mechanic" in signal_mask:
            for m in c_mechanics:
                s = effective_profile.mechanics.get(m, 0.0)
                if s > score_mech:
                    score_mech = s
                    best_mech = m

        score_theme = 0.0
        best_theme = None
        if not signal_mask or "theme" in signal_mask:
            for t in c_themes:
                s = effective_profile.themes.get(t, 0.0)
                if s > score_theme:
                    score_theme = s
                    best_theme = t

        score_mode = 0.0
        best_mode = None
        if not signal_mask or "mode" in signal_mask:
            for md in c_modes:
                s = effective_profile.modes.get(md, 0.0)
                if s > score_mode:
                    score_mode = s
                    best_mode = md

        # Record matched features for explainability
        if best_genre and score_genre > 0.0:
            trace_meta["dimensions"].append("genre")
            trace_meta["matched_features"][f"genre:{best_genre}"] = round(score_genre, 4)
        if best_mech and score_mech > 0.0:
            trace_meta["dimensions"].append("mechanic")
            trace_meta["matched_features"][f"mechanic:{best_mech}"] = round(score_mech, 4)
        if best_theme and score_theme > 0.0:
            trace_meta["dimensions"].append("theme")
            trace_meta["matched_features"][f"theme:{best_theme}"] = round(score_theme, 4)
        if best_mode and score_mode > 0.0:
            trace_meta["dimensions"].append("mode")
            trace_meta["matched_features"][f"mode:{best_mode}"] = round(score_mode, 4)

        cat_score = (
            (self.W_GENRE * score_genre)
            + (self.W_MECHANIC * score_mech)
            + (self.W_THEME * score_theme)
            + (self.W_MODE * score_mode)
        )
        trace_meta["raw_categorical"] = round(cat_score, 4)

        # 4. Semantic Vector Similarity (Cosine Similarity between candidate & preference vector)
        vec_sim = 0.0
        if (
            (not signal_mask or "vector" in signal_mask)
            and candidate_vector is not None
            and effective_profile.preference_vector is not None
        ):
            # Both vectors are expected to be L2-normalized 384-dimensional arrays
            if len(candidate_vector) == len(effective_profile.preference_vector):
                dot = sum(a * b for a, b in zip(candidate_vector, effective_profile.preference_vector))
                vec_sim = max(0.0, min(1.0, dot))
                trace_meta["vector_similarity"] = round(vec_sim, 4)

        # 5. Saved Discovery Similarity (if candidate is similar to a saved game)
        saved_score = 0.0
        if (not signal_mask or "saved_game" in signal_mask) and saved_discovery_similarities:
            for s_title, s_sim in saved_discovery_similarities:
                if s_sim >= 0.75 and s_sim > saved_score:
                    saved_score = s_sim
                    trace_meta["matched_features"][f"saved:{s_title}"] = round(s_sim, 4)
                    trace_meta["dimensions"].append("saved_game")

        # Combine signals into bounded personalization score
        if vec_sim > 0.0:
            final_p_score = (self.W_CATEGORICAL * cat_score) + (self.W_VECTOR * vec_sim)
        else:
            final_p_score = cat_score

        if saved_score > 0.0:
            # Saved-game similarity can provide an anchor boost up to 0.85
            final_p_score = max(final_p_score, saved_score * 0.85)

        # Determine active sources for provenance
        if effective_profile.active_project_id:
            trace_meta["sources"].append("PROJECT")
        if cat_score > 0.0:
            trace_meta["sources"].append("GLOBAL")
        if saved_score > 0.0:
            trace_meta["sources"].append("SAVED_DISCOVERY")
        trace_meta["sources"] = list(set(trace_meta["sources"]))

        final_bounded = round(max(0.0, min(1.0, final_p_score)), 4)
        return final_bounded, trace_meta

    def rerank(
        self,
        results: List[Any],
        effective_profile: Optional[EffectivePreferenceProfile],
        lambda_: float = 0.0,
        candidate_vectors: Optional[Dict[str, List[float]]] = None,
        saved_discovery_similarities: Optional[Dict[str, List[Tuple[str, float]]]] = None,
        signal_mask: Optional[Set[str]] = None,
    ) -> Tuple[List[Any], List[PersonalizationTrace]]:
        """
        Re-rank candidate search results using additive personalization:
        personalized_score = base_score + (lambda_ * personalization_score)

        Returns:
            (re_ranked_results, traces)
        """
        if not results:
            return [], []

        traces: List[PersonalizationTrace] = []
        scored_items: List[Dict[str, Any]] = []

        for idx, item in enumerate(results):
            # Extract base score and candidate identity
            if hasattr(item, "score"):
                base_score = float(item.score)
                cand_id = getattr(getattr(item, "game", None), "id", "") or str(idx)
                cand_title = getattr(getattr(item, "game", None), "title", "") or "Unknown"
            elif isinstance(item, dict):
                base_score = float(item.get("score", 0.0))
                cand_id = str(item.get("id") or item.get("game_id") or idx)
                cand_title = str(item.get("title") or "Unknown")
            else:
                base_score = 0.0
                cand_id = str(idx)
                cand_title = "Unknown"

            c_vec = candidate_vectors.get(cand_id) if candidate_vectors else None
            s_sims = (
                saved_discovery_similarities.get(cand_id)
                if saved_discovery_similarities
                else None
            )

            p_score, p_meta = self.compute_personalization_score(
                candidate=item,
                effective_profile=effective_profile,
                candidate_vector=c_vec,
                saved_discovery_similarities=s_sims,
                signal_mask=signal_mask,
            )

            # Additive re-ranking formula
            final_score = base_score + (lambda_ * p_score)
            final_score = round(final_score, 6)

            scored_items.append({
                "item": item,
                "base_rank": idx + 1,
                "base_score": base_score,
                "p_score": p_score,
                "final_score": final_score,
                "cand_id": cand_id,
                "cand_title": cand_title,
                "meta": p_meta,
            })

        # Deterministic sorting:
        # 1. Final score descending (-final_score)
        # 2. Tie-breaker: Original base rank ascending (preserves exact base order on ties)
        def sort_key(x: Dict[str, Any]):
            return (-x["final_score"], x["base_rank"])

        sorted_items = sorted(scored_items, key=sort_key)

        reranked_results: List[Any] = []
        for new_rank, it in enumerate(sorted_items, start=1):
            reranked_results.append(it["item"])
            trace = PersonalizationTrace(
                candidate_id=it["cand_id"],
                candidate_title=it["cand_title"],
                base_discovery_score=round(it["base_score"], 4),
                personalization_score=it["p_score"],
                personalization_sources=it["meta"]["sources"],
                personalization_dimensions=it["meta"]["dimensions"],
                effective_profile_confidence=1.0,
                lambda_=lambda_,
                personalized_final_score=round(it["final_score"], 4),
                base_rank=it["base_rank"],
                personalized_rank=new_rank,
                rank_delta=it["base_rank"] - new_rank,
                matched_features=it["meta"]["matched_features"],
            )
            traces.append(trace)

        return reranked_results, traces


personalization_reranker = PersonalizationReRanker()
