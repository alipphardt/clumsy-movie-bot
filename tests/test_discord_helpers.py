from discord_helpers import chunk_lines


def test_chunk_lines_returns_single_chunk_when_under_limit():
    result = chunk_lines("Header\n", ["A\n", "B\n"], max_length=20)

    assert result == ["Header\nA\nB\n"]


def test_chunk_lines_splits_when_next_line_would_exceed_limit():
    result = chunk_lines("Head\n", ["AAAA\n", "BBBB\n"], max_length=10)

    assert result == [
        "Head\nAAAA\n",
        "BBBB\n",
    ]


def test_chunk_lines_does_not_split_when_next_line_exactly_reaches_limit():
    result = chunk_lines("Head\n", ["AAAA\n"], max_length=10)

    assert result == ["Head\nAAAA\n"]


def test_chunk_lines_does_not_repeat_header_after_split():
    result = chunk_lines("Header\n", ["AAAA\n", "BBBB\n"], max_length=12)

    assert result == [
        "Header\nAAAA\n",
        "BBBB\n",
    ]


def test_chunk_lines_returns_header_for_empty_lines():
    assert chunk_lines("Header\n", [], max_length=10) == ["Header\n"]
