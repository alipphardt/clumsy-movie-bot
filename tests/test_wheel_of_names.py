from wheel_of_names import (
    WHEEL_API_V3_URL,
    WHEEL_OF_NAMES_REJECTED_TERMS,
    WHEEL_SHARE_BASE_URL,
    build_delete_wheel_url,
    build_list_wheels_params,
    build_sanitized_wheel_title_lines,
    build_wheel_entries,
    build_wheel_payload,
    build_wheel_share_url,
    censor_vowels,
    extract_wheel_path,
    extract_wheel_paths,
    find_rejected_wheel_terms,
    sanitize_title_for_wheel,
)


def test_build_wheel_entries_uses_wheel_of_names_text_shape():
    weighted_titles = ["Movie A", "Movie A", "Movie B"]

    result = build_wheel_entries(weighted_titles)

    assert result == [
        {"text": "Movie A"},
        {"text": "Movie A"},
        {"text": "Movie B"},
    ]


def test_find_rejected_wheel_terms_matches_confirmed_terms_case_insensitively():
    titles = [
        "Goon",
        "They Saved Hitler's Brain",
        "Safe Movie",
    ]

    result = find_rejected_wheel_terms(titles)

    assert result == [
        {"title": "Goon", "terms": ["goon"]},
        {"title": "They Saved Hitler's Brain", "terms": ["hitler"]},
    ]


def test_find_rejected_wheel_terms_does_not_match_inside_larger_words():
    assert find_rejected_wheel_terms(["Lagoon"] , {"goon"}) == []


def test_censor_vowels_replaces_english_vowels_with_asterisks():
    assert censor_vowels("They Saved Hitler's Brain") == "Th*y S*v*d H*tl*r's Br**n"


def test_sanitize_title_for_wheel_censors_flagged_titles_only():
    assert sanitize_title_for_wheel("Goon") == "G**n"
    assert sanitize_title_for_wheel("Safe Movie") == "Safe Movie"


def test_build_wheel_entries_sanitizes_flagged_titles():
    weighted_titles = ["Goon", "Safe Movie", "They Saved Hitler's Brain"]

    result = build_wheel_entries(weighted_titles)

    assert result == [
        {"text": "G**n"},
        {"text": "Safe Movie"},
        {"text": "Th*y S*v*d H*tl*r's Br**n"},
    ]


def test_build_sanitized_wheel_title_lines_describes_sanitized_titles():
    result = build_sanitized_wheel_title_lines(["Goon", "Safe Movie"])

    assert result == ["- Goon -> G**n (matched: goon)\n"]


def test_wheel_of_names_rejected_terms_documents_confirmed_api_rejections():
    assert WHEEL_OF_NAMES_REJECTED_TERMS == {
        "hitler",
        "fuck",
        "pussy",
        "goon",
        "jizz",
        "tits",
    }


def test_build_wheel_payload_uses_bot_wheel_configuration():
    entries = [
        {"text": "Movie A"},
        {"text": "Movie B"},
    ]

    result = build_wheel_payload(entries)

    assert result == {
        "title": "Clumsy Movie Night",
        "description": "First movie to 3 spins wins. Click 'Copy this Wheel' to customize.",
        "shareMode": "copyable",
        "wheelConfigs": [{
            "title": "Clumsy Movie Night",
            "description": "First movie to 3 spins wins. Click 'Copy this Wheel' to customize.",
            "displayWinnerDialog": True,
            "allowDuplicates": True,
            "maxNames": 50,
            "entries": entries,
        }],
    }


def test_extract_wheel_path_returns_response_path():
    response_json = {"data": {"path": "abc-123"}}

    assert extract_wheel_path(response_json) == "abc-123"


def test_build_wheel_share_url_appends_path_to_base_url():
    assert build_wheel_share_url("abc-123") == WHEEL_SHARE_BASE_URL + "abc-123"


def test_build_list_wheels_params_requests_only_paths_by_default():
    assert build_list_wheels_params() == {"fields": "path"}


def test_extract_wheel_paths_returns_paths_from_list_response():
    response_json = {
        "data": {
            "wheels": [
                {"path": "abc-123"},
                {"path": "def-456"},
            ]
        }
    }

    assert extract_wheel_paths(response_json) == ["abc-123", "def-456"]


def test_build_delete_wheel_url_uses_v3_wheel_path_endpoint():
    assert build_delete_wheel_url("abc-123") == f"{WHEEL_API_V3_URL}/abc-123"
