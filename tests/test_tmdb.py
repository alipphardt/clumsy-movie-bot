from tmdb import (
    TMDB_API_BASE_URL,
    TMDB_IMAGE_BASE_URL,
    TMDB_WEB_BASE_URL,
    build_auth_headers,
    build_find_by_imdb_id_url,
    build_movie_details_url,
    build_poster_url,
    build_search_movie_url,
    build_tmdb_movie_url,
    extract_first_movie_result_id,
    format_search_result_title,
    format_search_results_message,
    is_random_candidate_allowed,
    parse_movie_summary,
    parse_search_results,
)


def test_build_auth_headers_uses_bearer_token():
    assert build_auth_headers("token-123") == {"Authorization": "Bearer token-123"}


def test_build_search_movie_url_quotes_query():
    assert build_search_movie_url("Lair of the White Worm") == (
        f"{TMDB_API_BASE_URL}/search/movie?query=Lair%20of%20the%20White%20Worm"
    )


def test_build_movie_details_url_uses_movie_id():
    assert build_movie_details_url(123) == f"{TMDB_API_BASE_URL}/movie/123"


def test_build_find_by_imdb_id_url_uses_imdb_id():
    assert build_find_by_imdb_id_url("tt1234567") == f"{TMDB_API_BASE_URL}/find/tt1234567"


def test_build_tmdb_movie_url_uses_public_movie_url():
    assert build_tmdb_movie_url(123) == f"{TMDB_WEB_BASE_URL}123"


def test_build_poster_url_uses_original_image_base_url():
    assert build_poster_url("/poster.jpg") == f"{TMDB_IMAGE_BASE_URL}/poster.jpg"


def test_build_poster_url_returns_empty_string_without_path():
    assert build_poster_url("") == ""
    assert build_poster_url(None) == ""


def test_format_search_result_title_uses_title_and_release_year():
    movie = {"title": "Movie A", "release_date": "1984-01-02"}

    assert format_search_result_title(movie) == "Movie A (1984)"


def test_format_search_result_title_preserves_current_fallbacks():
    assert format_search_result_title({}) == "N/A (N/A)"


def test_parse_search_results_returns_stored_movie_shape_and_limit():
    data = {
        "results": [
            {"title": "Movie A", "release_date": "1984-01-02", "id": 1},
            {"title": "Movie B", "release_date": "1990-03-04", "id": 2},
            {"title": "Movie C", "release_date": "2000-05-06", "id": 3},
        ]
    }

    result = parse_search_results(data, limit=2)

    assert result == [
        {"title": "Movie A (1984)", "id": 1},
        {"title": "Movie B (1990)", "id": 2},
    ]


def test_parse_search_results_preserves_missing_id_fallback():
    data = {"results": [{"title": "Movie A", "release_date": "1984-01-02"}]}

    assert parse_search_results(data) == [{"title": "Movie A (1984)", "id": ""}]


def test_format_search_results_message_matches_tmdb_command_output():
    search_results = [
        {"title": "Movie A (1984)", "id": 1},
        {"title": "Movie B (1990)", "id": 2},
    ]

    assert format_search_results_message(search_results) == (
        "Top 10 Search Results from TMDB:\n"
        "[1] Movie A (1984)\n"
        "[2] Movie B (1990)\n"
    )


def test_parse_movie_summary_returns_embed_fields_and_poster_url():
    movie = {
        "title": "Movie A",
        "overview": "Description",
        "release_date": "1984-01-02",
        "runtime": 90,
        "poster_path": "/poster.jpg",
    }

    result = parse_movie_summary(movie)

    assert result == {
        "title": "Movie A",
        "description": "Description",
        "release_date": "1984-01-02",
        "runtime": "90",
        "poster_path": "/poster.jpg",
        "poster_url": f"{TMDB_IMAGE_BASE_URL}/poster.jpg",
    }


def test_parse_movie_summary_preserves_current_fallbacks():
    result = parse_movie_summary({})

    assert result == {
        "title": "Unavailable",
        "description": ["Unavailable"],
        "release_date": "N/A",
        "runtime": "N/A",
        "poster_path": "",
        "poster_url": "",
    }


def test_extract_first_movie_result_id_returns_first_result_id():
    response = {"movie_results": [{"id": 123}, {"id": 456}]}

    assert extract_first_movie_result_id(response) == 123


def test_is_random_candidate_allowed_accepts_non_adult_movie_from_1950_or_later():
    assert is_random_candidate_allowed({"adult": False, "release_date": "1950-01-01"})
    assert is_random_candidate_allowed({"adult": False, "release_date": "2000-01-01"})


def test_is_random_candidate_allowed_rejects_adult_movie():
    assert not is_random_candidate_allowed({"adult": True, "release_date": "2000-01-01"})


def test_is_random_candidate_allowed_rejects_pre_1950_movie():
    assert not is_random_candidate_allowed({"adult": False, "release_date": "1949-01-01"})


def test_is_random_candidate_allowed_rejects_missing_release_date_like_current_logic():
    assert not is_random_candidate_allowed({"adult": False})
