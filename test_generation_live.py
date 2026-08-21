import sys
import asyncio
import os
from dotenv import load_dotenv

sys.path.insert(0, "backend")
load_dotenv("backend/.env")
from app.ai.hosted_provider import GeminiProvider
from app.services.game_generation_service import GameGenerationService

async def test_generation():
    provider = GeminiProvider()
    service = GameGenerationService(provider=provider)
    
    prompt = "Cyberpunk neon survival arena with roaming drone enemies and health crystals"
    
    print("Requesting Game DSL generation from Google Gemini (Gemini 3 Flash Preview: gemini-3-flash-preview)...")
    start_time = asyncio.get_event_loop().time()
    try:
        result = await service.generate_game_dsl(
            prompt=prompt,
            engine="Phaser 3.88.2",
            art_density=75,
            physics=85,
            modules=["Procedural Generation", "Enhanced NPC Behavior", "Resource & Score Economy"],
            emit_log=lambda lvl, msg: print(f"[{lvl}] {msg}"),
        )
        elapsed = asyncio.get_event_loop().time() - start_time
        if result.success:
            dsl = result.dsl
            meta = result.provider_meta
            print(f"\n[OK] Generation succeeded in {elapsed:.2f}s!")
            print(f"Title: {dsl.metadata.title}")
            print(f"Genre: {dsl.metadata.genre}")
            print(f"Archetype: {dsl.metadata.archetype}")
            print(f"Entities ({len(dsl.entities)}): {[e.id for e in dsl.entities]}")
            print(f"Rules ({len(dsl.rules)}): {[r.trigger for r in dsl.rules]}")
            print(f"Metadata: {meta}")
            print("\n[SMOKE TEST PASSED]")
        else:
            print(f"\n[FAILED] Generation returned success=False in {elapsed:.2f}s: {result.error_message}")
            sys.exit(1)
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        print(f"\n[FAILED] in {elapsed:.2f}s: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_generation())
