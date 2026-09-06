import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.search.catalog import CatalogManager
from app.search.query_parser import QueryParser

def test_query_parser():
    cm = CatalogManager.get_instance()
    lex = cm.get_lexical_index()
    parser = QueryParser(lexical_index=lex)

    test_cases = [
        ("Cyberpunk 2077", "ENTITY"),
        ("stardew valley", "ENTITY"),
        ("witcher 3", "ENTITY"),
        ("cyberpunk", "TOPIC_TAG"),
        ("soulslike", "TOPIC_TAG"),
        ("cozy farming simulator", "CONCEPT"),
        ("space survival with base building", "CONCEPT"),
        ("games like Stardew Valley", "SIMILARITY"),
        ("similar to Cyberpunk 2077", "SIMILARITY"),
        ("more like Hades", "SIMILARITY"),
        ("cyberpunk open world RPG", "MIXED"),
        ("co-op roguelike shooter", "MIXED"),
    ]

    print("=" * 60)
    print("TESTING QUERY PARSER CLASSIFICATION")
    print("=" * 60)
    
    for query_str, expected_type in test_cases:
        pq = parser.parse(query_str)
        print(f"Query: '{query_str}' -> Type: {pq.query_type} (Expected: {expected_type}), Target: {pq.target_entity}, Modes: {pq.extracted_player_modes}")
        assert pq.query_type == expected_type, f"Failed for '{query_str}': expected {expected_type}, got {pq.query_type}"

    print("\n✓ Subtask 2.2 Query Parser Verified!")

if __name__ == "__main__":
    test_query_parser()
