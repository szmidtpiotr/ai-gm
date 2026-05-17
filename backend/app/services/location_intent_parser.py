"""Phase 8D — Parser intencji ruchu (Opcja A JSON + Opcja B fallback)."""

import json
import re
from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger
from app.services.llm_service import generate_chat
from app.services.location_config_service import get_bool_flag

logger = get_logger(__name__)


@dataclass
class LocationIntent:
    """Reprezentacja intencji zmiany lokalizacji."""
    action: str  # 'move' | 'create'
    target_label: str
    target_key: Optional[str] = None
    parent_key: Optional[str] = None
    description: Optional[str] = None


# Prompt dla Opcji B (fallback parser)
FALLBACK_PARSER_PROMPT = """Przeanalizuj poniższą narrację gracza i odpowiedz TYLKO w formacie JSON.

Zadanie: Wykryj czy gracz wyraźnie wyraża intencję przemieszczenia się do innej lokalizacji.

Odpowiedz w formacie:
{{"moved": true/false, "target_label": "nazwa lokalizacji lub null", "confidence": "high/medium/low"}}

Gdzie:
- "moved": true - gracz wyraźnie zmienia lokalizację
- "target_label": nazwa nowej lokalizacji (jeśli moved=true) lub null
- "confidence": jak pewny jesteś wykrycia (high=wyraźna zmiana, medium=możliwa, low=niejasne)

Zasady:
1. Tylko wyraźne przemieszczenia (np. "idę do...", "wracam do...", "przechodzę do...")
2. Pomijaj meta-akcje (rozmowy, ataki, używanie przedmiotów bez ruchu)
3. Jeśli gracz pozostaje w tym samym miejscu → "moved": false

Narracja: {text}

JSON:"""


def _clean_json_response(text: str) -> str:
    """Czyści odpowiedź LLM ze znaczników markdown i nadmiarowych białych znaków."""
    # Usuń znaczniki markdown ```json ... ```
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    # Usuń prefiks "JSON:" jeśli istnieje
    text = re.sub(r'^[\s\n]*JSON:\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _escape_unescaped_control_chars_in_json_strings(text: str) -> str:
    """
    Escape raw control characters inside JSON string literals.

    Some LLM responses embed literal newlines/tabs in `narrative`, which makes
    `json.loads` fail with "Invalid control character". We normalize only when
    inside quoted JSON strings.
    """
    out: list[str] = []
    in_string = False
    escaped = False

    for ch in text:
        if escaped:
            out.append(ch)
            escaped = False
            continue

        if ch == "\\":
            out.append(ch)
            escaped = True
            continue

        if ch == '"':
            out.append(ch)
            in_string = not in_string
            continue

        if in_string:
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue

        out.append(ch)

    return "".join(out)


def _parse_json_safely(text: str) -> Optional[dict]:
    """Bezpiecznie parsuje JSON, zwraca None przy błędzie."""
    try:
        cleaned = _clean_json_response(text)
        # Weź tylko pierwszy obiekt JSON (do zamknięcia nawiasu)
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = cleaned[start:end+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _escape_unescaped_control_chars_in_json_strings(candidate)
            return json.loads(repaired)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("json_parse_error", error=str(e), text_preview=text[:200])
        return None


def _extract_location_intent_from_json(data: dict) -> Optional[LocationIntent]:
    """Wyciąga LocationIntent ze sparsowanego JSON."""
    location_intent = data.get("location_intent")
    if not location_intent or location_intent is None:
        return None
    
    if isinstance(location_intent, dict):
        action = location_intent.get("action", "move")
        target_label = location_intent.get("target_label")
        target_key = location_intent.get("target_key")
        parent_key = location_intent.get("parent_key")
        description = location_intent.get("description")
        
        if target_label:
            return LocationIntent(
                action=action,
                target_label=target_label,
                target_key=target_key,
                parent_key=parent_key,
                description=description
            )
    
    return None


def parse_option_a(gm_response_text: str, session_id: Optional[int] = None) -> Optional[LocationIntent]:
    """
    Opcja A: Parsuje JSON wrapper z odpowiedzi GM.
    
    Oczekuje pola 'location_intent' w JSON:
    {"narrative": "...", "location_intent": {"action": "move", "target_label": "..."}}
    
    Returns:
        LocationIntent lub None (brak intencji / niepoprawny JSON)
    """
    data = _parse_json_safely(gm_response_text)
    if not data:
        return None
    
    intent = _extract_location_intent_from_json(data)
    if intent:
        logger.info("location_intent_parsed_option_a", 
                   action=intent.action, 
                   target_label=intent.target_label,
                   session_id=session_id)
    return intent


def parse_option_b(narrative_text: str, session_id: Optional[int] = None) -> Optional[LocationIntent]:
    """
    Opcja B: Fallback parser wysyła osobny prompt do LLM.
    
    Wywoływany TYLKO gdy Opcja A nie zadziała i location_parser_fallback_enabled=1.
    
    Returns:
        LocationIntent lub None
    """
    prompt = FALLBACK_PARSER_PROMPT.format(text=narrative_text[:2000])  # Limit długości
    
    try:
        response = generate_chat(
            messages=[
                {"role": "system", "content": "Jesteś precyzyjnym parserem intencji ruchu. Odpowiadaj tylko JSON."},
                {"role": "user", "content": prompt}
            ],
            model=None,
            llm_config=None  # Użyje domyślnego config
        )
        
        data = _parse_json_safely(response or "")
        if not data:
            return None
        
        moved = data.get("moved", False)
        target_label = data.get("target_label")
        confidence = data.get("confidence", "low")
        
        # Akceptuj tylko wyraźne zmiany (high/medium confidence + moved=true + target_label)
        if moved and target_label and confidence in ("high", "medium"):
            intent = LocationIntent(
                action="move",
                target_label=target_label,
                target_key=None,  # Opcja B nie generuje kluczy
                parent_key=None,
                description=None
            )
            logger.info("location_intent_parsed_option_b",
                       target_label=target_label,
                       confidence=confidence,
                       session_id=session_id)
            return intent
        
        return None
        
    except Exception as e:
        logger.error("location_intent_option_b_error", error=str(e), session_id=session_id)
        return None


def _parse_location_tag_format(text: str) -> Optional[LocationIntent]:
    """
    Parse the ▼ LOCATION: action → label\\n{json} format emitted by the LLM.
    Example:
      ▼ LOCATION: create → Opuszczona biblioteka
      {"action": "create", "target_label": "...", "description": "..."}
    """
    # Match ▼ LOCATION: (create|move) → label
    m = re.search(r'[▼▶]\s*LOCATION\s*:\s*(create|move)\s*[→>\-]+\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if not m:
        return None
    action = m.group(1).strip().lower()
    label_from_tag = m.group(2).strip()

    # Try to find a JSON block after the tag
    json_m = re.search(r'\{[^{}]*"action"[^{}]*\}', text[m.end():m.end()+800], re.DOTALL)
    if json_m:
        try:
            data = json.loads(json_m.group(0))
            return LocationIntent(
                action=data.get("action", action),
                target_label=data.get("target_label") or label_from_tag,
                target_key=data.get("target_key"),
                parent_key=data.get("parent_key"),
                description=data.get("description"),
            )
        except Exception:
            pass

    # Fallback: use just the tag info
    return LocationIntent(action=action, target_label=label_from_tag)


def parse(gm_response_text: str, session_id: Optional[int] = None) -> Optional[LocationIntent]:
    """
    Główna funkcja parsera zgodna z D-LOC-06.
    
    Flow:
    1. Sprawdź flagę location_parser_json_enabled
    2. Jeśli włączona → Opcja A (JSON wrapper)
    3. Jeśli Opcja A się nie powiedzie + fallback włączony → Opcja B
    4. Jeśli obie opcje fail lub wyłączone → return None
    
    Args:
        gm_response_text: pełna odpowiedź GM (może zawierać JSON)
        session_id: ID sesji do sprawdzenia flag
    
    Returns:
        LocationIntent lub None (brak intencji / błąd)
    """
    try:
        # Sprawdź czy Location Integrity jest włączone
        if not get_bool_flag("location_integrity_enabled", session_id, default=True):
            logger.debug("location_integrity_disabled", session_id=session_id)
            return None
        
        option_a_enabled = get_bool_flag("location_parser_json_enabled", session_id, default=True)
        option_b_enabled = get_bool_flag("location_parser_fallback_enabled", session_id, default=True)
        
        # Opcja 0: ▼ LOCATION: tag format (LLM native output)
        tag_intent = _parse_location_tag_format(gm_response_text)
        if tag_intent:
            logger.info("location_intent_parsed_tag_format",
                        action=tag_intent.action, target_label=tag_intent.target_label,
                        session_id=session_id)
            return tag_intent

        # Opcja A: JSON wrapper
        if option_a_enabled:
            intent = parse_option_a(gm_response_text, session_id)
            if intent:
                return intent
            # Jeśli A nie zadziała, przejdź do B (jeśli włączone)
        
        # Opcja B: Fallback parser (tylko gdy A nie zadziała i B włączone)
        if option_b_enabled:
            # Wyciągnij sam tekst narracji (bez JSON wrappera jeśli istnieje)
            data = _parse_json_safely(gm_response_text)
            if data and "narrative" in data:
                narrative = data["narrative"]
            else:
                narrative = gm_response_text
            
            return parse_option_b(narrative, session_id)
        
        return None
        
    except Exception as e:
        logger.error("location_intent_parse_error", error=str(e), session_id=session_id)
        return None
