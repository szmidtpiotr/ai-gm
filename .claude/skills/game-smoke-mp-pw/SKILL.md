---
name: game-smoke-mp-pw
description: >-
  Playwright-driven full-mode smoke playtest of AI-GM MULTIPLAYER: same party scenario as
  /game-smoke-mp (lobby → join → shared rounds → combat → chat → absence) but played through the
  REAL player UI via the Playwright MCP browser instead of the API. Verifies MP UI-only mechanics
  the API path cannot see — the lobby screen with member slots + host-kick ✕, the MOJE LOBBY /
  AKTYWNE GRY list sections with delete/leave buttons, the party-chat panel (toggle + public +
  whisper), the spectator "Widz" composer, shared narration landing in every player's chat, MP
  combat banner zones + initiative chips + downed state — with an inline-screenshot report +
  P0/P1/P2 defect issues. Use when: the user types /game-smoke-mp-pw 2|3, or asks "czy multiplayer
  jest grywalny end-to-end w prawdziwym UI". For the faster API-only variant use /game-smoke-mp.
  For testing ONE specific issue use /playwright-test-report.
---

# game-smoke-mp-pw — obchód trybu multiplayer przez prawdziwe UI (Playwright)

Bliźniak `/game-smoke-mp`, ale grany **przez przeglądarkę** (Playwright MCP, `mcp__playwright__*`),
nie przez API. Cel ten sam: **„czy w multiplayer da się grać drużyną?"** — z naciskiem na to, co
każdy gracz NAPRAWDĘ widzi i klika. Werdykt bez zagranych rund w UI jest nieważny.

Browser na `.19` uderza wprost w `https://aigm-dev.studio-colorbox.com/`. Bez docker test-agenta.

## ⚠ Ograniczenie: jeden browser = jeden zalogowany gracz

Playwright MCP ma **jeden kontekst** (wspólny localStorage/cookies — taby też). Nie da się trzymać
N zalogowanych graczy naraz jak w spec'ach `browser.newContext()`. Strategia (analogicznie do
kontraktu pw „API jako nudge setupowy, efekt z UI"):

- **API harness steruje pozostałymi graczami**, browser gra **graczem fokusowym** (P1) + widzem.
- **POV-switch** dla sprawdzenia, co widzi inny gracz: podmień token w localStorage i przeładuj —
  szybciej niż pełny re-login:
  ```
  mcp__playwright__browser_evaluate →
    () => { localStorage.setItem('token', '<TOKEN_Pn>'); localStorage.setItem('user', '<USER_JSON_Pn>'); location.reload(); }
  ```
  Tokeny graczy bierzesz z `POST /api/admin/dev-login` lub z setupu. Runda `collecting` czeka aż
  wszyscy oddadzą — **kolejność submitów nie ma znaczenia**, więc „symultaniczność" robisz sekwencyjnie.

## Po co osobny wariant PW (vs API /game-smoke-mp)

`/game-smoke-mp` gra przez skrypty (`play_mp_round.py`, ścieżka API) — NIE dotyka warstwy UI. Te
checkpointy są **UI-only** i tylko ten wariant je weryfikuje:
- **Ekran lobby:** sloty członków (`.lf-party-slot`), host-kick ✕ (`.lf-party-slot__kick`), Start
- **Lista kampanii:** sekcje **MOJE LOBBY** / **AKTYWNE GRY WIELOOSOBOWE** + przyciski **🗑/Opuść** (#954)
- **Sync rundy wizualnie:** akcja gracza → wspólna narracja GM ląduje w `#chat-messages` u WSZYSTKICH
- **Panel czatu party:** toggle (`.mp-chat-panel__toggle`), wiadomość publiczna, szept
- **Kompozytor widza:** placeholder „Widz…" (`#chat-input` read-only dla spectatora)
- **Baner walki MP:** kolumny DYSTANS/ZWARCIE, chipy inicjatywy 🏹/⚔ z wieloma graczami, powalenie (nie śmierć)
- **Stan oczekiwania:** „czekamy na pozostałych graczy" gdy część drużyny nie oddała akcji

## ⛔ KONTRAKT

- **Tylko realne akcje w UI** przez Playwright MCP dla gracza fokusowego. API (`http://192.168.1.61:8100`)
  i skrypty `game-smoke-mp/scripts/` wolno użyć do *setupu lobby* i *sterowania pozostałymi graczami*,
  ale każdy testowany efekt UI MUSI być zrzucony z ekranu.
- Konta testowe **tester_mp1..N** (hasło `mp_tester_2026`) + `tester_mp_spec`. Nigdy `piotrszmidt`
  (`user_id=1013`) ani bohatera Mizel (`999420`).
- Lobby/kampanii i postaci po teście NIE usuwać (chyba że test celowo testuje usuwanie — CP del).
- SQL wyłącznie do ODCZYTU dowodów, przez SSH+docker exec (**nigdy sshfs** — staleness WAL).
- **Każdy screenshot pokazuje DOWÓD** testowanej rzeczy (po akcji wyzwalającej), nie „gra otwarta".
- Screenshoty → `temp-img/<RUN>/NN-label.png`, NIGDY `/tmp/`. Zawsze `Read` PNG inline przed opisem.
- Limit: ~24 kroki na run (MP droższe — N graczy × narracja 2-fazowa). Po limicie: raport, nawet
  niekompletny — zaznacz czego nie osiągnięto.
- Zamknij browser na końcu (`mcp__playwright__browser_close`).

## Wywołanie

```
/game-smoke-mp-pw 2     # 2 graczy
/game-smoke-mp-pw 3     # 3 graczy (+ opcjonalnie widz: dodaj słowo "widz")
```

## Krok 1 — Setup graczy + lobby (skrypty API)

Reużyj infrastruktury `/game-smoke-mp` (setup przez skrypty, GRA przez UI):

```bash
cd /home/claude/projects/DEV_AIGM/.claude/skills/game-smoke-mp/scripts
python3 setup_mp_users.py --count N [--spectator]   # tester_mp1..N (+spec) — idempotentne; drukuje user_id/hero_id
python3 setup_mp_lobby.py --count N --no-start [--spectator]   # lobby zbudowane, zaproszeni, hero zaakceptowane, ALE NIE wystartowane
```

`--no-start` zostawia **otwarte lobby** — konieczne do CP1/CP2 (ekran lobby, host-kick) i startu z UI.
`setup_mp_lobby.py` drukuje JSON: `campaign_id` (CID) + `members` (`[{username,user_id,hero_id,role}]`).
Tokeny do POV-switch dobierz osobno: `POST /api/admin/dev-login` per gracz, albo użyj `?user_id=N`
w `browser_evaluate`-owych fetchach. Zapisz CID + members.

Utwórz katalog runu:
```bash
RUN="$(date +%Y%m%d_%H%M%S)_smoke-mp-pw-${N}p"
mkdir -p /home/claude/projects/DEV_AIGM/temp-img/$RUN
```

## Krok 2 — Otwórz browser + zaloguj P1 (Playwright MCP)

```
mcp__playwright__browser_navigate  → https://aigm-dev.studio-colorbox.com/
mcp__playwright__browser_snapshot
mcp__playwright__browser_type   #login-username = "tester_mp1"
mcp__playwright__browser_type   #login-password = "mp_tester_2026"
mcp__playwright__browser_click  #login-form button
mcp__playwright__browser_wait_for ("Moi Bohaterowie" / lista kampanii)
```

Selektory: `#login-username`, `#login-password`, `#login-form button`. Świeże refy: `browser_snapshot`.
Stan którego UI nie pokazuje wprost: `browser_evaluate`.

## Krok 3 — Scenariusz (checkpointy = /game-smoke-mp + warstwa UI)

Po CP1/CP2 wystartuj grę **z UI** (host klika Start w lobby). Potem graj rundami.

Wzorzec rundy: P1 oddaje akcję w UI (composer → wyślij) → pozostali gracze przez API, gdzie
`--members-json` zawiera **tylko P2..N** (subset z setupu, BEZ P1 — P1 już oddał w UI):
```bash
python3 play_mp_round.py --campaign CID \
  --members-json '[{"user_id":<P2>,"hero_id":<h2>,"role":"player"}, ...]'   # bez P1
```
→ runda domyka się → wspólna narracja. Jeśli timer nie zamyka — `python3 mp_sweep.py --campaign CID`.
Każdy CP = zrzut PO akcji wyzwalającej + `Read` PNG + dowód.

| # | Checkpoint | Mechanika (G) | Dowód UI (screenshot) + opcjonalnie SQL |
|---|---|---|---|
| 1 | **Ekran lobby**: sloty N graczy, oznaczenie Host, status „dołączył"/„zaproszony" | base | zrzut `#lobby-members-list`; N × `.lf-party-slot`; `campaign_members` |
| 2 | **Host-kick ✕** widoczny przy nie-hostach (jako P1=host); klik → slot znika | G3/G13 #787/#799 | zrzut ✕ + zrzut po kicku; member `status='kicked'` |
| 3 | *(jeśli widz)* widz dołącza bez bohatera; w grze kompozytor = placeholder „Widz…" | G19 #800 | zrzut composera widza; `role='spectator'`, `character_id=NULL` |
| 4 | **Start gry** (host) → wszyscy wchodzą w grę; wspólna narracja otwarcia w `#chat-messages` | base | zrzut narracji otwarcia; runda 1 istnieje |
| 5 | **Lista MP**: po wyjściu do listy — sekcje MOJE LOBBY / AKTYWNE GRY z kartą tej gry + przyciski 🗑/Opuść (#954) | #954 | zrzut sekcji z przyciskiem (host=🗑, nie-host=Opuść) |
| 6 | **Sync rundy**: P1 wysyła akcję → „czekamy na graczy" → po oddaniu reszty (API) wspólna narracja u P1 | G30 #801 | zrzut stanu oczekiwania + zrzut narracji po domknięciu; runda `done` |
| 7 | **Sync u innego gracza (POV-switch)**: podmień token na P2, reload → ta SAMA narracja w czacie P2 | G30 | zrzut czatu P2 z identyczną narracją rundy |
| 8 | **Prywatne notatki per gracz**: narracja P1 pokazuje notatki/rzuty P1, nie P2 (porównaj POV) | G8 #792 | zrzut sekcji prywatnej P1 vs P2 — różne |
| 9 | **Panel czatu party**: toggle (`.mp-chat-panel__toggle`) → P1 pisze publicznie → POV-switch P2 widzi to samo | G19 #800 | zrzut czatu u P1 i u P2 z tą samą wiadomością |
| 10 | **Walka MP — baner**: kolumny DYSTANS/ZWARCIE, chipy inicjatywy 🏹/⚔ z graczami + wrogami | G7 #791 | zrzut banera z wieloma combatantami; `combatants[]` |
| 11 | **Powalenie, nie śmierć**: gracz HP 0 → „nieprzytomny" w UI (nie „martwy"); da się ocucić | G17 #794 | zrzut stanu powalenia; stan = unconscious |
| 12 | **Szept prywatny**: P1 szepcze do P2 → P2 (POV-switch) widzi, P3 NIE; treść NIE w promptcie LLM | G19/#950 | zrzut czatu P2 z szeptem + zrzut P3 bez; SQL prompt rundy bez treści szeptu |
| 13 | *(opcjonalnie)* **Usuwanie kampanii MP** (#954): host klika 🗑 na karcie → potwierdzenie → znika z listy | #954 | zrzut przed/po; `DELETE /campaigns/{id}` skutkuje brakiem na liście |
| 14 | Spójność: narracja NIE twierdzi nic sprzecznego ze stanem UI/innego gracza | G28 | przegląd zrzutów; każda sprzeczność = defekt |

Minimum zrzutów kluczowych: CP1 (lobby z N), CP6+CP7 (sync u dwóch graczy), CP9 (czat party), CP10 (baner walki).

## Krok 4 — Defekty (issue od razu, przed dalszą grą)

Każde ❌ = issue (szablon #18):

```bash
gh issue create --repo szmidtpiotr/ai-gm --title "[BUG] SMOKE-MP-PW — <opis>" \
  --label "bug,smoke-defect,needs-testing" --body "<tryb mp-N, runda, oczekiwane vs faktyczne, repro UI, screenshot>"
```

Priorytety: **P0** = drużyna nie posuwa rundy w UI / blokuje grę · **P1** = psuje doświadczenie
(brak synchronizacji u gracza, **wyciek prywatności szeptu**, brak banera/czatu/kicka, sprzeczność
narracja↔stan) · **P2** = kosmetyka.

## Krok 5 — Upload zrzutów na GitHub

```bash
TAG=$(gh release list --repo szmidtpiotr/ai-gm --limit 1 --json tagName --jq '.[0].tagName')
for f in /home/claude/projects/DEV_AIGM/temp-img/$RUN/*.png; do
  gh release upload "$TAG" "$f" --repo szmidtpiotr/ai-gm --clobber
done
```
Trzymaj mapę label→URL w kolejności zrzutów.

## Krok 6 — Raport (inline screenshoty, prosty polski)

Komentarz do issue trybu (#892 master MP) — **zdjęcia INLINE pod nagłówkiem każdego kroku**, nigdy
galeria na końcu:

```markdown
## 🎮 game-smoke-mp-pw <N graczy> — <data>
**Kampania:** id | **Gracze:** tester_mp1..N (+widz) | **Rund w UI:** N

### Werdykt: GRYWALNY / GRYWALNY Z ZASTRZEŻENIAMI / NIEGRYWALNY
(NIEGRYWALNY jeśli ≥1 P0; Z ZASTRZEŻENIAMI jeśli ≥1 P1)

### Przebieg krok po kroku
#### 1. <co testowano>
![<alt: co widać>](URL_01)
- **Co widać:** <konkret z ekranu, z którego POV>
- **Werdykt:** ✅ DZIAŁA / ❌ PROBLEM → #issue

(…wszystkie checkpointy w kolejności, każdy ze zrzutem inline…)

### Podsumowanie — co poprawić (🔴→🟡, linki do issue)
### Defekty: P0: n · P1: n · P2: n
```

## Krok 7 — notes.md + commit

Zaktualizuj notes.md (status smoke-MP-PW + link do raportu). Commit na `develop` przez
`sudo -u piotrszmidt git` na `.61`, referuj numery issue. Push. Krótki komunikat do usera:
werdykt, liczba problemów, link.

## Gotchas

- **POV-switch tokenem** jest szybszy niż re-login, ale po `location.reload()` poczekaj
  (`browser_wait_for`) aż UI wstanie na właściwym koncie — sprawdź nazwę gracza w HUD zanim zrzucisz.
- Endpoint submit zwraca **HTTP 200 nawet przy odmowie** (`round_closed`) — gdy sterujesz resztą przez
  `play_mp_round.py`, sprawdzaj pole `blocked`, nie tylko kod HTTP.
- **Nie czekaj zegara** — zamykaj rundy `mp_sweep.py` (wstrzyknięty czas). Lobby ma timer=1 min jako bufor.
- Prywatne notatki/roll_facts są **per-token** — POV-switch jest jedynym sposobem zobaczyć je w UI z perspektywy danego gracza.
- **Prywatność szeptu (CP12) = bramka P1:** po szepcie przeszukaj zapisany prompt/kontekst rundy (SQL)
  pod kątem treści — każde trafienie = wyciek, niezależnie od tego co widać w czacie.
- **P0 #959 naprawiony** — po rundzie otwarcia pierwszy submit auto-otwiera kolejną `collecting`. Jeśli
  CP6+ blokuje na `round_closed` → regresja #959, P0.
- Rate limit TPM → 502: czekaj 60 s; `gpt-4.1-mini` w configu kampanii tnie koszt (N graczy mnoży tury).
- Nie wymuszaj checkpointów łamiąc fikcję — graj naturalnie; nieosiągnięty organicznie po limicie → N/D.
- Zamknij browser na końcu.
