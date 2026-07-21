// #1190 — kropka „nowa plotka" na zakładce Kolekcje. Atlas jest głęboko (Karta →
// Kolekcje → Atlas → Plotki), więc bez sygnału gracz nie zauważy nowej wieści.
// Stan „przeczytane" trzymamy w localStorage per bohater (liczba plotek przy
// ostatnim otwarciu Atlasu). unread = aktualna liczba > zapamiętana.
import { useAtlas } from "@/hooks/useSheetData";
import { useAppStore } from "@/store/appStore";

const KEY = (cid: number) => `aigm_rumors_seen_${cid}`;

export function markRumorsSeen(characterId: number, count: number) {
  try {
    localStorage.setItem(KEY(characterId), String(count));
  } catch {
    /* localStorage niedostępny — trudno, kropka po prostu zostanie */
  }
}

function seenCount(characterId: number): number {
  try {
    return parseInt(localStorage.getItem(KEY(characterId)) || "0", 10) || 0;
  } catch {
    return 0;
  }
}

/** True gdy bohater ma plotki, których nie widział od ostatniego otwarcia Atlasu.
 *  `enabled=false` (poza grą) nie strzela po Atlas — hook i tak MUSI być wołany
 *  bezwarunkowo przez wołającego, inaczej rozjeżdża się kolejność hooków (#1517). */
export function useUnreadRumors(enabled = true): boolean {
  const heroId = useAppStore((s) => s.currentHeroId);
  const { data } = useAtlas(enabled ? heroId ?? undefined : undefined);
  if (!enabled || !heroId || !data) return false;
  return data.rumors.entries.length > seenCount(heroId);
}
