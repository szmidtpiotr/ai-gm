#!/usr/bin/env python3
"""
RM2 — Lore→data: backfill game_locations.region + sync world_hexes.
Idempotent: safe to re-run. Logs unmapped locations.
Refs: issue #1029, FAZA RM #917, LORE_v1_KANON.md sec 3, FAZA_RM_MAPA_KRAIN.md sec 2.
"""
import sqlite3
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

DEFAULT_DB = Path('/data/ai_gm.db')

# Canon from LORE_v1_KANON.md section 3 + FAZA_RM_MAPA_KRAIN.md section 2.
# Commit of this dict = Piotr's approval of the mapping.
REGION_MAP: dict[str, str] = {
    # ── KORONNE NIZINY (A) — Vilnograd, Volhynia, Klasztor Iskry ──────────────
    'vilnograd_stolica': 'koronne_niziny',
    'vilnograd_dzielnica_zlodziei': 'koronne_niziny',
    'vilnograd_rynek': 'koronne_niziny',
    'vilnograd_swiatynia_swiatla': 'koronne_niziny',
    'vilnograd_tawerna_pod_korona': 'koronne_niziny',
    'vilnograd_zamek': 'koronne_niziny',
    'volhynia_kupiecka': 'koronne_niziny',
    'volhynia_arena_walk': 'koronne_niziny',
    'volhynia_gildia_kupcow': 'koronne_niziny',
    'volhynia_gospoda_szlaku': 'koronne_niziny',
    'volhynia_targowisko': 'koronne_niziny',
    'klasztor_iskry_centrum': 'koronne_niziny',
    'klasztor_iskry_biblioteka': 'koronne_niziny',
    'klasztor_iskry_cele_mnichow': 'koronne_niziny',
    'klasztor_iskry_grobowiec_swietego': 'koronne_niziny',
    'klasztor_iskry_kaplica_glowna': 'koronne_niziny',

    # ── KRESY (B) — Strażyn/Strzegwacht, Cieszowice/Cieszburg, Brzezino/Birkenwald,
    #               Wolanka/Wolfsmark, Pod Trzema Krukami, Most Czarnej Rzeki,
    #               Pustelnia Świętego Marcina, Zgliszcza ─────────────────────
    'strazyn': 'kresy',
    'strazyn_kantyna': 'kresy',
    'strazyn_koszary': 'kresy',
    'strazyn_lazaret': 'kresy',
    'strazyn_wieza_strazak': 'kresy',
    'cieszowice': 'kresy',
    'cieszowice_kaplica': 'kresy',
    'cieszowice_karczma': 'kresy',
    'cieszowice_pole_lubek': 'kresy',
    'cieszowice_studnia': 'kresy',
    'cieszowice_tavern': 'kresy',
    'brzezino': 'kresy',
    'brzezino_dom_starszego': 'kresy',
    'brzezino_swieta_polanka': 'kresy',
    'brzezino_tartak': 'kresy',
    'borowiec': 'kresy',
    'wolanka': 'kresy',
    'wolanka_kopalnia_glowna': 'kresy',
    'wolanka_kosciol_swietego_floriana': 'kresy',
    'wolanka_kuznia': 'kresy',
    'wolanka_szynk': 'kresy',
    'trzech_krukow': 'kresy',
    'trzech_krukow_pokoje_kupcow': 'kresy',
    'trzech_krukow_stajnia': 'kresy',
    'trzech_krukow_wielka_izba': 'kresy',
    'gospoda_pod_z_amanym_rogiem': 'kresy',
    'karczma_pod_czarnym_krukiem': 'kresy',
    'karczma_przy_rozwidleniu': 'kresy',
    'most_czarnej_rzeki': 'kresy',
    'most_karczma_pod_lupinkami': 'kresy',
    'most_komora_celna': 'kresy',
    'most_warta_mostowa': 'kresy',
    'pustelnia_marcina': 'kresy',
    'pustelnia_kaplica_lesna': 'kresy',
    'pustelnia_ogrod_ziolowy': 'kresy',
    'pustelnia_zrodlo': 'kresy',
    'zgliszcza': 'kresy',
    'zgliszcza_kosciol_spalony': 'kresy',
    'zgliszcza_masowy_grob': 'kresy',
    'zgliszcza_obozowisko': 'kresy',
    # roads & unnamed Kresy features
    'nasyp_zawalonego_traktu': 'kresy',
    'zawalony_trakt': 'kresy',
    'wschodnia_wioska': 'kresy',
    'wioska_przy_trakcie': 'kresy',
    'osada_przy_trakcie': 'kresy',
    'osada_przy_rozwidleniu': 'kresy',
    'opuszczona_kaplica': 'kresy',
    'podziemna_izba_stra_nicza': 'kresy',
    'pocz_tek_cie_ki_za_sk_adem_drewna': 'kresy',
    'ruiny_stra_nicy_przy_urwisku': 'kresy',

    # ── CZARNOBÓR (C) — Bór Zmarłych, Knieja Czarnych Drzew, Bagienna Knieja,
    #                   Trzęsawiska Mgieł, Step Wilków ──────────────
    'bor_zmarlych': 'czarnobor',
    'bor_cmentarz_przy_drodze': 'czarnobor',
    'bor_kosciol_zapomniany': 'czarnobor',
    'bor_kostnica_lesna': 'czarnobor',
    'bor_swiete_zrodlo_krwi': 'czarnobor',
    'las_czarnych_drzew': 'czarnobor',
    'las_czarnych_chata_starej': 'czarnobor',
    'las_czarnych_grobowiec_kniazia': 'czarnobor',
    'las_czarnych_polanka_starszych': 'czarnobor',
    'las_czarnych_zlamany_dab': 'czarnobor',
    'bagienna_knieja': 'czarnobor',
    'bagienna_chatka_zielarki': 'czarnobor',
    'bagienna_pradawny_kamien': 'czarnobor',
    'bagienna_wyspa_topielca': 'czarnobor',
    'bagienna_chata_pustelnika': 'czarnobor',
    'trzesawiska_mgiel': 'czarnobor',
    'trzesawiska_chata_topielcow': 'czarnobor',
    'trzesawiska_drzewo_powieszonych': 'czarnobor',
    'trzesawiska_ognisty_kostkocian': 'czarnobor',
    'step_wilkow': 'czarnobor',
    'step_kurhan_chana': 'czarnobor',
    'step_obozowisko_koczownikow': 'czarnobor',
    'step_strazowanica': 'czarnobor',
    # Złoty Las (+suby) usunięty z Czarnoboru 2026-07-24 (CB-4): lore krainy §4
    # (zatw. 2026-07-20) go NIE wymienia. To generyczna bazowa lokacja świata —
    # tag 'czarnobor' był artefaktem auto-heurystyki 06-29 (#1029) SPRZED lore.
    # Nowsza, zatwierdzona przebudowa krainy go wyklucza → region=NULL (floating).

    # ── SIWE GRANIE (D) — Kopalnia Czarnego Hutmana, Krzyż Gór, Lodowy Pas,
    #                     Tundra Wiecznego Mrozu, Czarne Skały ─────────────────
    'kopalnia_czarnego_hutmana': 'siwe_granie',
    'kopalnia_komnata_brygadzisty': 'siwe_granie',
    'kopalnia_serce_kopalni': 'siwe_granie',
    'kopalnia_sztolnia_srebrna': 'siwe_granie',
    'kopalnia_wejscie_glowne': 'siwe_granie',
    'kopalnia_zalane_korytarze': 'siwe_granie',
    'krzyz_gor': 'siwe_granie',
    'krzyz_chatka_pasterska': 'siwe_granie',
    'krzyz_jaskinia_smoka': 'siwe_granie',
    'krzyz_klasztor_szczytu': 'siwe_granie',
    'krzyz_kopalnia_kobaltu': 'siwe_granie',
    'krzyz_przelecz_swietej_jadwigi': 'siwe_granie',
    'lodowy_pas': 'siwe_granie',
    'lodowy_dom_szamana': 'siwe_granie',
    'lodowy_jaskinia_lodu': 'siwe_granie',
    'lodowy_kostnica_morsow': 'siwe_granie',
    'lodowy_kryształowa_komnata': 'siwe_granie',
    'tundra_mrozu': 'siwe_granie',
    'tundra_lodowiec_pradawny': 'siwe_granie',
    'tundra_obozowisko_huskies': 'siwe_granie',
    'tundra_swiete_kamienie': 'siwe_granie',
    'czarne_skaly': 'siwe_granie',
    'czarne_grobowiec_kapłana': 'siwe_granie',
    'czarne_krater_dymiacy': 'siwe_granie',
    'czarne_swiatynia_ognia': 'siwe_granie',

    # ── WYBRZEŻE ŁEZ (E) — Czarnogród, Zatoka Topielców, Wybrzeże Łez ─────────
    'czarnogrod_port': 'wybrzeze_lez',
    'czarnogrod_giełda_kontrabandy': 'wybrzeze_lez',
    'czarnogrod_latarnia_topielcow': 'wybrzeze_lez',
    'czarnogrod_nabrzeze': 'wybrzeze_lez',
    'czarnogrod_pod_topielcem': 'wybrzeze_lez',
    'zatoka_topielcow': 'wybrzeze_lez',
    'zatoka_jaskinie_skarbow': 'wybrzeze_lez',
    'zatoka_kapitanska_karczma': 'wybrzeze_lez',
    'zatoka_pirackie_doki': 'wybrzeze_lez',
    'zatoka_rada_piracka': 'wybrzeze_lez',
    'wybrzeze_lez': 'wybrzeze_lez',
    'wybrzeze_jaskinia_kontrabandy': 'wybrzeze_lez',
    'wybrzeze_latarnia_starego': 'wybrzeze_lez',
    'wybrzeze_wraki_starych_statkow': 'wybrzeze_lez',
    'wybrzeze_świątynia_topielcow': 'wybrzeze_lez',

    # ── MARTWE PUSTKOWIA (F) — Pustkowie Solne, Świątynia Pradawnych,
    #                          Ruiny Klasztoru, Krypta Krwawego Hrabiego,
    #                          Twierdza Bezimiennego ──────────────────────────
    'pustkowie_solne': 'martwe_pustkowia',
    'pustkowie_oaza_zlodzieja': 'martwe_pustkowia',
    'pustkowie_piaskowa_mogila': 'martwe_pustkowia',
    'pustkowie_zatopiony_okret': 'martwe_pustkowia',
    'swiatynia_pradawnych': 'martwe_pustkowia',
    'swiatynia_brama_dziwna': 'martwe_pustkowia',
    'swiatynia_komnata_kapłanów': 'martwe_pustkowia',
    'swiatynia_ołtarz_glowny': 'martwe_pustkowia',
    'swiatynia_podziemna_rzeka': 'martwe_pustkowia',
    'ruiny_klasztoru_pradawnego': 'martwe_pustkowia',
    'ruiny_klasztoru_kaplica_glowna': 'martwe_pustkowia',
    'ruiny_klasztoru_krypta': 'martwe_pustkowia',
    'ruiny_klasztoru_skryptorium': 'martwe_pustkowia',
    'ruiny_klasztoru_studnia': 'martwe_pustkowia',
    'krypta_krwawego_hrabiego': 'martwe_pustkowia',
    'krypta_grobowiec_hrabiego': 'martwe_pustkowia',
    'krypta_przedsionek': 'martwe_pustkowia',
    'krypta_sala_uczt': 'martwe_pustkowia',
    'krypta_sale_służących': 'martwe_pustkowia',
    'twierdza_bezimiennego': 'martwe_pustkowia',
    'twierdza_biblioteka_zakazana': 'martwe_pustkowia',
    'twierdza_dziedziniec': 'martwe_pustkowia',
    'twierdza_lochy': 'martwe_pustkowia',
    'twierdza_sala_tronowa': 'martwe_pustkowia',
    'twierdza_szczyt_wiezy': 'martwe_pustkowia',
}

# Keys that are intentionally NULL (test fixtures, system entries, unnamed camps)
NULL_PREFIXES = (
    'building_', 'city_', 'city_a_', 'city_b_', 'city_nested_',
    'district_', 'district_nested_',
    'child_', 'child_del_',
    'parent_', 'parent_del_', 'parent_detail_', 'parent_force_',
    'parent_immut_', 'parent_macro_', 'parent_create_', 'parent_1_', 'parent_2_',
    'sub_1_', 'sub_2_',
    'create_test_', 'create_data_test_', 'crud_flow_',
    'dup_test_', 'detail_test_', 'leaf_delete_',
    'test_loc_', 'test_location_', 'test_flow_', 'test_city_val', 'test_tavern_val',
    'unikalna_nazwa_lokalizacji_',
    'real_place_', 'real_place_pw_',
    'temp_camp_',
    'nowa_tajemna_jaskinia',
    'campaign_',
    'building_nested_',
    'empty_inn_u31', 'goblin_camp_u31', 'parent_inn_u31', 'locked_inn_u31',
    'test_inn_u31', 'tavern_u31', 'sub_cellar_u31',
    'pre_llm_here', 'log_success_loc',
    'approve_ai_loc', 'approved_ai_loc', 'pending_ai_loc', 'reject_ai_loc',
    'hook_karczma', 'hook_fenced_karczma',
)


def _is_null_key(key: str) -> bool:
    return any(key.startswith(p) or key == p for p in NULL_PREFIXES)


def run(db_path: Path = DEFAULT_DB) -> dict:
    """Assign region to game_locations and sync placed hex region. Returns stats."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Fetch all locations
    cur.execute('SELECT key, world_hex_q, world_hex_r, region FROM game_locations')
    locations = cur.fetchall()

    updated_locs = 0
    skipped_null = 0
    unmapped = []

    for loc in locations:
        key = loc['key']
        desired = REGION_MAP.get(key)

        if desired is None:
            if _is_null_key(key):
                skipped_null += 1
                continue
            if loc['region'] is None:
                unmapped.append(key)
            continue

        if loc['region'] != desired:
            cur.execute('UPDATE game_locations SET region=? WHERE key=?', (desired, key))
            updated_locs += 1

    # 2. Sync world_hexes for placed locations
    cur.execute(
        # #1525: „osadzona" = wskazana przez heks (kanon); cache q/r jest jego lustrem.
        'SELECT g.key, g.world_hex_q, g.world_hex_r, g.region FROM game_locations g '
        'WHERE g.world_hex_q IS NOT NULL AND g.world_hex_r IS NOT NULL '
        'AND g.region IS NOT NULL '
        'AND EXISTS (SELECT 1 FROM world_hexes h WHERE h.map_level=0 AND h.is_active=1 '
        '            AND h.location_key = g.key)'
    )
    placed = cur.fetchall()

    # Group by (q, r) to detect conflicts
    from collections import defaultdict
    hex_to_regions: dict[tuple, list[tuple]] = defaultdict(list)
    for loc in placed:
        hex_to_regions[(loc['world_hex_q'], loc['world_hex_r'])].append((loc['key'], loc['region']))

    updated_hexes = 0
    conflict_hexes = 0

    for (q, r), assignments in hex_to_regions.items():
        regions = {reg for _, reg in assignments}
        if len(regions) > 1:
            log.warning(
                'CONFLICT hex(%d,%d): multiple regions %s from locations %s — skipping hex sync',
                q, r, regions, [k for k, _ in assignments]
            )
            conflict_hexes += 1
            continue

        desired_region = next(iter(regions))
        cur.execute(
            'SELECT region FROM world_hexes WHERE q=? AND r=? AND map_level=0',
            (q, r)
        )
        row = cur.fetchone()
        if row is None:
            log.warning('No world_hex at (%d,%d) map_level=0 — skipping', q, r)
            continue
        if row['region'] != desired_region:
            cur.execute(
                'UPDATE world_hexes SET region=? WHERE q=? AND r=? AND map_level=0',
                (desired_region, q, r)
            )
            updated_hexes += 1

    conn.commit()
    conn.close()

    if unmapped:
        log.warning('UNMAPPED locations (region=NULL, no lore entry): %s', unmapped)

    log.info(
        'Done — locs updated: %d, skipped nulls: %d, unmapped: %d, hexes updated: %d, hex conflicts: %d',
        updated_locs, skipped_null, len(unmapped), updated_hexes, conflict_hexes
    )

    return {
        'updated_locs': updated_locs,
        'unmapped': unmapped,
        'updated_hexes': updated_hexes,
        'conflict_hexes': conflict_hexes,
    }


if __name__ == '__main__':
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        log.error('DB not found: %s', db)
        sys.exit(1)
    run(db)
