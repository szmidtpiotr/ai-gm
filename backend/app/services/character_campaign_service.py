import json
import sqlite3


def maybe_reset_hp_for_new_campaign(
    conn: sqlite3.Connection,
    character_id: int,
    campaign_id: int,
) -> bool:
    """U14 (rozszerza C19): pełny reset bohatera przy wejściu do świeżej kampanii (0 tur).

    Resetuje stan bojowy/tymczasowy: HP, mana, conditions (sheet + tabela
    character_conditions), aktywne rentale, wisząca flaga sandbox. NIE rusza
    XP / złota / ekwipunku / zaklęć.

    Wznowienie istniejącej kampanii (>0 tur) zostawia stan bez zmian.
    Zwraca True jeśli reset wykonano, False w przeciwnym razie.
    """
    turn_count_row = conn.execute(
        "SELECT COUNT(*) FROM campaign_turns WHERE campaign_id = ?", (campaign_id,)
    ).fetchone()
    if turn_count_row and int(turn_count_row[0]) > 0:
        return False

    char = conn.execute(
        "SELECT sheet_json FROM characters WHERE id = ?", (character_id,)
    ).fetchone()
    if not char:
        return False

    try:
        sheet = json.loads(char["sheet_json"] or "{}")
    except Exception:
        return False

    # HP + mana — odnowienie do max (jeśli zdefiniowane)
    max_hp = int(sheet.get("max_hp") or 0)
    if max_hp > 0:
        sheet["current_hp"] = max_hp

    max_mana = int(sheet.get("max_mana") or 0)
    if max_mana > 0:
        sheet["current_mana"] = max_mana

    # Conditions — czyste przy starcie nowej kampanii (sheet + tabela)
    sheet["conditions"] = []
    # Wisząca flaga sandbox (np. po imporcie/kopii) nie ma prawa być na żywym bohaterze
    sheet.pop("__sandbox_clone__", None)

    conn.execute(
        "UPDATE characters SET sheet_json = ? WHERE id = ?",
        (json.dumps(sheet, ensure_ascii=False), character_id),
    )

    # Tabela kondycji — usuń wszystkie wiersze bohatera (jeśli tabela istnieje)
    try:
        conn.execute(
            "DELETE FROM character_conditions WHERE character_id = ?", (character_id,)
        )
    except sqlite3.OperationalError:
        pass

    # Aktywne rentale → wygaszone (stan tymczasowy nie przechodzi do nowej kampanii)
    try:
        conn.execute(
            "UPDATE character_rentals SET status = 'expired' "
            "WHERE character_id = ? AND status = 'active'",
            (character_id,),
        )
    except sqlite3.OperationalError:
        pass

    return True
