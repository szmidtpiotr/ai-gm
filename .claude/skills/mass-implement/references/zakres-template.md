<!--
  ZAKRES block template. Place ONE such block at the top of each faza/list section
  in the task doc (notes.md / fix_list.md). The orchestrator extracts the block
  between the MASS-ZAKRES markers and injects it into {ZAKRES} of the child prompt.
  This replaces the per-faza prompt_*.md files — the varying ~20% lives here, next
  to the tasks it governs.
-->
<!-- MASS-ZAKRES:START -->
**Źródło opisu zadania:** [np. „issue GitHub #<N>" lub „game_mechanics.md → CZĘŚĆ XX (Cel / Dla agenta / Weryfikacja)"]

**Mapowanie id:** [np. „FIX<N> = issue #<N>" lub „LNN = zadanie LNN w CZĘŚCI AJ"]

**Decyzje / zakres:** [kluczowe decyzje właściciela z datą; co JEST w zakresie]

**Poza zakresem (NIE implementuj):** [lista]

**Wyjątki pipeline:** [np. „L14–L17 = kontent/batch bez TDD; L13c/L19 = playtest przez /game-smoke-dungeon, bez issue"]

**Twarde zależności:** [np. „#595 musi być gotowe; jeśli nie → GATE"]
<!-- MASS-ZAKRES:END -->
