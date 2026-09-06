import json
from pathlib import Path

catalog_path = Path("backend/data/processed/games_catalog.json")
with open(catalog_path, "r", encoding="utf-8") as f:
    catalog = json.load(f)

meta_20k_path = Path("backend/data/processed/index_meta.json")
with open(meta_20k_path, "r", encoding="utf-8") as f:
    meta_20k = json.load(f)

meta_rev_path = Path("backend/data/benchmark_indexes/index_meta_reviewed_only.json")
with open(meta_rev_path, "r", encoding="utf-8") as f:
    meta_rev = json.load(f)

print(f"Total catalog games: {len(catalog)}")
print(f"Meta 20k id_mapping length: {len(meta_20k.get('id_mapping', []))}")
print(f"Meta Reviewed id_mapping length: {len(meta_rev.get('id_mapping', []))}")

map20 = set(str(x) for x in meta_20k.get("id_mapping", []))
maprev = set(str(x) for x in meta_rev.get("id_mapping", []))

for target in [
    "Shapebreaker",
    "Colony Ship",
    "Cyberpunk 2077",
    "Slay the Spire",
    "Space Haven",
    "Sven Co-op",
    "Neurodeck",
    "Mahokenshi",
    "Cobalt Core",
]:
    matches = [
        (idx, g)
        for idx, g in enumerate(catalog)
        if target.lower() in g.get("title", "").lower()
    ]
    print(f"\nTarget: {target}")
    for idx, g in matches[:3]:
        gid = str(g.get("id"))
        in_20k = gid in map20
        in_rev = gid in maprev
        pos_20k = meta_20k.get("id_mapping", []).index(gid) if in_20k else -1
        pos_rev = meta_rev.get("id_mapping", []).index(gid) if in_rev else -1
        print(
            f"  Catalog pos: {idx:<6} | ID: {gid:<8} | Title: {g.get('title'):<45} | Reviews: {g.get('total_reviews', 0):<8} | In 20k Index: {str(in_20k):<5} (pos {pos_20k:<5}) | In Rev Index: {str(in_rev):<5} (pos {pos_rev:<5})"
        )
