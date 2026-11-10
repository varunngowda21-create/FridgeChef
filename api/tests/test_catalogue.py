from fastapi.testclient import TestClient


def test_list_ingredients_basic(client: TestClient):
    response = client.get("/api/v1/ingredients?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 10
    assert data["next_cursor"] is not None

    # Verify ingredient structure
    item = data["items"][0]
    assert "id" in item
    assert "display_name" in item
    assert "category" in item
    assert "aliases" in item
    assert "shelf_life" in item
    assert isinstance(item["shelf_life"], list)
    assert len(item["shelf_life"]) > 0


def test_list_ingredients_filter_category(client: TestClient):
    response = client.get("/api/v1/ingredients?category=Vegetables&limit=50")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["category"].lower() == "vegetables"


def test_list_ingredients_search_query(client: TestClient):
    response = client.get("/api/v1/ingredients?query=paneer")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    found = any("paneer" in item["id"] or "paneer" in item["display_name"].lower() for item in data["items"])
    assert found


def test_list_ingredients_pagination(client: TestClient):
    # Fetch page 1
    res1 = client.get("/api/v1/ingredients?limit=5")
    assert res1.status_code == 200
    data1 = res1.json()
    cursor = data1["next_cursor"]
    assert cursor is not None
    page1_ids = [item["id"] for item in data1["items"]]

    # Fetch page 2 using cursor
    res2 = client.get(f"/api/v1/ingredients?limit=5&cursor={cursor}")
    assert res2.status_code == 200
    data2 = res2.json()
    page2_ids = [item["id"] for item in data2["items"]]

    # No overlap
    assert len(set(page1_ids).intersection(set(page2_ids))) == 0


def test_get_recipe_by_id(client: TestClient):
    response = client.get("/api/v1/recipes/dal_tadka")
    assert response.status_code == 200
    recipe = response.json()
    assert recipe["id"] == "dal_tadka"
    assert recipe["title"] == "Restaurant Style Dal Tadka"
    assert recipe["base_servings"] == 4
    assert recipe["scaled_servings"] == 4
    assert len(recipe["steps"]) >= 3
    assert len(recipe["ingredients"]) > 0
    assert "nutrition_per_serving" in recipe
    assert recipe["nutrition_per_serving"]["kcal"] > 0


def test_get_recipe_servings_scaling(client: TestClient):
    # Base servings for dal_tadka is 4, base toor_dal qty is 150g
    res_base = client.get("/api/v1/recipes/dal_tadka")
    assert res_base.status_code == 200
    base_data = res_base.json()
    base_toor = next(i for i in base_data["ingredients"] if i["canonical_id"] == "toor_dal")
    assert base_toor["qty"] == 150.0

    # Scale to 8 servings (double)
    res_scaled = client.get("/api/v1/recipes/dal_tadka?servings=8")
    assert res_scaled.status_code == 200
    scaled_data = res_scaled.json()
    assert scaled_data["scaled_servings"] == 8
    scaled_toor = next(i for i in scaled_data["ingredients"] if i["canonical_id"] == "toor_dal")
    assert scaled_toor["qty"] == 300.0


def test_get_recipe_not_found(client: TestClient):
    response = client.get("/api/v1/recipes/non_existent_recipe_slug")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RECIPE_NOT_FOUND"
    assert "request_id" in data["error"]
