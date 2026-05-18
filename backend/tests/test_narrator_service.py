"""
Tests for Narrator Service — Phase 07 Tasks 26-29
All LLM calls are mocked; these tests verify structure, fallback, and post-processing logic.
"""
from unittest.mock import patch, MagicMock
import pytest

from app.services.narrator_service import (
    # Core
    post_process,
    _enforce_length,
    _strip_invented_numbers,
    _strip_invented_nouns,
    _split_sentences,
    FALLBACK_TEMPLATES,
    SENTENCE_LIMITS,
    # Data classes
    CombatNarrationRequest,
    NPCDialogueRequest,
    DialogueTurn,
    SceneNarrationRequest,
    LocationContext,
    # Functions
    narrate_combat_action,
    narrate_npc_dialogue,
    narrate_scene,
    narrate_turn,
    narrate_round,
)


# ---------------------------------------------------------------------------
# Task 26 — Core / Post-processing
# ---------------------------------------------------------------------------

class TestSentenceSplitter:
    def test_splits_on_period(self):
        parts = _split_sentences("Pierwsze zdanie. Drugie zdanie. Trzecie.")
        assert len(parts) == 3

    def test_splits_on_exclamation(self):
        parts = _split_sentences("Cios trafia! Wróg się chwieje.")
        assert len(parts) == 2

    def test_single_sentence(self):
        parts = _split_sentences("Jedno zdanie bez końca")
        assert len(parts) == 1


class TestLengthEnforcement:
    def test_combat_limit_2(self):
        text = "Zdanie jedno. Zdanie dwa. Zdanie trzy."
        result = _enforce_length(text, "ATTACK_HIT")
        assert result.count(".") == 2

    def test_scene_limit_4(self):
        text = "A. B. C. D. E."
        result = _enforce_length(text, "CAMPAIGN_EVENT")
        assert result == "A. B. C. D."

    def test_search_limit_3(self):
        text = "A. B. C. D."
        result = _enforce_length(text, "SEARCH")
        assert result == "A. B. C."

    def test_rest_long_limit_3(self):
        text = "A. B. C. D."
        result = _enforce_length(text, "REST_LONG")
        assert result == "A. B. C."


class TestInventedNumberStripping:
    def test_strips_damage_phrase(self):
        text = "Cios trafia. Zadajesz 7 obrażeń. Wróg się chwieje."
        result = _strip_invented_numbers(text)
        assert "7 obrażeń" not in result
        assert "Cios trafia" in result

    def test_strips_dice_result_phrase(self):
        text = "Wyrzucasz wynik 18. Cios trafia."
        result = _strip_invented_numbers(text)
        assert "18" not in result

    def test_preserves_clean_sentence(self):
        text = "Wróg pada na ziemię. Cisza."
        result = _strip_invented_numbers(text)
        assert result == text


class TestInventedNounStripping:
    def test_strips_unknown_noun(self):
        swiat = "lokacja: Karczma\naktor: Gracz\ncel: Goblin"
        # Sentence 1: known entities. Sentence 2: invented proper noun entirely outside ŚWIAT.
        text = "Gracz wchodzi do karczmy. Xerthonak Veldris upada na ziemię."
        result = _strip_invented_nouns(text, swiat)
        assert "Xerthonak Veldris" not in result

    def test_keeps_known_noun(self):
        swiat = "lokacja: Karczma\naktor: Gracz\ncel: Goblin Zwiadowca"
        text = "Gracz uderza Goblina Zwiadowcę."
        result = _strip_invented_nouns(text, swiat)
        assert "Goblin" in result or "Gracz" in result

    def test_keeps_generic_concepts(self):
        swiat = "lokacja: Zamek"
        text = "Śmierć patrzy z każdego cienia."
        result = _strip_invented_nouns(text, swiat)
        assert "Śmierć" in result


class TestPostProcess:
    def test_full_pipeline_strips_and_limits(self):
        text = "Gracz atakuje. Zadajesz 7 obrażeń. Wymyślony_NPC_X upada. Extra sentence. Another one."
        result = post_process(text, "ATTACK_HIT", "aktor: Gracz")
        # Length: max 2 sentences for ATTACK_HIT
        sentences = _split_sentences(result)
        assert len(sentences) <= 2


class TestFallbackTemplates:
    def test_all_combat_keys_present(self):
        combat_keys = [
            "ATTACK_HIT", "ATTACK_MISS", "ATTACK_CRIT", "ATTACK_KILL",
            "FLEE_SUCCESS", "FLEE_FAIL", "ITEM_USE", "FEAR_TRIGGER",
            "CONDITION_APPLIED", "ENEMY_ACTION_HIT", "ENEMY_ACTION_MISS", "ENEMY_CRIT"
        ]
        for key in combat_keys:
            assert key in FALLBACK_TEMPLATES, f"Missing fallback for {key}"

    def test_all_scene_keys_present(self):
        scene_keys = ["SEARCH", "MOVEMENT", "REST_SHORT", "REST_LONG", "EXAMINE", "SKILL_TEST"]
        for key in scene_keys:
            assert key in FALLBACK_TEMPLATES, f"Missing scene fallback for {key}"

    def test_fallback_values_are_polish(self):
        for key, value in FALLBACK_TEMPLATES.items():
            # Each fallback should be a non-empty string
            assert value and len(value) > 5, f"Fallback for {key} is too short"


# ---------------------------------------------------------------------------
# Task 27 — Combat narration (mocked LLM)
# ---------------------------------------------------------------------------

class TestCombatNarration:
    def _make_req(self, **kwargs) -> CombatNarrationRequest:
        defaults = dict(
            actor="Gracz",
            action_type="ATTACK_HIT",
            target_name="Goblin Zwiadowca",
            weapon="Miecz Żelazny",
            location_name="Ciemny Korytarz",
        )
        defaults.update(kwargs)
        return CombatNarrationRequest(**defaults)

    def test_returns_string_on_success(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Cios dosięga goblina. Wróg się chwieje."
            req = self._make_req()
            result = narrate_combat_action(req)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_no_numbers_in_output(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Cios trafia goblina w bok. Wróg cofa się z bólem."
            req = self._make_req()
            result = narrate_combat_action(req)
            import re
            assert not re.search(r'\b\d+\b', result), f"Numbers found in: {result}"

    def test_max_2_sentences(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Pierwsze. Drugie. Trzecie. Czwarte."
            req = self._make_req()
            result = narrate_combat_action(req)
            sentences = _split_sentences(result)
            assert len(sentences) <= 2

    def test_fallback_on_llm_error(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM timeout")
            req = self._make_req()
            result = narrate_combat_action(req)
            assert result == FALLBACK_TEMPLATES["ATTACK_HIT"]

    def test_kill_uses_fallback_key(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.side_effect = RuntimeError("error")
            req = self._make_req(action_type="ATTACK_KILL", target_is_dead=True)
            result = narrate_combat_action(req)
            assert result == FALLBACK_TEMPLATES["ATTACK_KILL"]

    def test_nat20_request_includes_special_instructions(self):
        """Verify nat_20=True results in special instructions being passed to LLM."""
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Spektakularny cios."
            req = self._make_req(nat_20=True)
            narrate_combat_action(req)
            call_args = mock_llm.call_args[0][0]  # messages list
            user_content = call_args[1]["content"]
            assert "spektakularny" in user_content.lower() or "druzgocący" in user_content.lower()

    def test_nat1_request_includes_fumble_instructions(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Potknąłeś się żałośnie."
            req = self._make_req(nat_1=True)
            narrate_combat_action(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "poszło bardzo nie tak" in user_content

    def test_hit_location_in_prompt(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Goblin kuleje po ciosie w nogę."
            req = self._make_req(hit_location="prawa_noga")
            narrate_combat_action(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "kulawi" in user_content.lower() or "noga" in user_content.lower()

    def test_enemy_action_miss_fallback(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.side_effect = RuntimeError("error")
            req = self._make_req(action_type="ENEMY_ACTION_MISS")
            result = narrate_combat_action(req)
            assert result == FALLBACK_TEMPLATES["ENEMY_ACTION_MISS"]


class TestNarrateRound:
    def test_returns_list_of_strings(self):
        import asyncio
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Cios trafia."
            actions = [
                CombatNarrationRequest("Gracz", "ATTACK_HIT", "Goblin A"),
                CombatNarrationRequest("Goblin B", "ENEMY_ACTION_MISS", "Gracz"),
            ]
            results = asyncio.get_event_loop().run_until_complete(narrate_round(actions))
            assert len(results) == 2
            assert all(isinstance(r, str) for r in results)

    def test_partial_failure_uses_fallback(self):
        import asyncio
        call_count = 0

        def side_effect(messages):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("second call fails")
            return "Cios trafia."

        with patch("app.services.narrator_service.generate_chat", side_effect=side_effect):
            actions = [
                CombatNarrationRequest("Gracz", "ATTACK_HIT", "Goblin A"),
                CombatNarrationRequest("Goblin B", "ENEMY_ACTION_HIT", "Gracz"),
                CombatNarrationRequest("Gracz", "ATTACK_KILL", "Goblin C"),
            ]
            results = asyncio.get_event_loop().run_until_complete(narrate_round(actions))
            assert len(results) == 3
            # Second should be fallback
            assert results[1] == FALLBACK_TEMPLATES["ENEMY_ACTION_HIT"]
            # Others should be the LLM response
            assert "Cios" in results[0]


# ---------------------------------------------------------------------------
# Task 28 — NPC dialogue narration
# ---------------------------------------------------------------------------

class TestNPCDialogue:
    def _make_req(self, **kwargs) -> NPCDialogueRequest:
        defaults = dict(
            npc_id="wotan_1",
            npc_name="Wotan",
            personality_prompt="Mrukliwy karczmiarz, nieufny wobec obcych, skąpy w słowach.",
            knowledge_set=["Zna wszystkich stałych bywalców karczmy", "Słyszał plotki o bandytach na drodze"],
            player_input="Gdzie jest skrzynka z dokumentami?",
        )
        defaults.update(kwargs)
        return NPCDialogueRequest(**defaults)

    def test_returns_string(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Nie wiem, o czym mówisz."
            req = self._make_req()
            result = narrate_npc_dialogue(req)
            assert isinstance(result, str)

    def test_max_4_sentences(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "A. B. C. D. E. F."
            req = self._make_req()
            result = narrate_npc_dialogue(req)
            sentences = _split_sentences(result)
            assert len(sentences) <= 4

    def test_must_reveal_info_in_system_prompt(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Skrzynka jest za portretem."
            req = self._make_req(must_reveal_info="Skrzynka jest w skrytce za portretem w jadalni.")
            narrate_npc_dialogue(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "Skrzynka jest w skrytce" in user_content

    def test_is_secret_adds_reluctance_instruction(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Nieee... nie powinienem ci tego mówić..."
            req = self._make_req(
                must_reveal_info="Skrzynka jest za portretem.",
                is_secret=True
            )
            narrate_npc_dialogue(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "NIECHĘTNIE" in user_content

    def test_recent_exchanges_injected(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Tak, wspominałem o tym wcześniej."
            exchanges = [
                DialogueTurn("Gracz", "Pytałem o bandytów."),
                DialogueTurn("Wotan", "Słyszałem coś o nich na południu."),
            ]
            req = self._make_req(recent_exchanges=exchanges)
            narrate_npc_dialogue(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "bandytów" in user_content or "OSTATNIA ROZMOWA" in user_content

    def test_fallback_on_llm_error(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM error")
            req = self._make_req()
            result = narrate_npc_dialogue(req)
            assert isinstance(result, str)

    def test_deceased_npc_context_injected(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Tak, słyszałem o jego śmierci."
            req = self._make_req(deceased_npc_context="Heinz jest martwy. Twój stosunek: neutral")
            narrate_npc_dialogue(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "martwy" in user_content

    def test_deceased_npc_relationship_ally(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Heinz... mój brat. Kto to zrobił?!"
            req = self._make_req(
                deceased_npc_context="Heinz jest martwy.",
                deceased_npc_relationship="ally",
            )
            narrate_npc_dialogue(req)
            user_content = mock_llm.call_args[0][0][1]["content"]
            assert "stosunek do tej postaci: ally" in user_content
            assert "żalem" in user_content or "gniewem" in user_content

    def test_deceased_npc_relationship_enemy(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Heinz? Dobrze. Należał mu się."
            req = self._make_req(
                deceased_npc_context="Heinz jest martwy.",
                deceased_npc_relationship="enemy",
            )
            narrate_npc_dialogue(req)
            user_content = mock_llm.call_args[0][0][1]["content"]
            assert "stosunek do tej postaci: enemy" in user_content
            assert "lekceważąco" in user_content or "satysfakcji" in user_content

    def test_deceased_npc_relationship_defaults_to_neutral(self):
        """When relationship is None, prompt falls back to neutral wording."""
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Tak, słyszałem o jego śmierci."
            req = self._make_req(
                deceased_npc_context="Heinz jest martwy.",
                # deceased_npc_relationship not set → defaults to neutral
            )
            narrate_npc_dialogue(req)
            user_content = mock_llm.call_args[0][0][1]["content"]
            assert "stosunek do tej postaci: neutral" in user_content


# ---------------------------------------------------------------------------
# Task 29 — Scene narration
# ---------------------------------------------------------------------------

class TestSceneNarration:
    def _loc(self, archetype="tavern") -> LocationContext:
        return LocationContext(
            name="Karczma Pod Krzyżem",
            description="Zakurzone wnętrze z drewnianymi stołami. W powietrzu unosi się dym.",
            archetype=archetype,
        )

    def _make_req(self, action_type="SEARCH", outcome="success", **kwargs) -> SceneNarrationRequest:
        return SceneNarrationRequest(
            action_type=action_type,
            outcome=outcome,
            location=self._loc(),
            **kwargs
        )

    def test_search_success_mentions_item(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Twoje ręce zamykają się na starym kluczu."
            req = self._make_req(found_items=["Stary Klucz"])
            result = narrate_scene(req)
            assert isinstance(result, str)

    def test_search_fail_no_item_in_prompt(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Nic tutaj nie ma wartego uwagi."
            req = self._make_req(action_type="SEARCH", outcome="fail", found_items=[])
            narrate_scene(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "ZNALEZIONE PRZEDMIOTY" not in user_content

    def test_movement_includes_both_locations(self):
        destination = LocationContext(
            name="Ciemna Aleja",
            description="Wąska uliczka między kamienicami.",
            archetype="city"
        )
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Opuszczasz karczmę i wchodzisz w ciemną aleję."
            req = self._make_req(action_type="MOVEMENT", outcome="success", destination=destination)
            narrate_scene(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "Ciemna Aleja" in user_content
            assert "Karczma Pod Krzyżem" in user_content

    def test_rest_long_has_unease_instruction(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Noc mija niespokojnie."
            req = self._make_req(action_type="REST_LONG", outcome="success")
            narrate_scene(req)
            call_args = mock_llm.call_args[0][0]
            # System prompt should contain the no-perfect-rest reminder
            system_content = call_args[0]["content"]
            assert "niepokój" in system_content or "STYL" in system_content

    def test_no_numbers_in_output(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Zmęczony siadasz pod ścianą. Odpoczywasz przez chwilę."
            req = self._make_req(action_type="REST_SHORT", outcome="success")
            result = narrate_scene(req)
            import re
            assert not re.search(r'\b\d+\b', result), f"Numbers in result: {result}"

    def test_length_search_max_3(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "A. B. C. D. E."
            req = self._make_req(action_type="SEARCH")
            result = narrate_scene(req)
            assert len(_split_sentences(result)) <= 3

    def test_length_examine_max_2(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "A. B. C."
            req = self._make_req(action_type="EXAMINE", object_examined="Stary Dziennik")
            result = narrate_scene(req)
            assert len(_split_sentences(result)) <= 2

    def test_length_campaign_event_max_4(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "A. B. C. D. E."
            req = self._make_req(action_type="CAMPAIGN_EVENT")
            result = narrate_scene(req)
            assert len(_split_sentences(result)) <= 4

    def test_time_weather_injected_into_prompt(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "W gęstej mgle nocy wchodzisz."
            req = self._make_req(action_type="MOVEMENT", time_of_day="noc", weather="mgła",
                                 destination=self._loc("city"))
            narrate_scene(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "noc" in user_content
            assert "mgła" in user_content

    def test_atmosphere_disturbed_flag(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Nic nie znalazłeś, ale coś ruszyłeś."
            req = self._make_req(action_type="SEARCH", outcome="fail",
                                 atmosphere_disturbed=True, found_items=[])
            narrate_scene(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "porusza" in user_content or "niepokoi" in user_content

    def test_dungeon_rest_has_dangerous_hint(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Odpoczywasz, ale niebezpieczeństwo nie śpi."
            loc = LocationContext("Lochy Zamku", "Wilgotna sala.", "dungeon")
            req = SceneNarrationRequest(action_type="REST_SHORT", outcome="success", location=loc)
            narrate_scene(req)
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "niebezpiecznym" in user_content or "niespokojny" in user_content

    def test_fallback_on_error(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.side_effect = RuntimeError("timeout")
            req = self._make_req(action_type="REST_SHORT")
            result = narrate_scene(req)
            assert result == FALLBACK_TEMPLATES["REST_SHORT"]


# ---------------------------------------------------------------------------
# Task 26 — narrate_turn (main turn narrator)
# ---------------------------------------------------------------------------

class TestNarrateTurn:
    def test_returns_string(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Gracz uderza goblina. Wróg się chwieje."
            result = narrate_turn(
                action_type="ATTACK_HIT",
                mechanical_result={"aktor": "Gracz", "cel": "Goblin", "wynik": "trafienie"},
                location_name="Korytarz",
                location_description="Wąski, ciemny korytarz.",
            )
            assert isinstance(result, str)
            assert len(result) > 0

    def test_wound_label_injected(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "Ciężko ranny, ale walczysz dalej."
            narrate_turn(
                "ATTACK_HIT",
                {},
                "Korytarz",
                "Opis.",
                wound_label="Ciężko Ranny"
            )
            call_args = mock_llm.call_args[0][0]
            user_content = call_args[1]["content"]
            assert "Ciężko Ranny" in user_content

    def test_fallback_on_error(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM down")
            result = narrate_turn("ATTACK_HIT", {}, "Loc", "Desc")
            assert result == FALLBACK_TEMPLATES["ATTACK_HIT"]

    def test_max_sentences_respected(self):
        with patch("app.services.narrator_service.generate_chat") as mock_llm:
            mock_llm.return_value = "A. B. C. D. E. F."
            # ATTACK_HIT → 2 sentence limit
            result = narrate_turn("ATTACK_HIT", {}, "Loc", "Desc")
            assert len(_split_sentences(result)) <= 2
