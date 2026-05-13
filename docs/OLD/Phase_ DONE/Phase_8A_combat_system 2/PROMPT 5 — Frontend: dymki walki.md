Jesteś AI pomagającym w projekcie ai-gm (Vanilla JS + HTML, port 3001).

⚠️ ZANIM cokolwiek zaimplementujesz — STOP i odpowiedz na pytania:
1. Jak aktualnie renderowane są wiadomości w chacie? (przeczytaj ui.js w całości)
   Czy używany jest innerHTML, createElement, template literals?
2. Czy plik combat_bubbles.js już istnieje? Jeśli tak — jaka jest jego zawartość?
3. Czy combat_panel.js już obsługuje odpowiedź z backendu walki?
   Jeśli tak — co dokładnie robi po otrzymaniu wyniku ataku?
4. Jak wygląda struktura HTML chat containera? (id, klasy)
   Czy dodanie nowych elementów może zepsuć istniejący layout lub CSS?
5. Czy są jakieś globalne zmienne JS których nie mogę nadpisać?
6. Czy index.html ładuje skrypty w określonej kolejności która ma znaczenie?

Jeśli znajdziesz JAKIKOLWIEK bloker lub ryzyko złamania UI — opisz go i czekaj.
Jeśli wszystko bezpieczne — napisz "✅ Brak blokerów, kontynuuję" i dopiero wtedy działaj.

---

Zadanie: Dodaj wizualizację wyników walki jako dymki czatu.

Przeczytaj KONIECZNIE:
- frontend/js/ui.js (cały plik)
- frontend/js/api.js
- frontend/js/combat_panel.js
- frontend/index.html

Utwórz frontend/js/combat_bubbles.js z funkcją renderCombatBubble(result, attackerName, targetName):

JEŚLI hit === false:
  [LEWO] 🎲 {attackerName} Trafienie: {attack_total}
  [PRAWO] {targetName} Unik: {dodge_total} ✅  LUB  💀 Krytyczna porażka!

JEŚLI hit === true:
  [LEWO] 🎲 {attackerName} Trafienie: {attack_total}{⚡KRYT} | {weapon_die}({damage_roll})+bonus={damage_total}
  [PRAWO] {targetName} Unik: {dodge_total} ❌ | Obrona: {defense_total} | −{final_damage} HP ({target_hp_after}){💀ZABITY}

CSS (dopasuj do istniejącego stylu projektu — NIE narzucaj własnych kolorów jeśli
jest już zdefiniowany motyw kolorystyczny):
.combat-turn — flex column, gap 4px
.bubble-left — align flex-start, rounded
.bubble-right — align flex-end, rounded

Podłącz do combat_panel.js lub ui.js po odebraniu odpowiedzi z /api/combat/attack.
Dodaj <script> do index.html jeśli potrzeba — TYLKO NA KOŃCU listy skryptów.
NIE zmieniaj logiki GM chat. Pokaż wszystkie zmiany przed zapisem.