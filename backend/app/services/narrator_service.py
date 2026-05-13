"""
Narrator Service — Phase 07 (Tasks 26-29)

LLM job #2: receive structured mechanical facts, return Polish prose.
The narrator never decides outcomes — it only describes them.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional

from app.core.logging import get_logger
from app.services.llm_service import generate_chat

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Core system prompt (Task 26)
# ---------------------------------------------------------------------------

NARRATOR_SYSTEM_PROMPT = (
    "Jesteś narratorem mrocznej fantasy. Opisujesz tylko to, co ci podano — "
    "nigdy nie wymyślasz faktów ze świata gry.\n\n"
    "ZASADY:\n"
    "- Pisz po polsku, 2-4 zdania (krótsze w walce, dłuższe w eksploracji)\n"
    "- Opisuj wynik mechaniczny, który otrzymałeś — nie zmieniaj go\n"
    "- Używaj tylko nazw postaci/miejsc/przedmiotów z bloku ŚWIAT\n"
    "- Nie decyduj co się stanie — opisz co się stało\n"
    "- Ton: mroczna fantasy, grim, bez wybranego-przez-los bohatera"
)

# Fallback templates (Task 26/27) — used when LLM fails
FALLBACK_TEMPLATES: dict[str, str] = {
    "ATTACK_HIT": "Cios dosięga celu. Wróg się chwieje.",
    "ATTACK_MISS": "Atak rozmija się w ostatniej chwili.",
    "ATTACK_CRIT": "Druzgocący cios trafia w słaby punkt.",
    "ATTACK_KILL": "Wróg pada, pokonany.",
    "FLEE_SUCCESS": "Udaje ci się wyrwać z walki i zniknąć w ciemnościach.",
    "FLEE_FAIL": "Droga ucieczki jest zablokowana.",
    "ITEM_USE": "Używasz przedmiotu w wirze walki.",
    "FEAR_TRIGGER": "Coś w tej chwili przeszywa cię zimnym dreszczem.",
    "CONDITION_APPLIED": "Nowy stan wpływa na przebieg walki.",
    "ENEMY_ACTION_HIT": "Wróg trafia. Poczułeś ból.",
    "ENEMY_ACTION_MISS": "Atak wroga chybia o włos.",
    "ENEMY_CRIT": "Wróg zadaje okrutny cios.",
    # scene fallbacks
    "SEARCH": "Przeszukujesz okolicę uważnie.",
    "MOVEMENT": "Przemieszczasz się w wyznaczone miejsce.",
    "REST_SHORT": "Odpoczywasz przez chwilę.",
    "REST_LONG": "Noc mija powoli. Budzisz się zmęczony.",
    "EXAMINE": "Badasz obiekt dokładnie.",
    "SKILL_TEST": "Podejmujesz próbę.",
    "SKILL_PASS": "Twoje działanie przynosi efekt.",
    "SKILL_FAIL": "Próba kończy się niepowodzeniem.",
    "CAMPAIGN_EVENT": "Coś się zmieniło w otoczeniu.",
}

# Sentence limits per context (Task 26/29)
SENTENCE_LIMITS: dict[str, int] = {
    "COMBAT": 2,
    "ATTACK_HIT": 2,
    "ATTACK_MISS": 2,
    "ATTACK_CRIT": 2,
    "ATTACK_KILL": 2,
    "FLEE_SUCCESS": 2,
    "FLEE_FAIL": 2,
    "ITEM_USE": 2,
    "FEAR_TRIGGER": 2,
    "CONDITION_APPLIED": 2,
    "ENEMY_ACTION_HIT": 2,
    "ENEMY_ACTION_MISS": 2,
    "ENEMY_CRIT": 2,
    "EXPLORATION": 4,
    "MOVEMENT": 3,
    "DIALOGUE": 4,
    "REST_SHORT": 2,
    "REST_LONG": 3,
    "SEARCH": 3,
    "EXAMINE": 2,
    "SKILL_TEST": 2,
    "CAMPAIGN_EVENT": 4,
    "SCENE": 4,
}

# Generic atmospheric words allowed even if not in ŚWIAT block
_GENERIC_ALLOWED = frozenset([
    "Bóg", "Boga", "Bogów", "Śmierć", "Śmierci", "Chaos", "Przeznaczenie",
    "Ciemność", "Ciemności", "Los", "Losu", "Zło", "Mroczność",
])

# Patterns for detecting invented mechanical numbers (Task 26)
_DAMAGE_PATTERN = re.compile(r"\b\d+\s*(obrażeń|dmg|damage|hp|HP)\b", re.IGNORECASE)
_DICE_PATTERN = re.compile(r"\b(rzucam|wyrzuca|wynik)\s*\d+\b", re.IGNORECASE)
# Any bare number in narration is suspect
_ANY_NUMBER = re.compile(r"\b\d+\b")

# Sentence boundary split
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


# ---------------------------------------------------------------------------
# Data classes (Tasks 27-29)
# ---------------------------------------------------------------------------

@dataclass
class CombatNarrationRequest:
    actor: str
    action_type: str
    target_name: str
    weapon: Optional[str] = None
    # Constraint enforcement only — NOT passed to LLM
    damage_dealt: Optional[int] = None
    target_hp_after: Optional[int] = None
    hit_location: Optional[str] = None
    nat_20: bool = False
    nat_1: bool = False
    condition_applied: Optional[str] = None
    target_is_dead: bool = False
    target_archetype: Optional[str] = None  # goblin/bandit/undead/beast/soldier/boss
    location_name: str = ""


@dataclass
class DialogueTurn:
    speaker: str
    text: str


@dataclass
class NPCDialogueRequest:
    npc_id: str
    npc_name: str
    personality_prompt: str
    knowledge_set: list[str]
    player_input: str
    must_reveal_info: Optional[str] = None
    is_secret: bool = False
    tone_context: str = "WFRP grim dark"
    recent_exchanges: list[DialogueTurn] = field(default_factory=list)
    deceased_npc_context: Optional[str] = None


@dataclass
class LocationContext:
    name: str
    description: str
    archetype: str  # tavern/dungeon/forest/city/ruin/road


@dataclass
class SceneNarrationRequest:
    action_type: str
    outcome: str  # success/fail/critical_success/critical_fail
    location: LocationContext
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    wound_label: Optional[str] = None
    campaign_act: Optional[str] = None
    skill_used: Optional[str] = None
    object_examined: Optional[str] = None
    found_items: list[str] = field(default_factory=list)
    destination: Optional[LocationContext] = None
    atmosphere_disturbed: bool = False


# ---------------------------------------------------------------------------
# Post-processing (Task 26)
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _enforce_length(text: str, action_type: str) -> str:
    limit = SENTENCE_LIMITS.get(action_type, 4)
    sentences = _split_sentences(text)
    return " ".join(sentences[:limit])


def _strip_invented_numbers(text: str) -> str:
    sentences = _split_sentences(text)
    clean = []
    for s in sentences:
        if _DAMAGE_PATTERN.search(s) or _DICE_PATTERN.search(s):
            logger.warning("narrator_invented_number_stripped", sentence=s)
            continue
        clean.append(s)
    return " ".join(clean) if clean else text


def _extract_proper_nouns(text: str) -> list[str]:
    """Extract capitalised words that look like proper nouns."""
    return re.findall(r"\b[A-ZŁÓŚŻŹĆĄĘŃ][a-złóśżźćąęń]+(?:\s+[A-ZŁÓŚŻŹĆĄĘŃ][a-złóśżźćąęń]+)*\b", text)


def _build_allowed_nouns(swiat_block: str) -> set[str]:
    """Extract every capitalised token from the ŚWIAT block as allowed proper nouns."""
    allowed = set(_extract_proper_nouns(swiat_block))
    allowed |= _GENERIC_ALLOWED
    # Also allow individual words of multi-word entries
    for noun in list(allowed):
        for word in noun.split():
            allowed.add(word)
    return allowed


def _word_is_known(word: str, allowed: set[str]) -> bool:
    """Check if a word is known, accounting for Polish inflection (suffix variations)."""
    if word in allowed:
        return True
    # Polish inflection: 'Goblina' derives from 'Goblin' — check if any allowed word is a prefix
    for a in allowed:
        if len(a) >= 4 and word.startswith(a):
            return True
        if len(word) >= 4 and a.startswith(word):
            return True
    return False


def _strip_invented_nouns(text: str, swiat_block: str) -> str:
    if not swiat_block:
        return text
    allowed = _build_allowed_nouns(swiat_block)
    sentences = _split_sentences(text)
    clean = []
    for s in sentences:
        nouns = _extract_proper_nouns(s)
        invented = [n for n in nouns if n not in allowed and n not in _GENERIC_ALLOWED]
        # Only strip if a clearly foreign/made-up name is detected (all words must be unknown)
        if invented:
            all_words_unknown = all(
                all(not _word_is_known(w, allowed) for w in n.split())
                for n in invented
            )
            if all_words_unknown:
                logger.warning("narrator_invented_noun_stripped", sentence=s, invented=invented)
                continue
        clean.append(s)
    # If all sentences were stripped, return the first sentence of the original as minimal output
    if not clean:
        original_sentences = _split_sentences(text)
        return original_sentences[0] if original_sentences else text
    return " ".join(clean)


def post_process(text: str, action_type: str, swiat_block: str = "") -> str:
    text = _strip_invented_numbers(text)
    if swiat_block:
        text = _strip_invented_nouns(text, swiat_block)
    text = _enforce_length(text, action_type)
    return text.strip()


# ---------------------------------------------------------------------------
# LLM call wrapper — raises on failure; callers handle fallback
# ---------------------------------------------------------------------------

_FALLBACK_SENTINEL = object()


def _call_llm(system: str, user: str) -> str:
    """Call LLM; raises RuntimeError on any failure."""
    return generate_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])


def _with_fallback(fn, fallback_key: str, *args, **kwargs) -> str:
    """Run fn(*args, **kwargs); on exception return the fallback template directly."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("narrator_fallback_activated", reason=str(exc), fallback_key=fallback_key)
        return FALLBACK_TEMPLATES.get(fallback_key, "Akcja zostaje wykonana.")


# ---------------------------------------------------------------------------
# Task 27 — Combat narration
# ---------------------------------------------------------------------------

_HIT_LOCATION_INSTRUCTIONS: dict[str, str] = {
    "głowa": "Opisz ogłuszenie, zamazany wzrok, chwiejny krok.",
    "tors": "Opisz głęboką ranę, utrudniony oddech.",
    "prawa_ręka": "Opisz osłabiony uścisk broni, drżące ramię.",
    "lewa_ręka": "Opisz trudności z tarczą lub wolną ręką.",
    "prawa_noga": "Opisz kulawienie, chwiejny krok, oparcie o ścianę.",
    "lewa_noga": "Opisz kulawienie, chwiejny krok, oparcie o ścianę.",
}

_ARCHETYPE_DEATH_FLAVOR: dict[str, str] = {
    "goblin": "Cel jest żałosny i piszczący — pada w kupę.",
    "bandit": "Cel klnie pod nosem, chwyta ranę, pada.",
    "undead": "Cel upada cicho, wreszcie nieruchomy.",
    "beast": "Cel miota się, warczy po raz ostatni, potem nic.",
    "soldier": "Cel pada w szyku, jeszcze ściskając broń.",
    "boss": "To jest decydujący moment — zasługuje na pełne 2 zdania opisu.",
}


def _build_combat_swiat(req: CombatNarrationRequest) -> str:
    parts = [f"lokacja: {req.location_name}" if req.location_name else ""]
    parts.append(f"aktor: {req.actor}")
    parts.append(f"cel: {req.target_name}")
    if req.weapon:
        parts.append(f"broń: {req.weapon}")
    if req.target_archetype:
        parts.append(f"typ_celu: {req.target_archetype}")
    return "\n  ".join(p for p in parts if p)


def _build_combat_special_instructions(req: CombatNarrationRequest) -> str:
    instructions = []
    if req.nat_20:
        instructions.append(
            "To był spektakularny, druzgocący cios. Opisz go jako decydujący moment — "
            "precyzja, brutalna siła, lub szczęśliwy traf."
        )
    if req.nat_1:
        instructions.append(
            "Coś poszło bardzo nie tak. Opisz śmieszne lub niebezpieczne potknięcie aktora — "
            "broń się ślizga, aktor się potyka, cel unika w zabawny sposób. Bez ofiar po stronie aktora."
        )
    if req.target_is_dead:
        flavor = _ARCHETYPE_DEATH_FLAVOR.get(req.target_archetype or "", "")
        instructions.append(
            f"Cel właśnie zginął. Opisz jego śmierć jako zapamiętały moment — "
            f"specyficzny dla tej postaci. {flavor}"
        )
    if req.hit_location and req.hit_location in _HIT_LOCATION_INSTRUCTIONS:
        instructions.append(_HIT_LOCATION_INSTRUCTIONS[req.hit_location])
    if req.action_type == "FEAR_TRIGGER":
        instructions.append(
            "Zanim test strachu — chwilowy opis grozy. \"Terror przeszył cię na wskroś\" lub podobnie. "
            "Jedno zdanie, potem test."
        )
    if req.condition_applied:
        instructions.append(
            f"Stan '{req.condition_applied}' został właśnie nałożony. "
            "Wspomnij go jedną klauzulą, nie pełnym zdaniem."
        )
    return "\n".join(instructions) if instructions else "—"


def narrate_combat_action(req: CombatNarrationRequest) -> str:
    swiat = _build_combat_swiat(req)
    special = _build_combat_special_instructions(req)

    system = (
        "Jesteś narratorem walki. Jedna akcja, 1-2 zdania, po polsku.\n"
        "NIE wspominaj liczb (HP, obrażenia, wyniki kości).\n"
        "NIE wymyślaj nowych postaci ani miejsc."
    )
    user = (
        f"AKCJA:\n"
        f"  aktor: {req.actor}\n"
        f"  typ: {req.action_type}\n"
        f"  broń: {req.weapon or 'gołe ręce'}\n"
        f"  cel: {req.target_name}\n"
        f"  trafienie_krytyczne: {req.nat_20}\n"
        f"  fumble: {req.nat_1}\n"
        f"  lokacja_trafienia: {req.hit_location or '—'}\n"
        f"  stan_zastosowany: {req.condition_applied or '—'}\n"
        f"  cel_martwy: {req.target_is_dead}\n\n"
        f"ŚWIAT:\n  {swiat}\n\n"
        f"SPECJALNE INSTRUKCJE:\n{special}\n\n"
        f"Opisz tę akcję w 1-2 zdaniach."
    )

    def _do():
        raw = _call_llm(system, user)
        return post_process(raw, req.action_type, swiat)

    return _with_fallback(_do, req.action_type)


async def narrate_round(actions: list[CombatNarrationRequest]) -> list[str]:
    """Parallel narration for all actions in a combat round."""
    async def _async_narrate(req: CombatNarrationRequest) -> str:
        # narrate_combat_action already has fallback; exceptions from asyncio.to_thread
        # are still possible if something unexpected happens
        try:
            return await asyncio.to_thread(narrate_combat_action, req)
        except Exception as exc:
            logger.warning("narrator_round_action_failed", reason=str(exc), action=req.action_type)
            return FALLBACK_TEMPLATES.get(req.action_type, "Akcja zostaje wykonana.")

    tasks = [_async_narrate(a) for a in actions]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        r if isinstance(r, str) else FALLBACK_TEMPLATES.get(actions[i].action_type, "Akcja zostaje wykonana.")
        for i, r in enumerate(results)
    ]


# ---------------------------------------------------------------------------
# Task 28 — NPC dialogue narration
# ---------------------------------------------------------------------------

def narrate_npc_dialogue(req: NPCDialogueRequest) -> str:
    # Build knowledge list
    knowledge_lines = "\n".join(f"- {k}" for k in req.knowledge_set) if req.knowledge_set else "- (brak szczególnej wiedzy)"

    # Build recent exchanges
    exchanges_text = ""
    if req.recent_exchanges:
        lines = []
        for turn in req.recent_exchanges[-5:]:
            lines.append(f'{turn.speaker}: "{turn.text}"')
        exchanges_text = "OSTATNIA ROZMOWA:\n" + "\n".join(lines) + "\n\n"

    # must_reveal section
    reveal_section = ""
    if req.must_reveal_info:
        reveal_section = f"OBOWIĄZKOWO WSPOMNIJ: {req.must_reveal_info}\nWłącz tę informację naturalnie w swoją odpowiedź.\n"
        if req.is_secret:
            reveal_section += (
                "UJAWNIJ TĘ INFORMACJĘ NIECHĘTNIE. Zachowuj się, jakbyś wolał/a zachować ją dla siebie — "
                "może po dłuższym nacisku, może ze wstydem, może ze strachem.\n"
            )
        reveal_section += "\n"

    # deceased NPC context
    deceased_section = ""
    if req.deceased_npc_context:
        deceased_section = f"UWAGA: {req.deceased_npc_context}\n\n"

    system = (
        f"Wciel się w postać {req.npc_name}.\n"
        f"Osobowość: {req.personality_prompt}\n"
        f"Styl: {req.tone_context}\n\n"
        f"Wiesz tylko to, co jest poniżej. Nie odpowiadaj na pytania spoza tej wiedzy.\n"
        f"WIEDZA POSTACI:\n{knowledge_lines}"
    )

    user = (
        f"{reveal_section}"
        f"{deceased_section}"
        f"{exchanges_text}"
        f"Gracz mówi: \"{req.player_input}\"\n\n"
        f"Odpowiedz w pierwszej osobie, jako {req.npc_name}. Maksymalnie 4 zdania."
    )

    swiat = f"{req.npc_name}\n{req.personality_prompt}"

    def _do():
        raw = _call_llm(system, user)
        return post_process(raw, "DIALOGUE", swiat)

    return _with_fallback(_do, "DIALOGUE")


# ---------------------------------------------------------------------------
# Task 29 — Scene narration
# ---------------------------------------------------------------------------

_SCENE_SENTENCE_LIMITS: dict[str, int] = {
    "SEARCH": 3,
    "MOVEMENT": 3,
    "REST_SHORT": 2,
    "REST_LONG": 3,
    "EXAMINE": 2,
    "SKILL_TEST": 2,
    "CAMPAIGN_EVENT": 4,
}

_REST_ARCHETYPE_HINTS: dict[str, str] = {
    "dungeon": "Odpoczynek jest niespokojny — gracz jest w niebezpiecznym miejscu.",
    "ruin": "Odpoczynek jest niespokojny — gracz jest w niebezpiecznym miejscu.",
    "forest": "Odpoczynek jest niespokojny — gracz jest w niebezpiecznym miejscu.",
    "tavern": "Odpoczynek jest względnie bezpieczny, ale nawet tu nie ma prawdziwego spokoju.",
    "inn": "Odpoczynek jest względnie bezpieczny, ale nawet tu nie ma prawdziwego spokoju.",
}

_DARK_FANTASY_STYLE_BLOCK = (
    "STYL:\n"
    "- Nigdy nie opisuj doskonałego, spokojnego odpoczynku — zawsze pozostaje jakiś niepokój\n"
    "- Świat jest wrogi i obojętny — nie sprzyja graczowi\n"
    "- Piękno jest zimne lub złowrogie\n"
    "- Gracz nie jest wybrańcem losu — jest tylko człowiekiem w ciemnym miejscu"
)


def _build_scene_swiat(req: SceneNarrationRequest) -> str:
    parts = [
        f"lokacja: {req.location.name}",
        f"opis: {req.location.description}",
        f"typ: {req.location.archetype}",
    ]
    if req.destination:
        parts.append(f"cel_podróży: {req.destination.name}")
    return "\n  ".join(parts)


def narrate_scene(req: SceneNarrationRequest) -> str:
    limit = _SCENE_SENTENCE_LIMITS.get(req.action_type, 4)
    swiat = _build_scene_swiat(req)

    # Build optional context blocks
    destination_block = ""
    if req.destination:
        destination_block = (
            f"\nDOCELOWA LOKACJA:\n"
            f"  Nazwa: {req.destination.name}\n"
            f"  Opis: {req.destination.description}"
        )

    found_block = ""
    if req.found_items:
        found_block = f"\nZNALEZIONE PRZEDMIOTY: {', '.join(req.found_items)}"

    examined_block = ""
    if req.object_examined:
        examined_block = f"\nBADANY OBIEKT: {req.object_examined}"

    disturbed_block = ""
    if req.atmosphere_disturbed and not req.found_items:
        disturbed_block = (
            "\nPrzeszukując, gracz coś porusza/niepokoi. "
            "Opisz atmosferyczny niepokojący szczegół — nie bezpośrednie niebezpieczeństwo."
        )

    rest_hint = ""
    if req.action_type in ("REST_SHORT", "REST_LONG"):
        rest_hint = _REST_ARCHETYPE_HINTS.get(req.location.archetype, "")

    system = (
        f"Jesteś narratorem mrocznej fantasy. Opisz scenę po polsku, {limit} zdania.\n"
        f"Ton: grim dark, Warhammer Fantasy. Nigdy nie opisuj spokojnej, bezpiecznej idylli.\n"
        f"Używaj tylko nazw z bloków LOKACJA i ŚWIAT.\n"
        f"Nie wspominaj liczb mechanicznych.\n\n"
        f"{_DARK_FANTASY_STYLE_BLOCK}"
    )

    user = (
        f"AKCJA: {req.action_type}\n"
        f"WYNIK: {req.outcome}\n"
        f"PORA DNIA: {req.time_of_day or 'nieznana'}\n"
        f"POGODA: {req.weather or 'nieznana'}\n"
        f"STAN GRACZA: {req.wound_label or 'Nieuszkodzony'}\n\n"
        f"LOKACJA:\n"
        f"  Nazwa: {req.location.name}\n"
        f"  Opis: {req.location.description}\n"
        f"  Typ: {req.location.archetype}"
        f"{destination_block}"
        f"{found_block}"
        f"{examined_block}"
        f"{disturbed_block}\n\n"
        f"KONTEKST KAMPANII: {req.campaign_act or '—'}\n"
        f"{f'WSKAZÓWKA ODPOCZYNKU: {rest_hint}' if rest_hint else ''}\n\n"
        f"PRZYPOMNIENIE: Nigdy nie opisuj spokojnego, doskonałego odpoczynku — zawsze pozostaje jakiś niepokój.\n\n"
        f"Opisz scenę."
    )

    def _do():
        raw = _call_llm(system, user)
        return post_process(raw, req.action_type, swiat)

    return _with_fallback(_do, req.action_type)


# ---------------------------------------------------------------------------
# Task 26 — Main turn narrator (full turn narration)
# ---------------------------------------------------------------------------

def narrate_turn(
    action_type: str,
    mechanical_result: dict,
    location_name: str,
    location_description: str,
    npc_info: str = "",
    previous_context: str = "",
    wound_label: str = "",
    fear_state: str = "",
    campaign_act: str = "",
) -> str:
    """
    Primary narrator call for a full player turn.
    Receives all mechanical facts, returns 2-4 sentences of Polish prose.
    """
    swiat_parts = [f"lokacja: {location_name}", f"opis: {location_description}"]
    if npc_info:
        swiat_parts.append(f"postacie: {npc_info}")

    swiat_block = "\n  ".join(swiat_parts)

    # Format mechanical result as key: value lines
    mech_lines = "\n  ".join(f"{k}: {v}" for k, v in mechanical_result.items())

    context_section = ""
    if previous_context:
        context_section = f"\nPOPRZEDNI_KONTEKST:\n  {previous_context}\n"

    state_lines = []
    if wound_label:
        state_lines.append(f"rany: {wound_label}")
    if fear_state:
        state_lines.append(f"strach: {fear_state}")
    state_section = ""
    if state_lines:
        state_section = "\nSTAN POSTACI:\n  " + "\n  ".join(state_lines) + "\n"

    limit = SENTENCE_LIMITS.get(action_type, 4)
    task_sentence = f"Opisz wynik akcji w {limit} zdaniach."

    user = (
        f"MECHANIKA:\n  akcja: {action_type}\n  {mech_lines}\n\n"
        f"ŚWIAT:\n  {swiat_block}\n"
        f"{context_section}"
        f"{state_section}"
        f"KONTEKST KAMPANII: {campaign_act or '—'}\n\n"
        f"ZADANIE: {task_sentence}"
    )

    def _do():
        raw = _call_llm(NARRATOR_SYSTEM_PROMPT, user)
        return post_process(raw, action_type, swiat_block)

    return _with_fallback(_do, action_type)
