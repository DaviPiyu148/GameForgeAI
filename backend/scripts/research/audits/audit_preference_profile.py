"""
GameForge Personalization V1 — Developer Preference Profile Audit Script
========================================================================
Development diagnostic tool to inspect the deterministic aggregation profile,
active project context, and blended effective profile for a given user.

Usage:
    python backend/scripts/audit_preference_profile.py --user <user_id_or_username>
    python backend/scripts/audit_preference_profile.py --user <id> --project <project_id>
    python backend/scripts/audit_preference_profile.py --all
"""

import argparse
import os
import sys

# Ensure backend root is on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db.session import SessionLocal
from app.models.project import Project
from app.models.user import User
from app.services.context_blender import context_blender
from app.services.preference_aggregator import preference_aggregator


def print_dimension_bars(title: str, items_dict: dict, max_items: int = 6):
    print(f"\n--- {title} ---")
    if items_dict:
        for k, conf in list(items_dict.items())[:max_items]:
            bar = "#" * int(conf * 20)
            print(f"  {k:<22} {conf:>6.4f}  {bar}")
    else:
        print("  (None)")


def audit_user_profile(db, user: User, project_id: str = None) -> None:
    """Run aggregation and print comprehensive diagnostic report."""
    print(f"\n{'='*70}")
    print(f"PROFILE AUDIT: {user.username} (ID: {user.id})")
    print(f"{'='*70}")

    # 1. Global Profile
    global_profile = preference_aggregator.build_profile(db=db, user_id=user.id)

    print(f"\n[1. GLOBAL DEVELOPER PROFILE]")
    print(f"Maturity Tier:       {global_profile.confidence_tier}")
    print(f"Total Signal Count:  {global_profile.total_signal_count}")
    print(f"Recent Focus Genre:  {global_profile.recent_focus_genre or 'None'}")
    print(f"Last Updated:        {global_profile.last_updated.isoformat()}")

    if global_profile.preference_vector is not None:
        dim = len(global_profile.preference_vector)
        norm_val = sum(x**2 for x in global_profile.preference_vector) ** 0.5
        print(f"Preference Vector:   AVAILABLE ({dim} dims, L2 norm = {norm_val:.4f})")
    else:
        print(f"Preference Vector:   NONE")

    print(f"Explicit Avoids:     {global_profile.explicit_avoidances if global_profile.explicit_avoidances else 'None'}")
    print(f"Suppressed Game IDs: {len(global_profile.suppressed_game_ids)}")

    print_dimension_bars("GLOBAL TOP GENRES", global_profile.genres)
    print_dimension_bars("GLOBAL TOP MECHANICS", global_profile.mechanics)
    print_dimension_bars("GLOBAL TOP THEMES", global_profile.themes)
    print_dimension_bars("GLOBAL PLAYER MODES", global_profile.modes)

    # 2. Project Profile (if requested)
    project_profile = None
    if project_id:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if not proj:
            print(f"\nProject '{project_id}' not found in database.")
            return

        project_profile = context_blender.build_project_profile(proj)

        print(f"\n[2. ACTIVE PROJECT PROFILE: '{proj.title}' (ID: {proj.id})]")
        print(f"Context Confidence:  {project_profile.context_confidence:.2f}")
        print(f"Project Genre:       {proj.genre or 'None'}")
        if project_profile.preference_vector is not None:
            dim = len(project_profile.preference_vector)
            norm_val = sum(x**2 for x in project_profile.preference_vector) ** 0.5
            print(f"Project Vector:      AVAILABLE ({dim} dims, L2 norm = {norm_val:.4f})")
        else:
            print(f"Project Vector:      NONE")

        print_dimension_bars("PROJECT GENRES", project_profile.genres)
        print_dimension_bars("PROJECT MECHANICS", project_profile.mechanics)
        print_dimension_bars("PROJECT THEMES", project_profile.themes)
        print_dimension_bars("PROJECT MODES", project_profile.modes)

    # 3. Blended Effective Profile
    effective = context_blender.blend(
        global_profile=global_profile,
        project_profile=project_profile,
    )

    print(f"\n[3. BLENDED EFFECTIVE PROFILE]")
    print(f"Active Project:      {effective.active_project_title or 'None (Global Only)'}")
    print(f"Blend Weights:       Global: {effective.blend_weights.get('global', 1.0):.2f}, Project: {effective.blend_weights.get('project', 0.0):.2f}")
    print(f"Recent Focus Genre:  {effective.recent_focus_genre or 'None'}")
    if effective.preference_vector is not None:
        dim = len(effective.preference_vector)
        norm_val = sum(x**2 for x in effective.preference_vector) ** 0.5
        print(f"Effective Vector:    AVAILABLE ({dim} dims, L2 norm = {norm_val:.4f})")
    else:
        print(f"Effective Vector:    NONE")

    print(f"Explicit Avoids:     {effective.explicit_avoidances if effective.explicit_avoidances else 'None'}")
    if effective.conflicts:
        print(f"Conflict Alerts ({len(effective.conflicts)}):")
        for c in effective.conflicts:
            print(f"  ! {c}")

    print_dimension_bars("EFFECTIVE TOP GENRES", effective.genres)
    print_dimension_bars("EFFECTIVE TOP MECHANICS", effective.mechanics)
    print_dimension_bars("EFFECTIVE TOP THEMES", effective.themes)
    print_dimension_bars("EFFECTIVE PLAYER MODES", effective.modes)

    # Provenance Breakdown
    print(f"\n--- PROVENANCE & SOURCE ATTRIBUTION ({len(effective.evidence)} items) ---")
    source_counts = {}
    dimension_counts = {}
    for ev in effective.evidence:
        source_counts[ev.source] = source_counts.get(ev.source, 0) + 1
        dimension_counts[ev.dimension] = dimension_counts.get(ev.dimension, 0) + 1

    print("By Source:")
    for src, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {src:<20}: {count} signals")

    print("By Dimension:")
    for dim, count in sorted(dimension_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {dim:<20}: {count} signals")

        print(f"\nSample Blended Contribution Details (up to 6):")
        for it in effective.blended_details[:6]:
            print(f"  * {it.dimension:<10} '{it.value}': global={it.global_score:.2f}, project={it.project_score:.2f} => effective={it.effective_score:.4f}")

    # 4. Grounded Personalization Explanations on Sample Catalog Candidates
    print(f"\n[4. SAMPLE CANDIDATE EXPLANATIONS (PHASE 4)]")
    from app.services.personalization_explanation_service import personalization_explanation_service
    from app.search.catalog import CatalogManager

    catalog_mgr = CatalogManager.get_instance()
    # Pick a diverse set of catalog candidates to audit grounded explanations
    sample_candidates = []
    # Sample catalog game IDs: Slay the Spire (646570), Cyberpunk/Action game, Stardew Valley (413150)
    for gid in ["646570", "413150", "984110", "28af5927-5595-41be-9233-b60c59a9415a"]:
        g = catalog_mgr.get_game(gid)
        if g:
            sample_candidates.append(g)

    if not sample_candidates:
        # Fallback to first 3 catalog games
        sample_candidates = catalog_mgr.get_all_games()[:3]

    for cand in sample_candidates:
        reasons = personalization_explanation_service.explain(
            candidate=cand,
            global_profile=global_profile,
            project_profile=project_profile,
            effective_profile=effective,
        )
        c_title = cand.get("title") if isinstance(cand, dict) else getattr(cand, "title", "Unknown")
        print(f"\nCandidate: {c_title}")
        if reasons:
            for r in reasons:
                print(f"  * Reason:     \"{r.text}\"")
                print(f"    Source:     {r.source}")
                print(f"    Dimension:  {r.dimension}")
                print(f"    Evidence:   {r.value}")
                print(f"    Confidence: {r.confidence:.4f}")
        else:
            print("  * (No personalization reason generated - insufficient evidence)")


def main():
    parser = argparse.ArgumentParser(description="Audit developer preference profiles.")
    parser.add_argument("--user", help="User ID or Username to audit.")
    parser.add_argument("--project", help="Optional active Project ID to audit blended context.")
    parser.add_argument("--all", action="store_true", help="Audit all registered users.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.all:
            users = db.query(User).all()
            if not users:
                print("No users found in database.")
                return
            for u in users:
                audit_user_profile(db, u, project_id=args.project)
        elif args.user:
            user = (
                db.query(User)
                .filter((User.id == args.user) | (User.username == args.user))
                .first()
            )
            if not user:
                print(f"User '{args.user}' not found in database.")
                sys.exit(1)
            audit_user_profile(db, user, project_id=args.project)
        else:
            print("Please specify --user <id_or_username> or --all.")
            parser.print_help()
    finally:
        db.close()


if __name__ == "__main__":
    main()
