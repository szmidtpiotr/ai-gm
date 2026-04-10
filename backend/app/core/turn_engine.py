from app.services.ollama_service import OllamaService, OllamaServiceError

SYSTEM_PROMPTS = {
    "warhammer": (
        "Jesteś mistrzem gry RPG Warhammer. "
        "Opisz po polsku. Używaj prostych słów. "
        "Krótkie zdania. Kończ: 'Co robisz?'"
    ),
    "cyberpunk": (
        "Jesteś mistrzem gry RPG cyberpunk. "
        "Opisz po polsku. Używaj prostych słów. "
        "Krótkie zdania. Kończ: 'Co robisz?'"
    ),
    "neuroshima": (
        "Jesteś mistrzem gry RPG Neuroshima. "
        "Opisz po polsku. Używaj prostych słów. "
        "Krótkie zdania. Kończ: 'Co robisz?'"
    ),
    "fantasy": (
        "Jesteś mistrzem gry RPG fantasy. "
        "Opisz po polsku. Używaj prostych słów. "
        "Krótkie zdania. Kończ: 'Co robisz?'"
    ),
}

ENGINE_MODEL_MAP = {
    "gemma3:1b": "gemma3:1b",
    "llama3.2": "llama3.2:latest",
}

def _normalize_system(system: str | None) -> str:
    return (system or "fantasy").strip().lower()

def _resolve_model(engine: str | None) -> str:
    engine = (engine or "").strip().lower()
    return ENGINE_MODEL_MAP.get(engine, "gemma3:1b")

def run_narrative_turn(*, campaign_id: int, character_id: int, text: str, 
                      system: str | None, engine: str | None, game_id: int | None = None) -> dict:
    clean_text = text.strip()
    if len(clean_text) < 3:
        return {"route": "narrative", "result": {"message": "Wpisz więcej tekstu.", "campaign_id": campaign_id}}
    
    system_key = _normalize_system(system)
    system_prompt = SYSTEM_PROMPTS.get(system_key, SYSTEM_PROMPTS["fantasy"])
    model = _resolve_model(engine)
    
    service = OllamaService()
    
    try:
        narrative_text = service.generate_narrative(
            model=model,
            system_prompt=f"{system_prompt}\n\nPROSTE SŁOWA. TYLKO POLSKI. BEZ BŁĘDÓW.",
            user_text=clean_text,
            character_id=character_id,
            campaign_id=campaign_id,
            game_id=game_id,
        )
    except OllamaServiceError:
        return {"route": "narrative", "result": {"message": "Narracja niedostępna.", "campaign_id": campaign_id}}
    
    return {
        "route": "narrative",
        "result": {
            "message": narrative_text,
            "campaign_id": campaign_id,
            "character_id": character_id,
            "text": clean_text,
            "system": system_key,
            "engine": model,
        },
    }