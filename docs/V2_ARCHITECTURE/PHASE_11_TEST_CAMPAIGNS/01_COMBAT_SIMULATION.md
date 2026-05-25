# AI-GM — Lista Błędów i Plan Napraw

**Źródło:** Test AI (Perplexity jako gracz), 29 tur  
**Kampania:** "Przebudzenie w Mgle" (id=1099)  
**Bohater:** Eldric, Łotr Poziom 1, HP 11/11  
**Data:** 2026-05-25  
**Repo:** `szmidtpiotr/ai-gm`  
**Faza:** Phase 8D

---

## Krótko

Zagrano 29 tur z botem-graczem. Narracja MG jest dobra, ale znaleziono 8 błędów. Trzy z nich są poważne i trzeba je naprawić jako pierwsze.

**Ocena teraz: 6.8/10**  
**Po naprawach: ~8.5/10**

---

## Błędy

### BUG-01 — Przedmioty się duplikują kiedy oddajesz je NPC

**Priorytet:** 🔴 KRYTYCZNY

**Co się dzieje:** Gracz oddał `Czarną Księgę Eldrana` NPC-owi (Eldranowi). MG opisał to w narracji. Ale w plecaku gracz nadal miał księgę — i pojawiła się druga kopia.

**Ekwipunek po oddaniu (źle):**
```
Medalion Eldrana x1
Czarna Księga Eldrana x1   ← powinno zniknąć
Czarna Księga Eldrana x1   ← duplikat
Sakiewka Eldrana x1
```

**Dlaczego:** MG tylko opisuje oddanie. Backend nie kasuje przedmiotu z bazy. Nie ma żadnego sygnału "usuń item".

**Gdzie szukać:**
- `backend/app/api/turns.py`
- logika `grant_item`
- `backend/prompts/system_prompt.txt`

**Pomysł na fix:** MG powinien wysyłać sygnał `REMOVE_ITEM` kiedy gracz oddaje rzecz. Albo backend wykrywa słowa jak "oddaję", "kładę", "przekazuję".

---

### BUG-02 — Zegar gry stoi w miejscu

**Priorytet:** 🔴 WYSOKI

**Co się dzieje:** Czas pokazywał **"Dzień 1, 09:00"** przez wszystkie 29 tur. Nieważne czy gracz szedł przez las, rozmawiał, czy zwiedzał ruiny — zegar nie ruszał.

**Jak powinno być:** Każda tura to kilkanaście minut. Podróże to godziny.

**Dlaczego:** Pole `ingame_hours` w `session_flags` istnieje i działa — ale rusza tylko przy odpoczynku, podróży i walce. Zwykła tura narracyjna nie dodaje czasu.

**Gdzie szukać:**
- `backend/app/services/clock_service.py`
- `backend/app/api/turns.py`

**Pomysł na fix:** Po każdej turze automatycznie dodać czas:
- +15–30 min dla tury narracyjnej
- +5 min dla walki
- +60 min dla podróży

MG może też wysyłać `TIME_ADVANCE: X` w odpowiedzi.

---

### BUG-03 — NPC nie są zapamiętywani

**Priorytet:** 🔴 WYSOKI

**Co się dzieje:** Po wielu rozmowach z **Martą** (karczmarka) i **Eldranem** (mag) pole `Znani NPC` w kampanii wciąż pokazuje **"brak"**.

**Problem:** MG nie ma listy poznanych NPC w kolejnych turach. Może ich "zapomnieć" albo opisać niespójnie.

**Stan w kodzie:** Tabela `npcs` istnieje (katalog wszystkich NPC), ale **nie ma tabeli "spotkanych" NPC** per kampania.

**Gdzie szukać:**
- migracje DB w `backend/app/migrations_admin.py`
- `backend/app/api/turns.py`
- `backend/prompts/system_prompt.txt`

**Pomysł na fix:** MG wysyła sygnał przy pierwszym spotkaniu:
```json
{
  "event": "NPC_MET",
  "name": "Marta",
  "role": "karczmarka",
  "location": "Pod Trzema Krukami"
}
```
Backend zapisuje to do nowej tabeli powiązanej z kampanią.

---

### BUG-04 — Plan MG (Akt/Scena/Cel) zawsze pusty

**Priorytet:** 🟡 ŚREDNI

**Co się dzieje:** Pola `Akt`, `Scena`, `Cel sceny` pokazują **N/D** przez całą sesję. Mimo że AI po ~16 turach robi sensowne podsumowanie.

**Stan w kodzie:** `campaigns.gm_plan_json` istnieje i ma dobrą strukturę (akty, sceny, cele), ale jest tworzony **tylko raz** przy starcie kampanii. Nie aktualizuje się w trakcie gry.

**Gdzie szukać:**
- `backend/app/services/gm_plan_generation_service.py`
- `backend/app/services/context_injector.py`

**Pomysł na fix:** Dwa sposoby:
- (a) MG wysyła `{"gm_plan_update": {"act": "...", "scene": "...", "goal": "..."}}` i backend zapisuje
- (b) Backend parsuje podsumowanie AI i wyciąga z niego pola Akt/Scena

---

### BUG-05 — Opisy nieudanych rzutów są nudne

**Priorytet:** 🟡 ŚREDNI

**Co się dzieje:** Odpowiedzi MG na porażki są prawie identyczne:

> *"Tajemnica pozostaje ukryta, wymykając się twojej dociekliwości..."*  
> *"Twoje słowa rozbiły się o mur determinacji."*

Porażka nie pcha fabuły do przodu — tylko ją zatrzymuje.

**Gdzie szukać:**
- `backend/prompts/system_prompt.txt` — sekcja o porażkach

**Pomysł na fix:** Dodać do system prompt zasadę: przy porażce MG **musi** dorzucić konkretną konsekwencję:
- hałas przyciąga wroga
- traci się czas (+30 min)
- NPC daje błędną informację
- zmęczenie / debuff
- ktoś niepowołany cię zauważa

---

### BUG-06 — XP rośnie za wolno

**Priorytet:** 🟡 ŚREDNI

**Co się dzieje:** 9 XP po 29 turach. Gracz: eksplorował las i ruiny, gadał z NPC, zrobił misję, zdobył ważny przedmiot, uciekł przed potworem. Brak awansu poziomu, brak nagrody.

**Stan w kodzie:** XP daje się tylko za odpoczynek, wskrzeszenie i admin-grant. **Brak XP za walkę** i brak XP za akcje narracyjne.

**Pomysł na fix:** Dodać XP za eventy:

| Event | XP |
|---|---|
| Krok misji ukończony | 25 |
| Pierwsze spotkanie NPC | 5 |
| Nowa lokacja | 10 |
| Zdobycie ważnego przedmiotu | 15 |
| Ucieczka ze spotkania | 5 |

---

### BUG-07 — Surowy błąd `LOCATION_BLOCKED` widoczny dla gracza

**Priorytet:** 🟢 NISKI

**Co się dzieje:** W turze 22 w narracji pojawił się techniczny błąd:
```
[LOCATION_BLOCKED: move_target_unknown]
```

**Dlaczego:** Funkcja `_inject_location_blocked()` w `backend/app/api/turns.py` (linia ~142) wkleja surowy powód blokady **bezpośrednio do tekstu narracji**.

**Pomysł na fix:** Zamiast doklejać tag do narracji, MG powinien narracyjnie opisać że ruch jest niemożliwy. Pre-LLM hook już to robi — wystarczy włączyć go zamiast post-hooka.

---

### BUG-08 — Nowy bohater zaczyna z pustym plecakiem

**Priorytet:** 🟢 NISKI

**Co się dzieje:** Eldric (Łotr Poziom 1) zaczął kampanię **bez niczego** — bez broni, bez prowiantu. Wszedł do groźnych ruin bezbronny. MG nie ostrzegł.

**Dlaczego:** W tabeli `game_config_archetypes` istnieją tylko `warrior` i `scholar`. **Brak archetypu `rogue`/`łotr`**. Nieznane archetypy nie dostają starter kitu.

**Pomysł na fix — dwie opcje:**
- (a) Dodać archetyp `rogue` do bazy ze starter kitem (sztylet, 5 złota, pochodnia)
- (b) MG sugeruje organicznie zakup ekwipunku w pierwszej bezpiecznej scenie

---

## Plan Napraw

### Sprint 1 — Najpilniejsze

| Bug | Co zrobić |
|---|---|
| BUG-02 | Auto-dodawanie czasu po każdej turze |
| BUG-03 | Tabela "spotkanych NPC" + event `NPC_MET` |

### Sprint 2 — Ważne

| Bug | Co zrobić |
|---|---|
| BUG-01 | Event `REMOVE_ITEM` przy oddaniu przedmiotu |
| BUG-04 | Aktualizacja Akt/Scena per tura |

### Sprint 3 — Polish

| Bug | Co zrobić |
|---|---|
| BUG-05 | Konsekwencje porażek w system prompt |
| BUG-06 | XP za eventy narracyjne |
| BUG-07 | Ukryć `LOCATION_BLOCKED` przed graczem |
| BUG-08 | Starter kit dla łotra |

---

## Co Działa Dobrze

- Narracja MG — dobry polski, klimat ✅
- System rzutów — przejrzysty ✅
- Reakcje na kreatywne pomysły gracza ✅
- Zmiana lokacji ✅
- Dodawanie nowych przedmiotów ✅
- Podsumowanie AI MG po ~16 turach ✅
- `initialize_player_session` — stabilne ✅

---

## Oceny

| Co | Ocena |
|---|---|
| Narracja | 9/10 |
| Reaktywność MG | 8/10 |
| Fabuła | 8/10 |
| Rzuty | 7/10 |
| Zegar gry | 1/10 |
| Pamięć NPC | 3/10 |
| XP | 3/10 |
| Ekwipunek | 4/10 |
| **Razem** | **6.8/10** |

---

*Raport z sesji testowej AI-GM, 2026-05-25.*
