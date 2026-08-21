import os
import sys
import time
import json
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.search.lexical import LexicalIndex, normalize_string, tokenize
from app.search.query_parser import QueryParser
from app.search.ranker import Ranker, ParsedQuery

# Multilingual Genre Dictionary mapping Russian, Chinese, Japanese, Spanish, Ukrainian to English canonicals
EXPANDED_GENRE_MAP = {
    # Russian / Ukrainian
    "инди": "Indie",
    "ролевые игры": "RPG",
    "симуляторы": "Simulation",
    "бесплатные": "Free to Play",
    "бесплатно": "Free to Play",
    "экшены": "Action",
    "приключенческие игры": "Adventure",
    "стратегии": "Strategy",
    "казуальные игры": "Casual",
    "гонки": "Racing",
    "спортивные игры": "Sports",
    "ммо": "Massively Multiplayer",
    "многопользовательские игры": "Massively Multiplayer",
    "ранний доступ": "Early Access",
    "насилие": "Violent",
    "мясо": "Gore",
    "пригоди": "Adventure",
    "бойовики": "Action",
    "казуальні ігри": "Casual",
    "інді": "Indie",
    
    # Chinese (Simplified & Traditional)
    "角色扮演": "RPG",
    "独立": "Indie",
    "獨立": "Indie",
    "獨立製作": "Indie",
    "动作": "Action",
    "動作": "Action",
    "冒险": "Adventure",
    "冒險": "Adventure",
    "模拟": "Simulation",
    "模擬": "Simulation",
    "策略": "Strategy",
    "休闲": "Casual",
    "休閒": "Casual",
    "免费开玩": "Free to Play",
    "抢先体验": "Early Access",
    "搶先體驗": "Early Access",
    "体育": "Sports",
    "競速": "Racing",
    "大型多人連線": "Massively Multiplayer",
    
    # Japanese
    "アドベンチャー": "Adventure",
    "インディー": "Indie",
    "アクション": "Action",
    "カジュアル": "Casual",
    "ストラテジー": "Strategy",
    "無料プレイ": "Free to Play",
    "シミュレーション": "Simulation",
    "ロールプレイング": "RPG",
    "レース": "Racing",
    "スポーツ": "Sports",
    
    # Spanish / French / German
    "acción": "Action",
    "rol": "RPG",
    "aventura": "Adventure",
    "simuladores": "Simulation",
    "estrategia": "Strategy",
    "carreras": "Racing",
    "deportes": "Sports",
    "multijugador masivo": "Massively Multiplayer",
    "acceso anticipado": "Early Access",
    "gratuit": "Free to Play",
    "kostenlos": "Free to Play",
}

# Multilingual Query Token Dictionary (Russian / foreign query words -> English search equivalents)
MULTILINGUAL_QUERY_DICTIONARY = {
    # Russian concepts
    "ферма": "farm farming",
    "фермы": "farm farming",
    "фермерство": "farm farming",
    "уютный": "cozy relaxing",
    "уютная": "cozy relaxing",
    "уютное": "cozy relaxing",
    "песочница": "sandbox",
    "песочницы": "sandbox",
    "крафтинг": "crafting",
    "крафт": "crafting",
    "выживание": "survival",
    "выживалка": "survival",
    "рогалик": "roguelike",
    "рогалики": "roguelike",
    "открытый": "open world",
    "открытом": "open world",
    "мир": "world",
    "мире": "world",
    "кооператив": "co-op",
    "кооперативный": "co-op",
    "кооперативная": "co-op",
    "метроидвания": "metroidvania",
    "жуки": "insects bugs",
    "жуках": "insects bugs",
    "фабрика": "automation factory",
    "завод": "automation factory",
    "строительство": "building",
    "строить": "building",
    "космос": "space",
    "космический": "space",
    "космическая": "space",
    "подводный": "underwater ocean",
    "океан": "underwater ocean",
    "приключение": "adventure",
    "приключения": "adventure",
    "стрелялка": "shooter fps",
    "шутер": "shooter fps",
    "стратегия": "strategy",
    "симулятор": "simulator",
    "экшен": "action",
    "ролевая": "rpg",
}

def normalize_catalog_genres(raw_genres: List[str]) -> List[str]:
    canonical = []
    for g in raw_genres:
        g_clean = g.strip().lower()
        if g_clean in EXPANDED_GENRE_MAP:
            norm = EXPANDED_GENRE_MAP[g_clean]
            if norm not in canonical:
                canonical.append(norm)
        else:
            if g.strip() and g.strip() not in canonical:
                canonical.append(g.strip())
    return canonical

def translate_query_multilingual(query: str) -> str:
    tokens = tokenize(query)
    expanded = []
    for t in tokens:
        if t in MULTILINGUAL_QUERY_DICTIONARY:
            expanded.append(MULTILINGUAL_QUERY_DICTIONARY[t])
        else:
            expanded.append(t)
    return " ".join(expanded)

def main():
    print("=" * 80)
    print("EVALUATING MULTILINGUAL NORMALIZATION STRATEGY ON CATALOG & BENCHMARKS")
    print("=" * 80)
    
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
        
    print(f"Loaded {len(catalog)} games.")
    
    # Audit normalization impact on Stardew Valley, Terraria, Hollow Knight, Elden Ring
    target_ids = ["413150", "105600", "367520", "1245620"]
    for game in catalog:
        gid = str(game.get("external_id") or game.get("id"))
        if gid in target_ids:
            raw_g = game.get("genres", [])
            norm_g = normalize_catalog_genres(raw_g)
            print(f"\nGame: {game.get('title')} ({gid})")
            print(f"  Original genres: {raw_g}")
            print(f"  Canonical genres: {norm_g}")
            print(f"  Standard tags (sample): {game.get('tags', [])[:6]}")
            
    # Test query translation
    test_queries = [
        "уютный симулятор фермы",
        "2D песочница крафтинг выживание",
        "cozy ферма game",
        "метроидвания жуки",
        "кооперативный рогалик",
        "space симулятор фабрика"
    ]
    print("\n" + "-" * 80)
    print("MULTILINGUAL QUERY NORMALIZATION EXAMPLES:")
    print("-" * 80)
    for q in test_queries:
        trans = translate_query_multilingual(q)
        print(f"  '{q}' -> '{trans}'")

if __name__ == "__main__":
    main()
