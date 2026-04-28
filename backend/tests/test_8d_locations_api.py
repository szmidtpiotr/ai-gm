"""Phase 8D — Testy API Locations (8D-5, 8D-6, 8D-7)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_admin_token():
    """Generuje admin token przez endpoint dev-login."""
    # Uwaga: admin_router ma prefix /api
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        return resp.json()["token"]
    # Fallback — spróbuj z demo/demo
    resp2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    if resp2.status_code == 200:
        return resp2.json()["token"]
    raise RuntimeError(f"Nie udało się uzyskać admin tokena: {resp.status_code} {resp.text}")


@pytest.fixture
def admin_token():
    """Fixture dostarczający ważny admin token."""
    return get_admin_token()


class TestListLocations:
    """8D-5: GET /api/locations"""

    def test_empty_list(self, admin_token):
        """Zwraca pustą listę gdy brak lokalizacji (zgodnie z aktualnym stanem DB)."""
        response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_returns_tree_structure(self, admin_token):
        """Zwraca strukturę drzewa (lokalizacje z children)."""
        response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()

        for loc in data:
            assert "id" in loc
            assert "key" in loc
            assert "label" in loc
            assert "children" in loc
            assert isinstance(loc["children"], list)

    def test_filter_by_type_macro(self, admin_token):
        """Filtr type=macro zwraca tylko makro-lokalizacje."""
        response = client.get(
            "/api/locations?type=macro",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()

        for loc in data:
            assert loc.get("location_type") == "macro"

    def test_filter_by_type_sub(self, admin_token):
        """Filtr type=sub zwraca tylko sub-lokalizacje."""
        response = client.get(
            "/api/locations?type=sub",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()

        for loc in data:
            assert loc.get("location_type") == "sub"

    def test_filter_by_parent_id(self, admin_token):
        """Filtr parent_id zwraca flat list dzieci (nie drzewo)."""
        # Najpierw pobierz jakąś lokalizację (jeśli istnieje)
        all_response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if all_response.status_code == 200 and all_response.json():
            parent_id = all_response.json()[0]["id"]

            response = client.get(
                f"/api/locations?parent_id={parent_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
            data = response.json()

            # Flat list — brak children (nie budujemy drzewa przy parent_id)
            for loc in data:
                assert loc.get("parent_id") == parent_id

    def test_unauthorized_returns_401(self):
        """Brak tokena zwraca 401."""
        response = client.get("/api/locations")
        assert response.status_code == 401


class TestCreateLocation:
    """8D-6: POST /api/locations"""

    def test_create_location_success(self, admin_token):
        """Happy path: tworzy lokalizację i zwraca 201."""
        unique_key = f"test_location_{__import__('time').time()}"

        payload = {
            "key": unique_key,
            "label": "Testowa Lokalizacja",
            "description": "Opis testowy",
            "location_type": "macro",
            "rules": None,
            "enemy_keys": ["goblin"],
            "npc_keys": []
        }

        response = client.post(
            "/api/locations",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["key"] == unique_key
        assert data["label"] == "Testowa Lokalizacja"
        assert data["location_type"] == "macro"
        assert data["enemy_keys"] == ["goblin"]
        assert "id" in data
        assert "created_at" in data

    def test_create_duplicate_key_returns_422(self, admin_token):
        """Duplikat klucza zwraca 422."""
        unique_key = f"dup_test_{__import__('time').time()}"

        payload = {
            "key": unique_key,
            "label": "Pierwsza",
            "location_type": "macro"
        }

        # Pierwsze utworzenie
        response1 = client.post(
            "/api/locations",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response1.status_code == 201

        # Drugie utworzenie — ten sam klucz
        response2 = client.post(
            "/api/locations",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response2.status_code == 422
        assert "już istnieje" in response2.json()["detail"]

    def test_create_with_invalid_parent_returns_404(self, admin_token):
        """Nieistniejący parent_id zwraca 404."""
        unique_key = f"orphan_test_{__import__('time').time()}"

        payload = {
            "key": unique_key,
            "label": "Sierotka",
            "location_type": "sub",
            "parent_id": 99999  # Nieistniejący parent
        }

        response = client.post(
            "/api/locations",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404
        assert "Parent lokalizacja" in response.json()["detail"]

    def test_create_sub_location_with_valid_parent(self, admin_token):
        """Tworzy sub-lokalizację z istniejącym parentem."""
        # Najpierw utwórz parenta
        parent_key = f"parent_{__import__('time').time()}"
        parent_payload = {
            "key": parent_key,
            "label": "Parent Test",
            "location_type": "macro"
        }

        parent_response = client.post(
            "/api/locations",
            json=parent_payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["id"]

        # Teraz utwórz dziecko
        child_key = f"child_{__import__('time').time()}"
        child_payload = {
            "key": child_key,
            "label": "Child Test",
            "location_type": "sub",
            "parent_id": parent_id
        }

        child_response = client.post(
            "/api/locations",
            json=child_payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert child_response.status_code == 201
        assert child_response.json()["parent_id"] == parent_id

    def test_create_with_invalid_location_type(self, admin_token):
        """Nieprawidłowy location_type zwraca 422 (walidacja Pydantic)."""
        payload = {
            "key": "invalid_type_test",
            "label": "Test",
            "location_type": "invalid"  # Nieprawidłowy
        }

        response = client.post(
            "/api/locations",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 422

    def test_unauthorized_returns_401(self):
        """Brak tokena zwraca 401."""
        payload = {"key": "unauthorized", "label": "Test", "location_type": "macro"}

        response = client.post("/api/locations", json=payload)
        assert response.status_code == 401


class TestGetLocationDetail:
    """8D-7: GET /api/locations/{key}"""

    def test_get_existing_location(self, admin_token):
        """Pobiera istniejącą lokalizację."""
        # Najpierw utwórz lokalizację
        unique_key = f"detail_test_{__import__('time').time()}"
        payload = {
            "key": unique_key,
            "label": "Szczegóły Test",
            "description": "Opis do szczegółów",
            "location_type": "macro",
            "rules": '{"no_combat": true}',
            "enemy_keys": [],
            "npc_keys": ["innkeeper"]
        }

        create_response = client.post(
            "/api/locations",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_response.status_code == 201

        # Pobierz szczegóły
        response = client.get(
            f"/api/locations/{unique_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == unique_key
        assert data["label"] == "Szczegóły Test"
        assert data["description"] == "Opis do szczegółów"
        assert data["location_type"] == "macro"
        assert data["rules"] == '{"no_combat": true}'
        assert "children" in data
        assert "parent" in data

    def test_get_nonexistent_location_returns_404(self, admin_token):
        """Nieistniejący key zwraca 404."""
        response = client.get(
            "/api/locations/this_key_definitely_does_not_exist_12345",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404
        assert "nie istnieje" in response.json()["detail"]

    def test_get_location_with_parent(self, admin_token):
        """Zwraca parent w odpowiedzi."""
        # Utwórz parenta
        parent_key = f"parent_detail_{__import__('time').time()}"
        parent_payload = {
            "key": parent_key,
            "label": "Parent Detail",
            "location_type": "macro"
        }

        parent_response = client.post(
            "/api/locations",
            json=parent_payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["id"]

        # Utwórz dziecko
        child_key = f"child_detail_{__import__('time').time()}"
        child_payload = {
            "key": child_key,
            "label": "Child Detail",
            "location_type": "sub",
            "parent_id": parent_id
        }

        child_response = client.post(
            "/api/locations",
            json=child_payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert child_response.status_code == 201

        # Pobierz dziecko — powinno mieć parent
        response = client.get(
            f"/api/locations/{child_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parent"] is not None
        assert data["parent"]["key"] == parent_key
        assert data["parent"]["label"] == "Parent Detail"

    def test_unauthorized_returns_401(self):
        """Brak tokena zwraca 401."""
        response = client.get("/api/locations/some-key")
        assert response.status_code == 401


class TestLocationTreeBuilding:
    """Testy budowania drzewa lokalizacji."""

    def test_nested_children_structure(self, admin_token):
        """Drzewo zawiera zagnieżdżone children."""
        # Utwórz strukturę: Miasto -> Dzielnica -> Budynek
        city_key = f"city_{__import__('time').time()}"
        city = client.post(
            "/api/locations",
            json={"key": city_key, "label": "Test City", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert city.status_code == 201
        city_id = city.json()["id"]

        district_key = f"district_{__import__('time').time()}"
        district = client.post(
            "/api/locations",
            json={"key": district_key, "label": "Test District", "location_type": "sub", "parent_id": city_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert district.status_code == 201
        district_id = district.json()["id"]

        building_key = f"building_{__import__('time').time()}"
        building = client.post(
            "/api/locations",
            json={"key": building_key, "label": "Test Building", "location_type": "sub", "parent_id": district_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert building.status_code == 201

        # Pobierz drzewo
        response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Znajdź miasto w drzewie
        city_data = next((loc for loc in data if loc["key"] == city_key), None)
        assert city_data is not None

        # Miasto powinno mieć dzielnicę w children
        assert len(city_data["children"]) > 0
        district_data = next((c for c in city_data["children"] if c["key"] == district_key), None)
        assert district_data is not None

        # Dzielnica powinna mieć budynek w children
        assert len(district_data["children"]) > 0
        building_data = next((c for c in district_data["children"] if c["key"] == building_key), None)
        assert building_data is not None
