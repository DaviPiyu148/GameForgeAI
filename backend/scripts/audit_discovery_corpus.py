import csv
import json
import os
import sys

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def audit():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(script_dir)
    raw_dir = os.path.join(backend_dir, "data", "raw")
    processed_dir = os.path.join(backend_dir, "data", "processed")
    
    print("=" * 60)
    print("DISCOVERY CORPUS & LANDMARK AUDIT")
    print("=" * 60)
    
    # 1. Raw games.csv check
    games_csv = os.path.join(raw_dir, "games.csv")
    raw_stardew = None
    raw_cyberpunk = None
    raw_count = 0
    if os.path.exists(games_csv):
        with open(games_csv, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                raw_count += 1
                if not row or len(row) < 2:
                    continue
                app_id = row[0].strip()
                title = row[1].strip()
                if "stardew" in title.lower():
                    raw_stardew = (app_id, title)
                if "cyberpunk" in title.lower() and "2077" in title.lower():
                    raw_cyberpunk = (app_id, title)
    
    print(f"A1. Raw games scanned: {raw_count}")
    print(f"A2. Raw Stardew Valley: {raw_stardew}")
    print(f"B1. Raw Cyberpunk 2077: {raw_cyberpunk}")
    
    # 2. Normalized catalog check
    catalog_path = os.path.join(processed_dir, "games_catalog.json")
    catalog_stardew = None
    catalog_cyberpunk = None
    stardew_rank = None
    cyberpunk_rank = None
    
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
            print(f"C. Normalized catalog count: {len(catalog)}")
            for idx, g in enumerate(catalog):
                t = g.get("title", "").lower()
                if "stardew" in t:
                    if catalog_stardew is None:
                        catalog_stardew = g
                        stardew_rank = idx
                if "cyberpunk 2077" in t:
                    if catalog_cyberpunk is None:
                        catalog_cyberpunk = g
                        cyberpunk_rank = idx

    print(f"A3. Catalog Stardew Valley: rank={stardew_rank}, id={catalog_stardew.get('id') if catalog_stardew else None}, title={catalog_stardew.get('title') if catalog_stardew else None}, reviews={catalog_stardew.get('total_reviews') if catalog_stardew else None}")
    if catalog_stardew:
        print(f"  Stardew Genres: {catalog_stardew.get('genres')}")
        print(f"  Stardew Tags: {catalog_stardew.get('tags')[:8]}")
        print(f"  Stardew Semantic Profile: {catalog_stardew.get('semantic_profile')[:150]}...")
        
    print(f"B2. Catalog Cyberpunk 2077: rank={cyberpunk_rank}, id={catalog_cyberpunk.get('id') if catalog_cyberpunk else None}, title={catalog_cyberpunk.get('title') if catalog_cyberpunk else None}, reviews={catalog_cyberpunk.get('total_reviews') if catalog_cyberpunk else None}")
    if catalog_cyberpunk:
        print(f"  Cyberpunk Genres: {catalog_cyberpunk.get('genres')}")
        print(f"  Cyberpunk Tags: {catalog_cyberpunk.get('tags')[:8]}")
        print(f"  Cyberpunk Semantic Profile: {catalog_cyberpunk.get('semantic_profile')[:150]}...")

    # 3. Index metadata check
    meta_path = os.path.join(processed_dir, "index_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            id_mapping = meta.get("id_mapping", [])
            print(f"D. Index record count: {meta.get('record_count')}, id_mapping length: {len(id_mapping)}")
            stardew_in_index = str(catalog_stardew.get("id")) in id_mapping if catalog_stardew else False
            cyberpunk_in_index = str(catalog_cyberpunk.get("id")) in id_mapping if catalog_cyberpunk else False
            print(f"A4. Stardew in FAISS ID mapping: {stardew_in_index} (index position: {id_mapping.index(str(catalog_stardew.get('id'))) if stardew_in_index else 'N/A'})")
            print(f"B3. Cyberpunk in FAISS ID mapping: {cyberpunk_in_index} (index position: {id_mapping.index(str(catalog_cyberpunk.get('id'))) if cyberpunk_in_index else 'N/A'})")

if __name__ == "__main__":
    audit()
