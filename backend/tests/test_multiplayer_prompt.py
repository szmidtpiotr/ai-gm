"""
TOR 2 — Manual test: multiplayer GM narration.

Simulates one round with 4 players sending simultaneous actions.
Tests: 3rd-person narration, action conflict resolution, per-player output.

Run inside backend container:
    python tests/test_multiplayer_prompt.py
"""

import json
import sys
import os

sys.path.insert(0, "/app")
os.environ.setdefault("LLM_PROVIDER", "")  # use runtime config

from app.services import llm_service

MULTIPLAYER_SYSTEM_PROMPT = """Jesteś Mistrzem Gry w tekstowej grze RPG osadzonej w mrocznym świecie fantasy.
Odpowiadasz WYŁĄCZNIE po polsku.

## TRYB MULTIPLAYER — ZASADY NADRZĘDNE

Prowadzisz grupę graczy (2–4 osoby) w TRYBIE MULTIPLAYER. Wszystkie zasady solo nadal obowiązują, ale:

### NARRACJA W TRZECIEJ OSOBIE
- Narruj w TRZECIEJ osobie (nie "widzisz" lecz "widzą", "Aldric zauważa", "Mira czuje").
- Każdego gracza adresuj po imieniu jego postaci.
- Akcje wszystkich graczy w rundzie dzieją się RÓWNOCZEŚNIE — narruj je jako jedną spójną scenę.

### JEDNOCZESNOŚĆ AKCJI
- Wszyscy gracze w rundzie działają w tym samym momencie.
- Nie ma kolejki — narruj jakby wszyscy ruszyli jednocześnie.
- Jeśli akcje graczy są SPRZECZNE (jeden atakuje NPC którego drugi chce przekonać słowami):
  → Najpierw opisz co każdy próbuje zrobić.
  → Następnie rozstrzygnij konflikt logicznie (przemoc wyklucza dialog w tej rundzie).
  → Narruj naturalną konsekwencję konfliktu.

### FORMAT ODPOWIEDZI MULTIPLAYER
Odpowiedź musi być JSON z polami:
{
  "narrative": "Narracja całej rundy w 3. osobie. Opis akcji wszystkich graczy i ich wyników.",
  "roll_cues": [
    {"player": "nazwa_gracza", "skill": "Perception", "dc": 12, "reason": "krótki powód"}
  ],
  "player_notes": {
    "nazwa_gracza": "Informacja przeznaczona tylko dla tego gracza (co widzi, czuje, co mu się wydarzyło osobno)"
  }
}

- "roll_cues" — lista rzutów których potrzebuje GM by kontynuować. Puste [] jeśli nie ma.
- "player_notes" — prywatne informacje dla poszczególnych graczy. Pomiń klucz jeśli nie ma nic prywatnego.
- Jeśli akcja gracza wymaga rzutu (ryzykowna) — uwzględnij go w roll_cues, nie blokuj narracji.

### STYL
- Nie powtarzaj opisów otoczenia — tylko zmiany i akcje.
- Max 5 akapitów na narrację zbiorową.
- Każda postać powinna mieć swój moment w narracji tej rundy.
"""

SCENE_CONTEXT = """
[SCENA]
Komnata przed żelazną kratą. Pojedynczy strażnik (Zbrojny Wartownik) stoi przy drzwiach — uzbrojony, czujny.
Za kratą widać skrzynię i ciemny korytarz prowadzący głębiej.

[GRACZE]
- Aldric (Wojownik, Poz. 3) — ciężka zbroja, topór dwuręczny
- Mira (Czarodziejka, Poz. 2) — laska arcana, zna zaklęcie sen (Zasypij)
- Zara (Łotr, Poz. 2) — lekka zbroja, sztylet, specjalizacja: skradanie
- Borin (Wojownik, Poz. 3) — tarcza i miecz, doświadczony weteran

[HISTORIA]
Gracze weszli do komnaty razem. Strażnik ich zauważył, ale nie krzyknął jeszcze — czeka, lekko spięty.
"""

ROUND_ACTIONS = """
[AKCJE RUNDY — wszyscy działają jednocześnie]

Aldric: "Ruszam na strażnika z toporem — atak!"
Mira: "Rzucam Zasypij na strażnika zanim Aldric dotrze — chcę go uśpić bez walki!"
Zara: "Kiedy wszyscy skupiają uwagę strażnika, kradnę się wzdłuż ściany w stronę kraty."
Borin: "Zostanę z tyłu i pilnuję czy nie nadchodzi ktoś z korytarza skąd przyszliśmy."
"""


def _load_active_preset() -> dict:
    import sqlite3
    conn = sqlite3.connect("/data/ai_gm.db")
    conn.row_factory = sqlite3.Row
    meta = conn.execute(
        "SELECT value FROM game_config_meta WHERE key='llm_global_active_preset_id'"
    ).fetchone()
    if not meta:
        conn.close()
        return {}
    preset_id = int(meta["value"])
    row = conn.execute(
        "SELECT provider, base_url, model, api_key FROM llm_connection_presets WHERE id=?",
        (preset_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def run_test():
    preset = _load_active_preset()
    if preset:
        llm_service.set_runtime_config(
            provider=preset["provider"],
            base_url=preset["base_url"],
            model=preset["model"],
            api_key=preset["api_key"] or "",
        )
    cfg = llm_service.get_effective_config()
    print(f"LLM: {cfg['provider']} / {cfg['model']} @ {cfg['base_url']}\n")

    messages = [
        {"role": "system", "content": MULTIPLAYER_SYSTEM_PROMPT},
        {"role": "user", "content": SCENE_CONTEXT + "\n" + ROUND_ACTIONS},
    ]

    print("=" * 60)
    print("SCENA: Komnata ze strażnikiem")
    print("AKCJE: Aldric=atak, Mira=zaklęcie sen, Zara=skradanie, Borin=straż tyłów")
    print("=" * 60)
    print()

    provider_name = cfg["provider"]
    if provider_name == "openai":
        driver = llm_service.OpenAIDriver()
    elif provider_name == "azure":
        driver = llm_service.AzureDriver()
    else:
        driver = llm_service.OllamaDriver()

    raw = driver.generate_chat(
        base_url=cfg["base_url"],
        model=cfg["model"],
        messages=messages,
        api_key=cfg.get("api_key", ""),
    )

    print("RAW RESPONSE:")
    print(raw)
    print()

    try:
        # strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        parsed = json.loads(clean)
        print("PARSED narrative:")
        print(parsed.get("narrative", ""))
        print()
        if parsed.get("roll_cues"):
            print("ROLL CUES:", json.dumps(parsed["roll_cues"], ensure_ascii=False, indent=2))
        if parsed.get("player_notes"):
            print("PLAYER NOTES:", json.dumps(parsed["player_notes"], ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"(JSON parse failed: {e} — raw output above)")


if __name__ == "__main__":
    run_test()
