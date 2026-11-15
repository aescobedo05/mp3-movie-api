import pytest

from src import MovieStorage
import main


def test_movies_persist(client, test_storage, uploaded_movies):
    reopened = MovieStorage(test_storage.db_path)
    movie = reopened.get()
    movie_count = reopened.count_movies()
    assert movie_count == 20
    assert set(movie.columns) == {"title", "release_year", "rating", "genre"}
    expected_titles = [
        "Movie A", "Movie B", "Movie B", "Movie C", "Movie D", "Movie D",
        "Movie E", "Movie F", "Movie G", "Movie H", "Movie I", "Movie J",
        "Movie K", "Movie L", "Movie M", "Movie N", "Movie O", "Movie P",
        "Movie Q", "Movie R",
    ]
    assert movie["title"].tolist() == expected_titles

    stored_ids = [
        row["id"] for row in reopened.select_columns(["title"], limit=100)
    ]
    response = client.get("/movies?limit=100")
    assert response.status_code == 200
    api_ids = [row["id"] for row in response.json()["data"]]
    assert stored_ids == api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200
    assert main.cache.get(100)

    second = client.get("/movies", params={"limit": 1})
    assert second.status_code == 200
    assert main.cache.get(1)

    third = client.get("/movies", params={"limit": 100})
    assert third.status_code == 200
    assert main.cache.get(100)

    response = client.post("/movies/process", json=processing_body)
    assert response.status_code == 200

    result = response.json()
    assert result["validation_rows_removed"] == 0
    assert result["cleaning_report"]["row_before"] == 20
    assert result["cleaning_report"]["rows_after"] == 16
    assert result["cleaning_report"]["rows_removed"] == 4

    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    refreshed = client.get("/movies", params={"limit": 100})
    assert refreshed.status_code == 200

    data = refreshed.json()
    assert data["total_rows"] == 16

    records = data["data"]
    expected_titles = [
        "Movie A", "Movie B", "Movie C", "Movie D", "Movie E", "Movie F", 
        "Movie G", "Movie H", "Movie I", "Movie J", "Movie K", "Movie L", 
        "Movie M", "Movie N", "Movie O", "Movie P"
    ]
    assert [row["title"] for row in records] == expected_titles
    assert [row["id"] for row in records] == list(range(1, 17))
    assert main.cache.get(100) == data


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200
    assert main.cache.get(100)

    def fail_if_called(*args, **kwargs):
        pytest.fail("A cache hit should not query the database")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()
