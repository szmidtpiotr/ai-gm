Jesteś programistą Vanilla JS/HTML pracującym nad projektem ai-gm.
Repozytorium: github.com/szmidtpiotr/ai-gm
Branch: phase-8d-location-integrity
Frontend: frontend/admin.html + frontend/admin_panel/
Port frontend: 3001, Port backend: 8000

## ZANIM ZACZNIESZ IMPLEMENTOWAĆ

Przejrzyj istniejący kod i odpowiedz na poniższe pytania.
Jeśli którakolwiek odpowiedź wskazuje na problem — powiedz mi o tym ZANIM napiszesz
jakikolwiek kod:

1. Jak działa system zakładek Game Design? (data-tab? klasy CSS? osobne pliki JS?)
   Pokaż mi jak dodana jest zakładka np. "Enemies" — żebym mógł dodać "Locations"
   dokładnie w ten sam sposób.
2. Jak wyglądają istniejące modale CRUD (np. dla Enemies lub Items)?
   Chcę użyć tego samego wzorca.
3. Czy jest globalny plik CSS/styl który powinienem znać?
4. Jak wygląda wywołanie API z frontendu? Czy jest helper fetchAPI() lub podobny?
5. Jak sprawdzana jest rola admin w UI? (żebym wiedział jak ukryć toggle flag dla gracza)
6. Czy istnieje już widok sesji gdzie mogę dodać sekcję flag? Jaki plik?
7. Czy dodanie nowej zakładki może cokolwiek złamać w istniejących zakładkach?

Jeśli nie widzisz blokerów — zaimplementuj poniższe elementy UI.

---

## Zadanie 8D-15: Zakładka "Locations" w Game Design

Dodaj zakładkę "Locations" do paska Game Design (zachowaj istniejący styl).

Widok główny:
- Drzewo lokalizacji: makro + rozwijane sub (accordion lub indent)
- Kolumny: Nazwa | Typ (badge MAKRO/SUB) | Rodzic | [Edytuj] [Usuń]
- Przycisk "+ Dodaj Lokalizację" → modal
- Wyszukiwarka po label

Form modal (dodaj/edytuj):
- label (text, wymagane)
- key (auto-slug z label, edytowalny)
- location_type (select: Makro / Sub)
- parent_id (select, widoczny tylko gdy type=Sub — lista makro lokalizacji)
- description (textarea)
- rules (textarea, walidacja JSON gdy zaczyna się od "{")

---

## Zadanie 8D-16: enemy_keys w formie lokalizacji

W formie edycji dodaj sekcję "Możliwi wrogowie":
- Lista enemy_keys jako tagi: [wilk ×] [bandyta ×]
- Dropdown z listą wrogów (GET /api/admin/enemies) do dodawania
- Sekcja NPC Keys wyszarzona z info: "Dostępne w Phase 9"

---

## Zadanie 8D-17: Edytor rules

Pole rules w formie lokalizacji:
- Textarea monospace
- Walidacja live: jeśli zaczyna od "{" → parsuj JSON → pokaż błąd jeśli invalid
- Hint pod textarea z przykładami (JSON i free text)

---

## Zadanie 8D-18: Toggle flag w panelu sesji (tylko admin)

W widoku sesji dodaj sekcję "Location Integrity Flags" (tylko dla roli admin):

┌─────────────────────────────────────────┐
│ Location Integrity      [toggle] (global: ON)  │
│ Parser JSON (Opcja A)   [toggle] (global: ON)  │
│ Fallback Parser (B)     [toggle] (global: ON)  │
│                [Resetuj do globalnych] [Zapisz] │
└─────────────────────────────────────────┘

- Toggle pokazuje wartość EFEKTYWNĄ (po merge z global)
- W nawiasie: wartość globalnego defaultu (informacyjnie, readonly)
- Resetuj → DELETE /api/admin/session/{id}/flags/{key} dla każdej flagi
- Zapisz → PATCH /api/admin/session/{id}/flags

---

## Zadanie 8D-19: Log viewer blokad

W panelu sesji dodaj zakładkę/sekcję "Log blokad lokalizacji":

Tabela: Data/czas | Postać | Próba ruchu | Z lokalizacji | Powód blokady
- Badge "TELEPORTACJA" gdy różne makro-lokalizacje
- Paginacja po 20 rekordów
- Filtr date range (od/do)
- Puste: "Brak zablokowanych prób ✅"

---

## Wymagania końcowe
- Vanilla JS, bez frameworków
- Spójny styl z istniejącymi zakładkami
- Loading state + error toast dla błędów API