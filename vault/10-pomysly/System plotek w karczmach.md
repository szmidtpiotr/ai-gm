---
typ: pomysl
status: szkic
zrodlo: "#1190"
---

# System plotek w karczmach

## Co gracz dostaje
W karczmie gracz może „nadstawić ucha" albo postawić komuś kolejkę (koszt w złocie) i dostaje plotkę — czasem prawdziwy trop do lochu, kontraktu, skarbu czy nadchodzącego wydarzenia, a czasem fałszywkę lub przekręconą wieść. Świat celowo nie jest wiarygodny w 100%.

## Jak to działa
- Część plotek jest **prawdziwa** — hook do lochu, kontraktu z tablicy zleceń, skrytego skarbu na konkretnym heksie, nadchodzącego wydarzenia regionalnego; część **fałszywa lub przekręcona**.
- Test WIS lub CHA decyduje, czy gracz wyczuje, że coś śmierdzi („plotka brzmi podejrzanie") — przez istniejący `skill_router`.
- Plotki zapisują się w dzienniku jako **„niepotwierdzone"** i zmieniają status po weryfikacji w grze (potwierdzona / fałszywa).
- Technicznie: tabela `campaign_rumors` (region, tekst, flaga prawdy, źródło generated/manual, cel np. hex/kontrakt/loch, status). Plotki generuje LLM z puli faktów o świecie (heksy, lokacje, NPC, aktywne kontrakty/eventy) + celowo wstrzykniętych fałszywek. Akcja „nadstaw ucha" rozpoznawana w intent-routingu tury (fraza kluczowa → akcja karczemna, jak gambling).

## Zarządzanie (admin)
- Panel Świat → zakładka „Plotki": lista krążących plotek per region, oznaczenie prawda/fałsz, przycisk „dodaj ręcznie".
- Ręczna plotka = najlepsze narzędzie do delikatnego kierowania gracza bez łamania immersji (zamiast deus-ex-machina w narracji).

## Dlaczego pasuje do gry
Tani sposób na „żywy świat" + naturalny kanał dystrybucji contentu (tablica zleceń, lochy, wydarzenia). Wykorzystuje istniejący system testów umiejętności i intent-routing w pipeline tury.

## Liczby startowe
- Proporcja prawda/fałsz: **60/40**
- DC testu wyczucia fałszu: **Medium 12**
- Koszt postawienia kolejki — wartość startowa.

## Zależności i powiązania
- Brak twardych zależności.
- Synergia: [[Tablica zleceń — bounty board]] i [[Wydarzenia regionalne]] jako źródła prawdziwych plotek; mapy skarbów (#1196).
- Plotki to główny surowiec dla [[Kurier Kresowy — gazeta świata]] (w tym fałszywe!).
- [[Nemezis — wróg, który pamięta]] podsyła plotki („podobno ktoś o ciebie wypytywał…"), a „dziwne" [[Kapliczki przydrożne i błogosławieństwa]] mogą generować hooki plotkowe.
- Gołębnik w [[Dom bohatera — kwatera w osadzie]] dostarcza plotki do domu.

## Out of scope
- Plotki rozchodzące się między osadami z czasem (propagacja) — v2.
- Plotki o czynach gracza (feed z Kroniki Bohatera) — v2, fajne rozszerzenie.

---
Źródło: https://github.com/szmidtpiotr/ai-gm/issues/1190
