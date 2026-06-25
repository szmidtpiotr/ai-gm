#!/usr/bin/env python3
"""Seed Kresy (Kraina B) casting — NPCs + location assignments + horror-place enemies.

Issue #981. Source of truth: docs/world/LORE_v1_KANON.md §62-67 +
frontend/showcase/swiat.html (Kresy gazetteer). Idempotent:
  - NPCs:   INSERT OR IGNORE on key (never clobbers manual edits).
  - Assignments: INSERT OR IGNORE on UNIQUE(location_key, *_key).
  - game_locations.npc_keys / enemy_keys JSON re-synced from the assignment
    tables (so the admin map + the engine JSON-fallback stay consistent).

Engine read-path (the reason this matters): turn_pipeline →
world_service.build_available_content_index() injects a "[AVAILABLE CONTENT]"
block into the LLM from location_npc_assignments / location_enemy_assignments.
A wired location makes the narrator present the canon NPC / hint the threat
instead of improvising a generic stand-in.

Run inside the backend container (reads /data/ai_gm.db).
"""
import json
import sqlite3
import sys

DB_PATH = "/data/ai_gm.db"

# ── NEW canon NPCs (created only if key absent) ──────────────────────────────
# Existing canon NPCs (Marta, Pius, Benedykt, Konrad, Wiktor, Komendant Groźna,
# medyk/kowale, pustelnik Marcin…) are reused as-is — listed in ASSIGNMENTS.
NEW_NPCS = [
    {"key": "wiedzma_jaga", "label": "Wiedźma Jaga", "npc_type": "neutral", "is_shop": 0,
     "description": "Czarownica z krzywej chaty na kurzych palach w głębi Boru Zmarłych. Lokalne dzieci straszone są jej imieniem, lecz to ona jako jedyna wie, gdzie pęknięcia Rdzenia sięgają najpłycej.",
     "personality_prompt": "Sarkastyczna i zgryźliwa. Pomoże — ale za cenę, której nie powiesz nikomu, i nigdy w sposób, jakiego się spodziewasz. Mówi zagadkami o zmarłych, którzy nie chcą leżeć."},
    {"key": "ocalaly_zgliszcza", "label": "Tobiasz, ocalały ze Zgliszcz", "npc_type": "quest_giver", "is_shop": 0,
     "description": "Przygarbiony mężczyzna o przypalonej brodzie, przywódca garstki rodzin koczujących w prowizorycznych chatach pośród spalonej wsi. Wykopał czterdzieści jeden grobów — a spis dusz mówił o czterdziestu dwóch.",
     "personality_prompt": "Zmęczony i czujny. Nie ufa obcym, lecz złamie się, gdy ktoś naprawdę wysłucha. Boi się powiedzieć głośno, co spaliło Zgliszcza — i kogo brakuje w grobach."},
    {"key": "zielarka_mira_bagno", "label": "Zielarka Mira", "npc_type": "merchant", "is_shop": 1,
     "description": "Kobieta z błotem we włosach, mieszkająca w chatce na palach pośród Bagiennej Kniei. Sprzedaje mikstury i wie o ziołach wszystko — także te rzeczy, których wiedzieć nie wypada.",
     "personality_prompt": "Bezpośrednia, lecz ostrożna w słowach. Wymienia remedia za przysługi i plotki. Ostrzega przed mgłą, która pożera wędrowców, i przed utopcami w mętnej wodzie."},
    {"key": "tartacznik_brzezino", "label": "Stary Jerzy z tartaku", "npc_type": "neutral", "is_shop": 0,
     "description": "Krzepki tartacznik znad strumienia w Brzezinie, z trocinami we włosach i lewą dłonią o trzech palcach. Pracuje od świtu do zmierzchu — i przysięga na wszystko, że słyszy nocą siekierę głęboko w borze, gdy nikogo tam nie ma.",
     "personality_prompt": "Małomówny i uparty. Mówi krótko, lecz to, co wie o lesie, ratuje życie. Bój się jego ciszy, nie jego słów."},
    {"key": "karczmarz_most", "label": "Lipka, karczmarz Pod Lipinkami", "npc_type": "merchant", "is_shop": 1,
     "description": "Pulchny karczmarz z karczmy „Pod Lipinkami” przy Moście Czarnej Rzeki. Rybny gulasz stoi u niego na ogniu dzień i noc, a z okna widać każdego, kto przeprawia się przez Czarną Rzekę.",
     "personality_prompt": "Gadatliwy i serdeczny. Zna każdą plotkę z przeprawy, bo wszyscy się u niego zatrzymują. Za miskę gulaszu powie więcej, niż powinien."},
    {"key": "karczmarz_cieszowice", "label": "Bartek, karczmarz Pod Lipą", "npc_type": "merchant", "is_shop": 1,
     "description": "Karczmarz spod stuletniej lipy w Cieszowicach — warzy najlepszy miód pitny w całych Kresach. Twarz rumiana, śmiech głośny, lecz ostatnio mniej się śmieje, bo we wsi dzieje się coś, czego nie umie nazwać.",
     "personality_prompt": "Wesoły i gościnny, choć przygaszony niepokojem ostatnich tygodni. Chętnie naleje i pogada — najlepsze plotki idą po trzecim kuflu."},
]

# ── NPC assignments: (location_key, npc_key, assignment_type) ─────────────────
# Hub-level gaps (new residents) + sub-location pins of existing hub NPCs
# (decision: "pełne — także pod-lokacje"). assignment_type='resident' unless noted.
NPC_ASSIGNMENTS = [
    # — Hub gaps (were 0 NPC) —
    ("bor_zmarlych", "wiedzma_jaga", "resident"),          # NPC-hak (decision)
    ("zgliszcza", "ocalaly_zgliszcza", "resident"),
    ("zgliszcza_obozowisko", "ocalaly_zgliszcza", "resident"),
    ("bagienna_knieja", "zielarka_mira_bagno", "resident"),
    ("bagienna_chatka_zielarki", "zielarka_mira_bagno", "resident"),
    # — Sub-location pins: new sub-specific characters —
    ("brzezino_tartak", "tartacznik_brzezino", "resident"),
    ("most_karczma_pod_lupinkami", "karczmarz_most", "resident"),
    ("cieszowice_karczma", "karczmarz_cieszowice", "resident"),
    # — Sub-location pins: existing hub NPCs at their natural sub —
    ("strazyn_lazaret", "medyk_strazyn", "resident"),
    ("strazyn_koszary", "komendant_strazyn", "resident"),
    ("wolanka_kuznia", "kowal_wolanka", "resident"),
    ("wolanka_kopalnia_glowna", "starszy_gornik_wolanka", "resident"),
    ("brzezino_dom_starszego", "soltys_brzezino", "resident"),
    ("most_komora_celna", "celnik_pius", "resident"),
    ("trzech_krukow_wielka_izba", "karczmarz_krukow", "resident"),
    ("cieszowice_kaplica", "znachorka_cieszowice", "visitor"),
    ("pustelnia_kaplica_lesna", "pustelnik_marcin", "resident"),
    ("pustelnia_ogrod_ziolowy", "pustelnik_marcin", "resident"),
    ("pustelnia_zrodlo", "pustelnik_marcin", "resident"),
]

# ── Enemy assignments (HORROR PLACES ONLY — decision) ────────────────────────
# (location_key, enemy_key, spawn_chance, max_count). All keys verified present
# in game_config_enemies on DEV. Canon: undead = Rdzeń leak; swamp = utopce/bestie.
ENEMY_ASSIGNMENTS = [
    # — Bór Zmarłych (las nieumarłych) —
    ("bor_zmarlych", "zombie", 0.6, 3),
    ("bor_zmarlych", "skeleton", 0.5, 3),
    ("bor_zmarlych", "ghoul", 0.4, 2),
    ("bor_zmarlych", "ghost", 0.3, 2),
    ("bor_cmentarz_przy_drodze", "skeleton", 0.6, 3),
    ("bor_cmentarz_przy_drodze", "zombie", 0.5, 3),
    ("bor_cmentarz_przy_drodze", "ghoul", 0.4, 2),
    ("bor_kostnica_lesna", "skeleton", 0.6, 4),
    ("bor_kostnica_lesna", "ghoul", 0.4, 2),
    ("bor_kosciol_zapomniany", "wraith", 0.4, 2),
    ("bor_kosciol_zapomniany", "ghoul", 0.4, 2),
    ("bor_kosciol_zapomniany", "cultist", 0.3, 3),
    ("bor_swiete_zrodlo_krwi", "ghoul", 0.5, 2),
    ("bor_swiete_zrodlo_krwi", "ghost", 0.3, 2),
    # — Zgliszcza (spalona wieś, masowy grób) —
    ("zgliszcza", "zombie", 0.4, 2),
    ("zgliszcza", "ghoul", 0.3, 2),
    ("zgliszcza_masowy_grob", "zombie", 0.6, 3),
    ("zgliszcza_masowy_grob", "ghoul", 0.5, 2),
    ("zgliszcza_masowy_grob", "skeleton", 0.4, 3),
    ("zgliszcza_kosciol_spalony", "wraith", 0.4, 2),
    ("zgliszcza_kosciol_spalony", "ghost", 0.4, 2),
    # — Bagienna Knieja (mokradła, utopce) —
    ("bagienna_knieja", "zombie", 0.4, 2),          # utopiec proxy
    ("bagienna_knieja", "giant_spider", 0.4, 2),
    ("bagienna_knieja", "slime", 0.3, 2),
    ("bagienna_wyspa_topielca", "zombie", 0.6, 3),
    ("bagienna_wyspa_topielca", "ghost", 0.3, 2),
    ("bagienna_pradawny_kamien", "cultist", 0.4, 3),
    ("bagienna_pradawny_kamien", "dark_mage", 0.3, 1),
]


def apply(conn: sqlite3.Connection) -> dict:
    """Idempotently apply Kresy casting. Returns counts. Importable for tests."""
    n_npc = n_npc_assign = n_enemy_assign = 0

    # 1) New NPCs (never clobber existing keys)
    for n in NEW_NPCS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO npcs
                 (key, label, npc_type, description, personality_json,
                  personality_prompt, is_shop, shop_inventory_json,
                  is_active, review_status, keyword_triggers)
               VALUES (?, ?, ?, ?, '{}', ?, ?, '[]', 1, 'permanent', '[]')""",
            (n["key"], n["label"], n["npc_type"], n["description"],
             n.get("personality_prompt", ""), int(n.get("is_shop", 0))),
        )
        n_npc += cur.rowcount or 0

    # 2) NPC assignments (engine read-path)
    for location_key, npc_key, atype in NPC_ASSIGNMENTS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO location_npc_assignments
                 (location_key, npc_key, assignment_type, is_active)
               VALUES (?, ?, ?, 1)""",
            (location_key, npc_key, atype),
        )
        n_npc_assign += cur.rowcount or 0

    # 3) Enemy assignments (horror places only)
    for location_key, enemy_key, spawn, maxc in ENEMY_ASSIGNMENTS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO location_enemy_assignments
                 (location_key, enemy_key, spawn_chance, max_count, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (location_key, enemy_key, float(spawn), int(maxc)),
        )
        n_enemy_assign += cur.rowcount or 0

    # 4) Re-sync game_locations.npc_keys / enemy_keys JSON from assignment tables
    #    (admin map display + engine JSON-fallback consistency).
    touched = {a[0] for a in NPC_ASSIGNMENTS} | {e[0] for e in ENEMY_ASSIGNMENTS}
    for loc in touched:
        npc_keys = [r[0] for r in conn.execute(
            "SELECT npc_key FROM location_npc_assignments WHERE location_key=? AND is_active=1 ORDER BY npc_key",
            (loc,))]
        enemy_keys = [r[0] for r in conn.execute(
            "SELECT enemy_key FROM location_enemy_assignments WHERE location_key=? AND is_active=1 ORDER BY enemy_key",
            (loc,))]
        conn.execute(
            "UPDATE game_locations SET npc_keys=?, enemy_keys=? WHERE key=?",
            (json.dumps(npc_keys, ensure_ascii=False),
             json.dumps(enemy_keys, ensure_ascii=False), loc),
        )

    conn.commit()
    return {"npcs_created": n_npc, "npc_assignments": n_npc_assign,
            "enemy_assignments": n_enemy_assign}


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        res = apply(conn)
        print(f"✓ NPCs created: {res['npcs_created']}")
        print(f"✓ NPC assignments added: {res['npc_assignments']}")
        print(f"✓ Enemy assignments added: {res['enemy_assignments']}")
        for tbl in ("npcs", "location_npc_assignments", "location_enemy_assignments"):
            cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: {cnt} rows total")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
