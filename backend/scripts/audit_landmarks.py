import json
import os
import sys

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def audit_landmarks():
    catalog_path = "backend/data/processed/games_catalog.json"
    meta_path = "backend/data/processed/index_meta.json"
    
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        id_mapping_set = set(meta.get("id_mapping", []))
        
    landmarks = [
        "Stardew Valley",
        "Cyberpunk 2077",
        "Elden Ring",
        "Dark Souls",
        "Terraria",
        "Hollow Knight",
        "Hades",
        "RimWorld",
        "No Man's Sky",
        "Subnautica",
        "Valheim",
        "Deep Rock Galactic",
        "Risk of Rain 2",
        "Dead Cells",
        "Slay the Spire",
        "Factorio",
        "Rust",
        "Raft",
        "Don't Starve",
        "The Witcher 3"
    ]
    
    print("=" * 70)
    print("LANDMARK TITLES PRESENCE AUDIT IN CATALOG & 20K FAISS INDEX")
    print("=" * 70)
    
    for lm in landmarks:
        matches = [g for g in catalog if lm.lower() in g.get("title", "").lower()]
        if matches:
            best = matches[0]
            in_index = str(best["id"]) in id_mapping_set
            idx_pos = catalog.index(best)
            print(f"[FOUND] '{lm}' -> '{best['title']}' (ID: {best['id']}, Catalog Pos: #{idx_pos+1}, Reviews: {best['total_reviews']}, In 20k Index: {in_index})")
        else:
            print(f"[MISSING] '{lm}' -> NOT FOUND in catalog!")

if __name__ == "__main__":
    audit_landmarks()
