"""TDD: PM1 (#1220) — Trójstanowy FOW: stan ``known``.

Testuje czystą funkcję ``compute_known_coords`` (bez DB), która wylicza zbiór
hexów ``known`` z trzech warstw:
  W1 — gazetteer regionu pochodzenia (landmarki krainy start-hexa),
  W2 — kroczący bąbel promienia R wokół KAŻDEGO discovered hexa,
  W3 — świat (miasta + rzeki + osady canonical globalnie).

Kontrakt: funkcja zwraca WYŁĄCZNIE współrzędne (żadnych ``location_key`` ani
danych ``game_locations``); ``discovered`` wygrywa z ``known``.
"""
import sys

sys.path.insert(0, "/app")

from app.services.fow_service import compute_known_coords  # noqa: E402


def _row(hex_type="plains", region="kresy", location_key=None):
    return {"hex_type": hex_type, "region": region, "location_key": location_key}


def _base_world():
    """Overworld index map_level=0 spread wide enough to test distance layers."""
    return {
        # Bubble neighbourhood of the discovered hex (0,0):
        (0, 0): _row(),                       # discovered (excluded from known)
        (4, 0): _row(),                       # exactly radius 4 → known via W2
        (5, 0): _row(),                       # radius 5 → NOT reached by bubble
        # W1: landmark deep in origin region, far from any discovered hex:
        (20, 0): _row(hex_type="town", region="kresy"),
        # W1: canonical-location landmark in origin region (plain terrain):
        (2, 2): _row(hex_type="plains", region="kresy", location_key="karczma_stara"),
        # W3: city in another region — visible worldwide:
        (30, 0): _row(hex_type="city", region="siwe_granie"),
        # Plain hex in another region, far away — must stay hidden:
        (31, 0): _row(hex_type="plains", region="siwe_granie"),
    }


CANON = {"karczma_stara"}


def test_bubble_radius_4_reveals_terrain():
    """W2: teren dokładnie w promieniu 4 od discovered → known; promień 5 → nie."""
    known, labelable = compute_known_coords(
        _base_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    assert (4, 0) in known, "hex w promieniu 4 musi być known"
    assert (4, 0) not in labelable, "zwykły teren w bąblu nie dostaje label"
    assert (5, 0) not in known, "hex w promieniu 5 nie może być known (poza bąblem)"


def test_region_landmark_visible_from_far():
    """W1: landmark regionu pochodzenia znany od startu, nawet z drugiego końca."""
    known, labelable = compute_known_coords(
        _base_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    assert (20, 0) in known, "landmark (town) regionu pochodzenia musi być known"
    assert (20, 0) in labelable, "landmark dostaje widoczny label"


def test_other_region_city_visible_via_world_layer():
    """W3: miasto innej krainy widoczne globalnie (bez promienia)."""
    known, labelable = compute_known_coords(
        _base_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    assert (30, 0) in known, "miasto innego regionu musi być known (W3)"
    assert (30, 0) in labelable, "miasto dostaje label"


def test_other_region_plain_hex_hidden():
    """Zwykły hex innej krainy poza bąblem — NIEwidoczny."""
    known, _ = compute_known_coords(
        _base_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    assert (31, 0) not in known, "zwykły teren obcego regionu nie może być known"


def test_canonical_location_is_gazetteer_landmark():
    """W1: hex z location_key → canonical=1 wchodzi do gazetteera (known + label)."""
    known, labelable = compute_known_coords(
        _base_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    assert (2, 2) in known, "hex z kanoniczną lokacją musi być known (gazetteer)"
    assert (2, 2) in labelable, "kanoniczna osada dostaje label"


def test_known_returns_only_coords_no_location_data():
    """Kontrakt: funkcja zwraca same współrzędne — zero location_key/danych lokacji."""
    known, labelable = compute_known_coords(
        _base_world(), discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    for coord in known:
        assert isinstance(coord, tuple) and len(coord) == 2, (
            f"known musi zawierać tylko krotki (q,r), dostano: {coord!r}"
        )
    assert labelable <= known, "label_coords musi być podzbiorem known"


def test_discovered_wins_over_known():
    """``discovered`` wykluczony ze zbioru known (pełne dane, nie known)."""
    world = _base_world()
    # Make (20,0) both a landmark AND discovered → must NOT appear in known.
    known, _ = compute_known_coords(
        world, discovered_coords={(0, 0), (20, 0)},
        origin_region="kresy", canonical_keys=CANON, bubble_radius=4,
    )
    assert (20, 0) not in known, "discovered hex nie może być zwrócony jako known"
