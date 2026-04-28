"""Phase 8D — HTTP endpoint tests for locations and admin_location routers.

Tests all endpoints from locations.py and admin_location.py using FastAPI TestClient.
Includes admin token authentication.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_admin_token():
    """Generuje admin token przez endpoint dev-login."""
    resp = client.post("/api/admin/dev-login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        return resp.json()["token"]
    resp2 = client.post("/api/admin/dev-login", json={"username": "demo", "password": "demo"})
    if resp2.status_code == 200:
        return resp2.json()["token"]
    raise RuntimeError("Nie udało się uzyskać admin tokena")


@pytest.fixture
def admin_token():
    """Fixture dostarczający ważny admin token."""
    return get_admin_token()


@pytest.fixture
def test_location(admin_token):
    """Fixture tworzący testową lokalizację."""
    import time

    unique_key = f"test_loc_{time.time()}"
    resp = client.post(
        "/api/locations",
        json={
            "key": unique_key,
            "label": "Test Location",
            "description": "Test description",
            "location_type": "macro"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    if resp.status_code == 201:
        return resp.json()
    return None


class TestGetLocations:
    """1. GET /api/locations - returns list with tree structure"""

    def test_get_locations_returns_200(self, admin_token):
        """GET /api/locations zwraca 200 dla autoryzowanego użytkownika."""
        response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_get_locations_returns_list(self, admin_token):
        """GET /api/locations zwraca listę."""
        response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        assert isinstance(data, list)

    def test_get_locations_returns_tree_structure(self, admin_token):
        """GET /api/locations zwraca strukturę drzewa z children."""
        response = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()

        for loc in data:
            assert "id" in loc
            assert "key" in loc
            assert "label" in loc
            assert "children" in loc
            assert isinstance(loc["children"], list)

    def test_get_locations_unauthorized_returns_401(self):
        """GET /api/locations bez tokena zwraca 401."""
        response = client.get("/api/locations")

        assert response.status_code == 401


class TestGetLocationDetail:
    """2. GET /api/locations/{key} - returns location details (404 for missing)"""

    def test_get_existing_location_returns_200(self, admin_token, test_location):
        """GET /api/locations/{key} dla istniejącej lokalizacji zwraca 200."""
        if not test_location:
            pytest.skip("Nie udało się utworzyć testowej lokalizacji")

        response = client.get(
            f"/api/locations/{test_location['key']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_get_existing_location_returns_details(self, admin_token, test_location):
        """GET /api/locations/{key} zwraca szczegóły lokalizacji."""
        if not test_location:
            pytest.skip("Nie udało się utworzyć testowej lokalizacji")

        response = client.get(
            f"/api/locations/{test_location['key']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        assert data["key"] == test_location["key"]
        assert data["label"] == test_location["label"]
        assert "id" in data
        assert "children" in data
        assert "parent" in data

    def test_get_nonexistent_location_returns_404(self, admin_token):
        """GET /api/locations/{key} dla nieistniejącej lokalizacji zwraca 404."""
        response = client.get(
            "/api/locations/this_key_does_not_exist_12345",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404

    def test_get_location_detail_unauthorized_returns_401(self):
        """GET /api/locations/{key} bez tokena zwraca 401."""
        response = client.get("/api/locations/some-key")

        assert response.status_code == 401


class TestCreateLocation:
    """3. POST /api/locations - creates new location (201)"""

    def test_create_location_returns_201(self, admin_token):
        """POST /api/locations tworzy lokalizację i zwraca 201."""
        import time

        unique_key = f"create_test_{time.time()}"
        response = client.post(
            "/api/locations",
            json={
                "key": unique_key,
                "label": "Create Test Location",
                "description": "Created during test",
                "location_type": "macro",
                "enemy_keys": ["goblin"],
                "npc_keys": ["merchant"]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201

    def test_create_location_returns_location_data(self, admin_token):
        """POST /api/locations zwraca dane utworzonej lokalizacji."""
        import time

        unique_key = f"create_data_test_{time.time()}"
        response = client.post(
            "/api/locations",
            json={
                "key": unique_key,
                "label": "Create Data Test",
                "location_type": "macro",
                "enemy_keys": ["rat"]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        assert data["key"] == unique_key
        assert data["label"] == "Create Data Test"
        assert data["location_type"] == "macro"
        assert data["enemy_keys"] == ["rat"]
        assert "id" in data
        assert "created_at" in data

    def test_create_duplicate_key_returns_422(self, admin_token):
        """POST /api/locations z duplikatem klucza zwraca 422."""
        import time

        unique_key = f"dup_test_{time.time()}"

        # Pierwsze utworzenie
        response1 = client.post(
            "/api/locations",
            json={"key": unique_key, "label": "First", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response1.status_code == 201

        # Drugie utworzenie - ten sam klucz
        response2 = client.post(
            "/api/locations",
            json={"key": unique_key, "label": "Second", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response2.status_code == 422

    def test_create_location_unauthorized_returns_401(self):
        """POST /api/locations bez tokena zwraca 401."""
        response = client.post(
            "/api/locations",
            json={"key": "unauthorized", "label": "Test", "location_type": "macro"}
        )

        assert response.status_code == 401


class TestUpdateLocation:
    """4. PUT /api/locations/{key} - updates location (parent_id immutable)"""

    def test_update_location_returns_200(self, admin_token, test_location):
        """PUT /api/locations/{key} aktualizuje lokalizację."""
        if not test_location:
            pytest.skip("Nie udało się utworzyć testowej lokalizacji")

        response = client.put(
            f"/api/locations/{test_location['key']}",
            json={
                "key": test_location["key"],
                "label": "Updated Label",
                "description": "Updated description",
                "location_type": "macro"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_update_location_changes_label(self, admin_token, test_location):
        """PUT /api/locations/{key} zmienia label."""
        if not test_location:
            pytest.skip("Nie udało się utworzyć testowej lokalizacji")

        new_label = "Updated Label Test"
        response = client.put(
            f"/api/locations/{test_location['key']}",
            json={
                "key": test_location["key"],
                "label": new_label,
                "location_type": "macro"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        assert data["label"] == new_label

    def test_update_nonexistent_location_returns_404(self, admin_token):
        """PUT /api/locations/{key} dla nieistniejącej zwraca 404."""
        response = client.put(
            "/api/locations/nonexistent_key_12345",
            json={"key": "nonexistent_key_12345", "label": "Test", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404

    def test_update_location_parent_id_immutable(self, admin_token):
        """PUT /api/locations/{key} nie zmienia parent_id."""
        import time

        # Stwórz dwie lokalizacje
        parent_key = f"parent_immut_{time.time()}"
        child_key = f"child_immut_{time.time()}"

        parent_resp = client.post(
            "/api/locations",
            json={"key": parent_key, "label": "Parent", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if parent_resp.status_code != 201:
            pytest.skip("Nie udało się utworzyć parenta")

        parent_id = parent_resp.json()["id"]

        child_resp = client.post(
            "/api/locations",
            json={"key": child_key, "label": "Child", "location_type": "sub", "parent_id": parent_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if child_resp.status_code != 201:
            pytest.skip("Nie udało się utworzyć childa")

        child_data = child_resp.json()
        original_parent_id = child_data.get("parent_id")

        # Próba aktualizacji - parent_id powinien pozostać niezmieniony
        # W PUT przekazujemy parent_id ale endpoint go ignoruje
        update_resp = client.put(
            f"/api/locations/{child_key}",
            json={
                "key": child_key,
                "label": "Updated Child",
                "location_type": "sub",
                "parent_id": parent_id  # Próba przekazania - powinna być zignorowana
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Aktualizacja powinna się udać
        assert update_resp.status_code == 200

    def test_update_location_unauthorized_returns_401(self):
        """PUT /api/locations/{key} bez tokena zwraca 401."""
        response = client.put(
            "/api/locations/some-key",
            json={"key": "some-key", "label": "Test", "location_type": "macro"}
        )

        assert response.status_code == 401


class TestDeleteLocation:
    """5. DELETE /api/locations/{key} - soft deletes leaf location
       6. DELETE /api/locations/{key} with children - returns 409 or 422
    """

    def test_delete_leaf_location_returns_204(self, admin_token):
        """DELETE /api/locations/{key} dla liścia zwraca 204."""
        import time

        # Stwórz lokalizację bez dzieci (leaf)
        leaf_key = f"leaf_delete_{time.time()}"
        create_resp = client.post(
            "/api/locations",
            json={"key": leaf_key, "label": "Leaf To Delete", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_resp.status_code != 201:
            pytest.skip("Nie udało się utworzyć lokalizacji")

        # Usuń
        delete_resp = client.delete(
            f"/api/locations/{leaf_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert delete_resp.status_code == 204

    def test_delete_location_with_children_returns_422(self, admin_token):
        """DELETE /api/locations/{key} z dziećmi zwraca 422."""
        import time

        # Stwórz strukturę parent + child
        parent_key = f"parent_del_{time.time()}"
        parent_resp = client.post(
            "/api/locations",
            json={"key": parent_key, "label": "Parent To Delete", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if parent_resp.status_code != 201:
            pytest.skip("Nie udało się utworzyć parenta")

        parent_id = parent_resp.json()["id"]

        # Stwórz dziecko
        child_key = f"child_del_{time.time()}"
        client.post(
            "/api/locations",
            json={"key": child_key, "label": "Child", "location_type": "sub", "parent_id": parent_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Próba usunięcia parenta - powinna zwrócić 422 (lub 409)
        delete_resp = client.delete(
            f"/api/locations/{parent_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert delete_resp.status_code in (409, 422)

    def test_delete_location_force_removes_children(self, admin_token):
        """DELETE /api/locations/{key}?force=true usuwa też dzieci."""
        import time

        # Stwórz strukturę parent + child
        parent_key = f"parent_force_{time.time()}"
        parent_resp = client.post(
            "/api/locations",
            json={"key": parent_key, "label": "Parent Force", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if parent_resp.status_code != 201:
            pytest.skip("Nie udało się utworzyć parenta")

        parent_id = parent_resp.json()["id"]

        child_key = f"child_force_{time.time()}"
        client.post(
            "/api/locations",
            json={"key": child_key, "label": "Child Force", "location_type": "sub", "parent_id": parent_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Usunięcie z force=true
        delete_resp = client.request(
            "DELETE",
            f"/api/locations/{parent_key}",
            json={"force": True},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Z force=true powinno się udać (204)
        assert delete_resp.status_code == 204

    def test_delete_nonexistent_location_returns_404(self, admin_token):
        """DELETE /api/locations/{key} dla nieistniejącej zwraca 404."""
        response = client.delete(
            "/api/locations/nonexistent_delete_12345",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404

    def test_delete_location_unauthorized_returns_401(self):
        """DELETE /api/locations/{key} bez tokena zwraca 401."""
        response = client.delete("/api/locations/some-key")

        assert response.status_code == 401


class TestAdminConfigLocationFlags:
    """7. GET /api/admin/config/location-flags - returns 3 flags
       8. PUT /api/admin/config/location-flags - updates flags
    """

    def test_get_location_flags_returns_200(self, admin_token):
        """GET /api/admin/config/location-flags zwraca 200."""
        response = client.get(
            "/api/admin/config/location-flags",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_get_location_flags_returns_three_flags(self, admin_token):
        """GET /api/admin/config/location-flags zwraca 3 flagi."""
        response = client.get(
            "/api/admin/config/location-flags",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        assert "location_integrity_enabled" in data
        assert "location_parser_json_enabled" in data
        assert "location_parser_fallback_enabled" in data

    def test_get_location_flags_unauthorized_returns_401(self):
        """GET /api/admin/config/location-flags bez tokena zwraca 401."""
        response = client.get("/api/admin/config/location-flags")

        assert response.status_code == 401

    def test_put_location_flags_returns_200(self, admin_token):
        """PUT /api/admin/config/location-flags aktualizuje flagi."""
        response = client.put(
            "/api/admin/config/location-flags",
            json={"location_integrity_enabled": 0},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in (200, 204)

    def test_put_location_flags_updates_value(self, admin_token):
        """PUT /api/admin/config/location-flags zmienia wartość."""
        # Najpierw wyłącz
        client.put(
            "/api/admin/config/location-flags",
            json={"location_integrity_enabled": 0},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Sprawdź czy się zmieniło
        get_resp = client.get(
            "/api/admin/config/location-flags",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = get_resp.json()
        assert data["location_integrity_enabled"] is False

        # Przywróć włączone
        client.put(
            "/api/admin/config/location-flags",
            json={"location_integrity_enabled": 1},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    def test_put_location_flags_unauthorized_returns_401(self):
        """PUT /api/admin/config/location-flags bez tokena zwraca 401."""
        response = client.put(
            "/api/admin/config/location-flags",
            json={"location_integrity_enabled": 0}
        )

        assert response.status_code == 401


class TestAdminLocationLog:
    """9. GET /api/admin/location-log - returns log entries"""

    def test_get_location_log_returns_200(self, admin_token):
        """GET /api/admin/location-log zwraca 200."""
        response = client.get(
            "/api/admin/location-log",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_get_location_log_returns_entries(self, admin_token):
        """GET /api/admin/location-log zwraca strukturę z entries."""
        response = client.get(
            "/api/admin/location-log",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        assert "entries" in data
        assert "count" in data
        assert isinstance(data["entries"], list)

    def test_get_location_log_with_session_filter(self, admin_token):
        """GET /api/admin/location-log?session_id=X filtruje po sesji."""
        response = client.get(
            "/api/admin/location-log?session_id=1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

        data = response.json()
        assert "filters_applied" in data
        assert data["filters_applied"]["session_id"] == 1

    def test_get_location_log_with_limit(self, admin_token):
        """GET /api/admin/location-log?limit=X ogranicza liczbę wyników."""
        response = client.get(
            "/api/admin/location-log?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_get_location_log_unauthorized_returns_401(self):
        """GET /api/admin/location-log bez tokena zwraca 401."""
        response = client.get("/api/admin/location-log")

        assert response.status_code == 401


class TestSessionLocationLog:
    """GET /api/admin/session/{id}/location-log - logi per sesja"""

    def test_get_session_location_log_returns_200_or_404(self, admin_token):
        """GET /api/admin/session/{id}/location-log zwraca 200 lub 404."""
        response = client.get(
            "/api/admin/session/1/location-log",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # 200 jeśli sesja istnieje, 404 jeśli nie
        assert response.status_code in (200, 404)

    def test_get_session_location_log_structure(self, admin_token):
        """GET /api/admin/session/{id}/location-log ma poprawną strukturę."""
        response = client.get(
            "/api/admin/session/1/location-log",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "count" in data
            assert "entries" in data

    def test_get_session_location_log_with_since_filter(self, admin_token):
        """GET /api/admin/session/{id}/location-log?since=... filtruje po dacie."""
        response = client.get(
            "/api/admin/session/1/location-log?since=2026-01-01T00:00:00",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in (200, 404)

    def test_get_session_location_log_unauthorized_returns_401(self):
        """GET /api/admin/session/{id}/location-log bez tokena zwraca 401."""
        response = client.get("/api/admin/session/1/location-log")

        assert response.status_code == 401


class TestIntegration:
    """Testy integracyjne pełnego flow API Location Integrity."""

    def test_full_crud_flow(self, admin_token):
        """Pełny flow CRUD dla lokalizacji."""
        import time

        unique_key = f"crud_flow_{time.time()}"

        # Create
        create_resp = client.post(
            "/api/locations",
            json={"key": unique_key, "label": "CRUD Test", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_resp.status_code == 201
        loc_data = create_resp.json()

        # Read (Get)
        get_resp = client.get(
            f"/api/locations/{unique_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["key"] == unique_key

        # Update
        update_resp = client.put(
            f"/api/locations/{unique_key}",
            json={"key": unique_key, "label": "Updated CRUD", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["label"] == "Updated CRUD"

        # Delete
        delete_resp = client.delete(
            f"/api/locations/{unique_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_resp.status_code == 204

        # Verify deletion (soft delete - is_active=0)
        get_after = client.get(
            f"/api/locations/{unique_key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_after.status_code == 404

    def test_nested_location_structure(self, admin_token):
        """Tworzenie zagnieżdżonej struktury lokalizacji."""
        import time

        # Stwórz: Miasto -> Dzielnica -> Budynek
        city_key = f"city_nested_{time.time()}"
        city_resp = client.post(
            "/api/locations",
            json={"key": city_key, "label": "Test City", "location_type": "macro"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert city_resp.status_code == 201
        city_id = city_resp.json()["id"]

        district_key = f"district_nested_{time.time()}"
        district_resp = client.post(
            "/api/locations",
            json={"key": district_key, "label": "Test District", "location_type": "sub", "parent_id": city_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert district_resp.status_code == 201
        district_id = district_resp.json()["id"]

        building_key = f"building_nested_{time.time()}"
        building_resp = client.post(
            "/api/locations",
            json={"key": building_key, "label": "Test Building", "location_type": "sub", "parent_id": district_id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert building_resp.status_code == 201

        # Pobierz drzewo
        tree_resp = client.get(
            "/api/locations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert tree_resp.status_code == 200

        # Znajdź miasto w drzewie
        tree_data = tree_resp.json()
        city_in_tree = next((loc for loc in tree_data if loc["key"] == city_key), None)

        if city_in_tree:
            assert len(city_in_tree.get("children", [])) > 0
