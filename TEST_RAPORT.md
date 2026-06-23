# Raport testów — issue in-review
Aktualizacja: 2026-06-23 | Zakres tej sesji: **PEŁNY skan label:review — wszystkie milestony (65 issue)**
Metoda: pytest na DEV (ai-gm-dev-backend-1) + grep realnych plików frontendu + HTTP integration na żywym frontend:80

## Dashboard
| Milestone | Łącznie | ✅ Zamknięte | ❌ Bug/Fail | ⏭ SKIP | 💬 Komentarz |
|---|---|---|---|---|---|
| Balans klas + czary maga (Faza B) | 13 | 13 | 0 | 0 | 0 |
| Multiplayer (Faza 5) | 25 | 24 | 1 (#801) | 0 | 0 |
| Admin Panel Mobile | 15 | 15 | 0 | 0 | 0 |
| Lochy kafelkowe (Faza L) | 2 | 1 (#741) | 1 (#719) | 0 | 0 |
| Głos/obrazy (Faza 6) | 3 | 2 | 0 | 0 | 1 (#593) |
| Frontend pasek akcji (Faza SF) | 2 | 0 | 1 (#861) | 1 (#635) | 0 |
| Bugi i poprawki (FIX) | 5 | 0 | 0 | 1 (#748) | 4 |
| **Łącznie** | **65** | **55** | **4** | **2** | **5** (10 otwartych) |

## Wynik pytest per grupa
| Grupa | Pliki | Wynik |
|---|---|---|
| Faza B | 12 | **122 passed** ✅ |
| MP G-tasks | 23 + 2 (G27/G28) | **218 passed / 1 failed** (#801) |
| Admin Mobile | 11 (+4 grep) | **66 passed** ✅ (po stagingu assetów) |
| Faza 6 + FIX/SF | 9 | **69 passed** ✅ |

> **Uwaga metodyczna:** mobile testy hardcodują ścieżki do kopii assetów (`tests/frontend_assets/`,
> `/tmp/forge_test/`, `_frontend_832/`) bez fixture stagingu — nie self-stagują. Frontend wkopiowany
> do kontenera backendu + staging assetów przed runem; HTTP testy (#831/#834/#838/#839/#846) biją
> w żywy `frontend:80`. Po runie wszystko sprzątnięte.

## ✅ Zamknięte (55)

**Faza B (13):** #598 #764 #765 #771 #773 #780 #820 #821 #822 #823 #858 #863 #864
> #820/#821/#823 NIE były tylko Księgą Zasad — kod gry istnieje (pytest GREEN).
> #858 rozwiązany: bandaż `heal_hp/self` w starterze wojownika; combat-item btn #859 zamknięty.

**Multiplayer (24):** #785 #786 #787 #788 #789 #790 #792 #793 #794 #795 #796 #797 #799 #800 #802 #803 #804 #805 #806 #807 #808 #809 #810 #811

**Admin Mobile (15):** #831 #832 #834 #835 #836 #837 #838 #839 #843 #844 #846 (pytest) · #833 #840 #841 #842 (grep klas: 44px touch / data-table--cards/scroll)

**Faza 6 (2):** #818 #919 (przełącznik LLM offline)

**Faza L (1):** #741 (D-pad drag — `_dpadDragInit`)

## ❌ / 💬 / ⏭ Otwarte (10)

| # | Milestone | Wynik | Powód |
|---|---|---|---|
| #801 | MP | ❌ FAIL | `test_concurrent_submits_no_locked_error`: `database is locked` przy 2 równoczesnych submitach (13/14 GREEN). WAL+busy_timeout włączone, ale `submit_action` nie respektuje timeout. Ticket FUNDAMENT — wymaga naprawy retry/busy_timeout. |
| #719 | Faza L | ❌ BUG | `dodge_roll` renderowany tylko dla czarów (`_dodgeOutcomeSpell` app.js:2585); modal walki wręcz nie pokazuje uniku wroga. pytest sprawdza tylko kontrakt backendu. |
| #861 | Faza SF | ❌ BUG | app.js nie renderuje `offhand`/`parry_bonus`. pytest sprawdza tylko meta-kontrakt (GREEN), nie render UI. |
| #593 | Faza 6 | 💬 | Backend GREEN (pytest, diagnostics 200), ale klient nie zapisuje subskrypcji ('nadal nie działa'). Wymaga debug w przeglądarce (SW/pushManager). |
| #635 | Faza SF | ⏭ SKIP | Karta hazardu SF6 niezaimplementowana w UI (brak sf6/gamble/Ryzykujesz w app.js). Backend gamble istnieje. |
| #748 | FIX | ⏭ SKIP | Voice service off na DEV — pełny test STT z .16 niemożliwy. pytest fallback GREEN. |
| #653 | FIX | 💬 | pytest GREEN; wizualizacja rzutu wymaga Scholara z niskim HP w przeglądarce. |
| #750 | FIX | 💬 | pytest GREEN; pełne potwierdzenie zależy od niedeterministycznej narracji LLM. |
| #826 | FIX | 💬 | pytest 19/19 GREEN; 3 kryteria 'feel'/Sandbox czekają na ocenę Piotra. |
| #866 | FIX | 💬 | pytest GREEN; finalne potwierdzenie wymaga prawdziwego incognito (rejestracja z linku). |

## Nowe bugi znalezione podczas testów
*(brak nowych — #801 to istniejący ticket którego własny test pada)*

---
*Legenda: ✅ zamknięte · ❌ bug/fail · ⏭ skip (niezaimplementowane/środowisko) · 💬 komentarz (blokada browser/Piotr)*
*Metoda zamknięcia: tylko po realnym teście (pytest GREEN / grep zweryfikowany), nie na podstawie samego komentarza.*
