import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_catalog.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "language_audit_report.json")

def detect_script_or_lang(text: str) -> str:
    if not text or not str(text).strip() or text.strip() in ("\\N", "nan", "None"):
        return "MISSING"
    
    s = str(text).strip()
    
    # Count character types
    cyrillic = len(re.findall(r'[\u0400-\u04FF]', s))
    cjk_unified = len(re.findall(r'[\u4E00-\u9FFF]', s))
    hiragana_katakana = len(re.findall(r'[\u3040-\u30FF]', s))
    hangul = len(re.findall(r'[\uAC00-\uD7AF\u1100-\u11FF]', s))
    latin = len(re.findall(r'[a-zA-Z]', s))
    
    total_alpha = cyrillic + cjk_unified + hiragana_katakana + hangul + latin
    if total_alpha == 0:
        return "PUNCT_NUM"
    
    if cyrillic / total_alpha > 0.25:
        return "RUSSIAN_CYRILLIC"
    if hangul / total_alpha > 0.20:
        return "KOREAN"
    if hiragana_katakana / total_alpha > 0.15:
        return "JAPANESE"
    if cjk_unified / total_alpha > 0.20:
        return "CHINESE"
    if latin / total_alpha > 0.60:
        return "ENGLISH_LATIN"
    
    return "MIXED_OTHER"

def main():
    if not os.path.exists(CATALOG_PATH):
        print(f"Error: {CATALOG_PATH} not found.")
        sys.exit(1)
        
    print(f"Loading {CATALOG_PATH}...")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    total_records = len(catalog)
    print(f"Total records: {total_records}")
    
    fields = ["title", "description", "genres", "tags", "player_modes", "platforms"]
    field_stats: Dict[str, Counter] = {field: Counter() for field in fields}
    
    raw_genres_counter = Counter()
    raw_tags_counter = Counter()
    
    # List of landmark games to specifically audit
    landmark_app_ids = {
        "413150": "Stardew Valley",
        "1091500": "Cyberpunk 2077",
        "1245620": "ELDEN RING",
        "374320": "DARK SOULS III",
        "105600": "Terraria",
        "367520": "Hollow Knight",
        "1145360": "Hades",
        "294100": "RimWorld",
        "427520": "Factorio",
        "264710": "Subnautica"
    }
    landmark_audits = {}

    for game in catalog:
        gid = str(game.get("external_id") or game.get("id"))
        if gid in landmark_app_ids:
            landmark_audits[landmark_app_ids[gid]] = {
                "id": gid,
                "title": game.get("title"),
                "genres": game.get("genres"),
                "tags": game.get("tags")[:5],
                "description_sample": game.get("description", "")[:100],
                "desc_lang": detect_script_or_lang(game.get("description", "")),
                "genre_lang": [detect_script_or_lang(g) for g in game.get("genres", [])]
            }

        # Title
        t_lang = detect_script_or_lang(game.get("title", ""))
        field_stats["title"][t_lang] += 1
        
        # Description
        d_lang = detect_script_or_lang(game.get("description", ""))
        field_stats["description"][d_lang] += 1
        
        # Genres
        genres = game.get("genres", [])
        if not genres:
            field_stats["genres"]["MISSING"] += 1
        else:
            g_str = " ".join(genres)
            g_lang = detect_script_or_lang(g_str)
            field_stats["genres"][g_lang] += 1
            for g in genres:
                raw_genres_counter[g] += 1
                
        # Tags
        tags = game.get("tags", [])
        if not tags:
            field_stats["tags"]["MISSING"] += 1
        else:
            t_str = " ".join(tags)
            tag_lang = detect_script_or_lang(t_str)
            field_stats["tags"][tag_lang] += 1
            for t in tags:
                raw_tags_counter[t] += 1
                
        # Player modes
        modes = game.get("player_modes", [])
        if not modes:
            field_stats["player_modes"]["MISSING"] += 1
        else:
            m_lang = detect_script_or_lang(" ".join(modes))
            field_stats["player_modes"][m_lang] += 1

    report = {
        "total_records": total_records,
        "fields": {},
        "non_latin_genres": [],
        "non_latin_tags_top50": [],
        "landmark_audits": landmark_audits
    }

    print("\n" + "="*80)
    print("FIELD-LEVEL LANGUAGE & SCRIPT DISTRIBUTION REPORT")
    print("="*80)
    
    for field in fields:
        print(f"\n--- Field: {field} ---")
        counter = field_stats[field]
        field_results = {}
        for k, count in counter.most_common():
            pct = (count / total_records) * 100
            print(f"  {k:20s}: {count:6d} ({pct:5.2f}%)")
            field_results[k] = {"count": count, "pct": round(pct, 2)}
        report["fields"][field] = field_results

    for g, count in raw_genres_counter.most_common():
        if detect_script_or_lang(g) != "ENGLISH_LATIN":
            report["non_latin_genres"].append({"genre": g, "count": count, "script": detect_script_or_lang(g)})
            
    for t, count in raw_tags_counter.most_common():
        if detect_script_or_lang(t) != "ENGLISH_LATIN":
            report["non_latin_tags_top50"].append({"tag": t, "count": count, "script": detect_script_or_lang(t)})
            if len(report["non_latin_tags_top50"]) >= 50:
                break

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"\nAudit report written to {REPORT_PATH}")
    print(f"Total non-Latin genres found: {len(report['non_latin_genres'])}")
    print(f"Total non-Latin tags found: {len(report['non_latin_tags_top50'])}")

if __name__ == "__main__":
    main()
