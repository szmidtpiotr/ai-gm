"""TDD: PM5 (#1224) — Drogi/trakty jako klasa gazetteer (known od startu).

Kontrakt PM5: hexy dróg (``hex_type='road'``) regionu pochodzenia są ``known``
od startu kampanii (warstwa W1), tak by gracz widział trakt i mógł wybrać
"idę traktem". Predykat gazetteera (``is_landmark_hex``) MUSI uznawać road za
landmark, a ``compute_known_coords`` MUSI zwracać road-hexy regionu w ``known``
+ ``labelable``.

Backend nie wymagał zmian kodu — ten test blokuje regresję, gdyby ktoś usunął
``road`` z ``LANDMARK_HEX_TYPES``.
"""
import sys

sys.path.insert(0, "/app")

from app.services.fow_service import (  # noqa: E402
    compute_known_coords,
    is_landmark_hex,
    LANDMARK_HEX_TYPES,
)


def _row(hex_type="plains", region="kresy", location_key=None):
    return {"hex_type": hex_type, "region": region, "location_key": location_key}


def test_road_is_landmark_type():
    """``road`` jest typem-landmarkiem gazetteera."""
    assert "road" in LANDMARK_HEX_TYPES
    assert is_landmark_hex(_row(hex_type="road"), canonical_keys=set())


def test_region_road_known_from_start():
    """W1: trakt regionu pochodzenia znany od startu, nawet z dala od discovered."""
    world = {
        (0, 0): _row(),                                  # discovered (excluded)
        (20, 0): _row(hex_type="road", region="kresy"),  # daleki trakt regionu
    }
    known, labelable = compute_known_coords(
        world, discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=set(), bubble_radius=4,
    )
    assert (20, 0) in known, "trakt regionu pochodzenia musi być known od startu"
    assert (20, 0) in labelable, "trakt dostaje label (landmark)"


def test_other_region_road_hidden_until_unlocked():
    """Trakt obcej, nieodblokowanej krainy — NIEwidoczny (poza bąblem)."""
    world = {
        (0, 0): _row(),
        (30, 0): _row(hex_type="road", region="siwe_granie"),
    }
    known, _ = compute_known_coords(
        world, discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=set(), bubble_radius=4,
    )
    assert (30, 0) not in known, "trakt obcego regionu nie jest known przed unlockiem"


def test_road_known_in_unlocked_region_pm2():
    """PM2: po odblokowaniu krainy jej trakty wchodzą do known (known_regions)."""
    world = {
        (0, 0): _row(),
        (30, 0): _row(hex_type="road", region="siwe_granie"),
    }
    known, labelable = compute_known_coords(
        world, discovered_coords={(0, 0)},
        origin_region="kresy", canonical_keys=set(), bubble_radius=4,
        known_regions={"kresy", "siwe_granie"},
    )
    assert (30, 0) in known, "trakt odblokowanej krainy musi być known (PM2)"
    assert (30, 0) in labelable
