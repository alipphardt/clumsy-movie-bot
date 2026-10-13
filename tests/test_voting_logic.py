from datetime import datetime

from voting_logic import (
    DEFAULT_OLDEST_EXCLUDED_TITLES,
    build_holdover_titles,
    build_weighted_wheel_titles,
    build_wheel_text_chunks,
    calculate_vote_totals,
    classify_rollover_and_fallen,
    collect_current_nomination_titles,
    count_movie_nominations,
    count_total_votes,
    find_first_seen_titles,
    format_oldest_title_lines,
    merge_fallen_titles,
    top_oldest_titles,
)


def test_calculate_vote_totals_sums_multiple_reactions_and_skips_unreacted_nominations():
    messages = [
        {"content": "Movie A", "reaction_counts": [2, 1]},
        {"content": "Movie B", "reaction_counts": []},
        {"content": "Movie C", "reaction_counts": [4]},
    ]

    result = calculate_vote_totals(messages)

    assert result == [
        ("Movie A", 3),
        ("Movie C", 4),
    ]


def test_calculate_vote_totals_excludes_titles():
    messages = [
        {"content": "Winner Movie", "reaction_counts": [5]},
        {"content": "Movie A", "reaction_counts": [2]},
    ]

    result = calculate_vote_totals(messages, excluded_titles={"Winner Movie"})

    assert result == [("Movie A", 2)]


def test_calculate_vote_totals_preserves_duplicate_nominations():
    messages = [
        {"content": "Movie A", "reaction_counts": [2]},
        {"content": "Movie A", "reaction_counts": [3]},
    ]

    result = calculate_vote_totals(messages)

    assert result == [
        ("Movie A", 2),
        ("Movie A", 3),
    ]


def test_count_total_votes_sums_vote_totals_and_applies_exclusions():
    messages = [
        {"content": "Movie A", "reaction_counts": [2, 1]},
        {"content": "Movie B", "reaction_counts": [3]},
        {"content": "Excluded Movie", "reaction_counts": [10]},
        {"content": "Unreacted Movie", "reaction_counts": []},
    ]

    result = count_total_votes(messages, excluded_titles={"Excluded Movie"})

    assert result == 6


def test_count_movie_nominations_counts_messages_regardless_of_reactions():
    messages = [
        {"content": "Movie A", "reaction_counts": []},
        {"content": "Movie B", "reaction_counts": [2]},
        {"content": "Bot-generated rollover movie", "reaction_counts": []},
    ]

    assert count_movie_nominations(messages) == 3


def test_count_movie_nominations_excludes_next_week_header_by_default():
    messages = [
        {"content": "Next Week on the Wheel:", "reaction_counts": []},
        {"content": "Movie A", "reaction_counts": []},
    ]

    assert count_movie_nominations(messages) == 1


def test_count_movie_nominations_preserves_duplicate_nominations_as_separate_count():
    messages = [
        {"content": "Movie A", "reaction_counts": []},
        {"content": "Movie A", "reaction_counts": [1]},
    ]

    assert count_movie_nominations(messages) == 2


def test_count_movie_nominations_allows_custom_exclusions():
    messages = [
        {"content": "Skip Me", "reaction_counts": []},
        {"content": "Next Week on the Wheel:", "reaction_counts": []},
        {"content": "Movie A", "reaction_counts": []},
    ]

    assert count_movie_nominations(messages, excluded_titles={"Skip Me"}) == 2



def test_collect_current_nomination_titles_excludes_empty_and_configured_titles():
    messages = [
        {"content": ""},
        {"content": "Movie A"},
        {"content": "Winner"},
        {"content": "Next Week on the Wheel:"},
    ]

    result = collect_current_nomination_titles(
        messages,
        excluded_titles={"Winner"}.union(DEFAULT_OLDEST_EXCLUDED_TITLES),
    )

    assert result == {"Movie A"}


def test_collect_current_nomination_titles_includes_unreacted_and_collapses_duplicates():
    messages = [
        {"content": "Movie A", "reaction_counts": []},
        {"content": "Movie A", "reaction_counts": [2]},
        {"content": "Movie B", "reaction_counts": []},
    ]

    result = collect_current_nomination_titles(messages)

    assert result == {"Movie A", "Movie B"}


def test_find_first_seen_titles_returns_earliest_ordered_occurrence_for_current_titles():
    current_titles = {"Movie A", "Movie B"}
    messages = [
        {"content": "Movie B", "created_at": datetime(2020, 1, 2)},
        {"content": "Ignored Movie", "created_at": datetime(2020, 1, 3)},
        {"content": "Movie A", "created_at": datetime(2020, 1, 4)},
        {"content": "Movie A", "created_at": datetime(2021, 1, 1)},
    ]

    result = find_first_seen_titles(messages, current_titles)

    assert result == {
        "Movie B": datetime(2020, 1, 2),
        "Movie A": datetime(2020, 1, 4),
    }


def test_top_oldest_titles_sorts_by_timestamp_and_applies_limit():
    first_seen = {
        "Movie C": datetime(2020, 1, 3),
        "Movie A": datetime(2020, 1, 1),
        "Movie B": datetime(2020, 1, 2),
    }

    result = top_oldest_titles(first_seen, limit=2)

    assert result == [
        ("Movie A", datetime(2020, 1, 1)),
        ("Movie B", datetime(2020, 1, 2)),
    ]


def test_format_oldest_title_lines_uses_numbered_date_output():
    oldest_titles = [
        ("Movie A", datetime(2020, 1, 1)),
        ("Movie B", datetime(2020, 2, 3)),
    ]

    result = format_oldest_title_lines(oldest_titles)

    assert result == [
        "[1] Movie A (first seen: 2020-01-01)\n",
        "[2] Movie B (first seen: 2020-02-03)\n",
    ]

def test_build_holdover_titles_reuses_vote_eligibility_and_sorts_titles():
    messages = [
        {"content": "Movie C", "reaction_counts": [1]},
        {"content": "Movie A", "reaction_counts": [2]},
        {"content": "Unreacted Movie", "reaction_counts": []},
        {"content": "Excluded Movie", "reaction_counts": [5]},
    ]

    result = build_holdover_titles(messages, excluded_titles={"Excluded Movie"})

    assert result == ["Movie A", "Movie C"]


def test_build_holdover_titles_preserves_duplicate_nominations():
    messages = [
        {"content": "Movie B", "reaction_counts": [1]},
        {"content": "Movie A", "reaction_counts": [2]},
        {"content": "Movie A", "reaction_counts": [3]},
    ]

    result = build_holdover_titles(messages)

    assert result == ["Movie A", "Movie A", "Movie B"]


def test_build_weighted_wheel_titles_repeats_titles_by_vote_count_in_order():
    vote_totals = [
        ("Movie A", 3),
        ("Movie B", 1),
    ]

    result = build_weighted_wheel_titles(vote_totals)

    assert result == [
        "Movie A",
        "Movie A",
        "Movie A",
        "Movie B",
    ]


def test_build_weighted_wheel_titles_preserves_duplicate_title_entries():
    vote_totals = [
        ("Movie A", 2),
        ("Movie A", 1),
    ]

    result = build_weighted_wheel_titles(vote_totals)

    assert result == [
        "Movie A",
        "Movie A",
        "Movie A",
    ]


def test_vote_totals_to_weighted_titles_preserves_exclusions_and_duplicate_nominations():
    messages = [
        {"content": "Movie A", "reaction_counts": [2]},
        {"content": "Movie A", "reaction_counts": [1]},
        {"content": "Excluded Movie", "reaction_counts": [5]},
        {"content": "Unreacted Movie", "reaction_counts": []},
    ]

    vote_totals = calculate_vote_totals(messages, excluded_titles={"Excluded Movie"})
    result = build_weighted_wheel_titles(vote_totals)

    assert result == [
        "Movie A",
        "Movie A",
        "Movie A",
    ]


def test_build_wheel_text_chunks_formats_titles_like_wheel_fallback_output():
    vote_totals = [
        ("Movie A", 2),
        ("Movie B", 1),
    ]

    result = build_wheel_text_chunks(vote_totals)

    assert result == ["Movie A\nMovie A\nMovie B\n"]


def test_build_wheel_text_chunks_splits_when_next_block_would_reach_max_length():
    vote_totals = [
        ("AAAA", 1),  # "AAAA\n" length 5
        ("BBBB", 1),  # current + next is exactly 10
    ]

    result = build_wheel_text_chunks(vote_totals, max_length=10)

    assert result == [
        "AAAA\n",
        "BBBB\n",
    ]


def test_build_wheel_text_chunks_preserves_empty_final_chunk_for_no_entries():
    assert build_wheel_text_chunks([]) == [""]


def test_build_wheel_text_chunks_preserves_empty_chunk_when_first_block_reaches_limit():
    vote_totals = [("AAAA", 1)]  # "AAAA\n" length 5

    result = build_wheel_text_chunks(vote_totals, max_length=5)

    assert result == ["", "AAAA\n"]


def test_classify_rollover_and_fallen_rolls_over_titles_with_two_unique_voters():
    nominations = [
        {"content": "Movie A", "unique_voter_count": 2},
        {"content": "Movie B", "unique_voter_count": 3},
    ]

    rollover, fallen = classify_rollover_and_fallen(nominations)

    assert rollover == ["Movie A", "Movie B"]
    assert fallen == []


def test_classify_rollover_and_fallen_sends_one_or_zero_voter_titles_to_fallen():
    nominations = [
        {"content": "Movie A", "unique_voter_count": 1},
        {"content": "Movie B", "unique_voter_count": 0},
    ]

    rollover, fallen = classify_rollover_and_fallen(nominations)

    assert rollover == []
    assert fallen == ["Movie A", "Movie B"]


def test_classify_rollover_and_fallen_excludes_titles_from_both_outputs():
    nominations = [
        {"content": "Winner", "unique_voter_count": 2},
        {"content": "Movie A", "unique_voter_count": 1},
    ]

    rollover, fallen = classify_rollover_and_fallen(
        nominations,
        excluded_titles={"Winner"},
    )

    assert rollover == []
    assert fallen == ["Movie A"]


def test_classify_rollover_and_fallen_ignores_default_control_messages_only_for_fallen():
    nominations = [
        {"content": "Next Week on the Wheel:", "unique_voter_count": 0},
        {"content": ".rollover", "unique_voter_count": 1},
        {"content": "Movie A", "unique_voter_count": 1},
    ]

    rollover, fallen = classify_rollover_and_fallen(nominations)

    assert rollover == []
    assert fallen == ["Movie A"]


def test_classify_rollover_and_fallen_preserves_control_message_rollover_behavior():
    nominations = [
        {"content": "Next Week on the Wheel:", "unique_voter_count": 2},
        {"content": ".rollover", "unique_voter_count": 2},
    ]

    rollover, fallen = classify_rollover_and_fallen(nominations)

    assert rollover == ["Next Week on the Wheel:", ".rollover"]
    assert fallen == []


def test_classify_rollover_and_fallen_preserves_duplicate_rollover_and_fallen_titles():
    nominations = [
        {"content": "Movie A", "unique_voter_count": 2},
        {"content": "Movie A", "unique_voter_count": 2},
        {"content": "Movie B", "unique_voter_count": 1},
        {"content": "Movie B", "unique_voter_count": 0},
    ]

    rollover, fallen = classify_rollover_and_fallen(nominations)

    assert rollover == ["Movie A", "Movie A"]
    assert fallen == ["Movie B", "Movie B"]


def test_classify_rollover_and_fallen_distinguishes_empty_ignored_titles_from_none():
    nominations = [
        {"content": "Next Week on the Wheel:", "unique_voter_count": 0},
        {"content": ".rollover", "unique_voter_count": 0},
    ]

    rollover, fallen = classify_rollover_and_fallen(
        nominations,
        ignored_fallen_titles=set(),
    )

    assert rollover == []
    assert fallen == ["Next Week on the Wheel:", ".rollover"]


def test_merge_fallen_titles_deduplicates_and_sorts_existing_and_new_titles():
    result = merge_fallen_titles(
        existing_fallen_titles=["Movie C", "Movie A"],
        new_fallen_titles=["Movie B", "Movie A", "Movie B"],
    )

    assert result == ["Movie A", "Movie B", "Movie C"]
