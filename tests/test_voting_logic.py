from voting_logic import (
    build_weighted_wheel_titles,
    build_wheel_entries,
    build_wheel_text_chunks,
    calculate_vote_totals,
    classify_rollover_and_fallen,
    count_total_votes,
    merge_fallen_titles,
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


def test_build_wheel_entries_uses_wheel_of_names_text_shape():
    weighted_titles = ["Movie A", "Movie A", "Movie B"]

    result = build_wheel_entries(weighted_titles)

    assert result == [
        {"text": "Movie A"},
        {"text": "Movie A"},
        {"text": "Movie B"},
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


def test_build_wheel_text_chunks_formats_titles_like_wheel2_output():
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
