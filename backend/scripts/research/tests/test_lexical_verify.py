import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.search.catalog import CatalogManager
from app.search.lexical import normalize_string

def test_lexical():
    cm = CatalogManager.get_instance()
    lex = cm.get_lexical_index()
    assert lex is not None, "LexicalIndex must be initialized"
    
    # 1. Test Stardew Valley entity resolution
    stardew = lex.resolve_entity("stardew")
    assert stardew is not None, "Alias 'stardew' must resolve"
    assert "Stardew Valley" in stardew["title"]
    print(f"✓ Resolved 'stardew' -> {stardew['title']} (Genres: {stardew['genres']})")
    
    # 2. Test Cyberpunk 2077 entity resolution
    cp = lex.resolve_entity("cyberpunk 2077")
    assert cp is not None, "Cyberpunk 2077 must resolve"
    print(f"✓ Resolved 'cyberpunk 2077' -> {cp['title']}")
    
    # 3. Test Witcher 3 alias resolution
    w3 = lex.resolve_entity("witcher 3")
    assert w3 is not None, "Witcher 3 must resolve"
    print(f"✓ Resolved 'witcher 3' -> {w3['title']}")
    
    # 4. Test lexical search for topic 'cyberpunk'
    results = lex.search_lexical("cyberpunk", limit=5)
    print("\nLexical search for 'cyberpunk':")
    for g, score, details in results[:5]:
        print(f"  [{score:.2f}] {g['title']} (Details: {details})")
        
    print("\n✓ Subtask 2.1 Lexical Index Verified!")

if __name__ == "__main__":
    test_lexical()
