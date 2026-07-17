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

/** True gdy bohater ma plotki, których nie widział od ostatniego otwarcia Atlasu. */
export function useUnreadRumors(): boolean {
  const heroId = useAppStore((s) => s.currentHeroId);
  const { data } = useAtlas(heroId ?? undefined);
  if (!heroId || !data) return false;
  return data.rumors.entries.length > seenCount(heroId);
}
