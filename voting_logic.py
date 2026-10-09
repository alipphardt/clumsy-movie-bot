"""Pure voting helpers for Clumsy Movie Bot.

This module intentionally avoids importing discord.py or accessing external
services so vote-counting behavior can be tested independently.
"""


def calculate_vote_totals(messages, excluded_titles=None):
    """Return vote totals for reacted nominations.

    Args:
        messages: Iterable of dictionaries with ``content`` and
            ``reaction_counts`` keys. ``reaction_counts`` should be a list of
            reaction counts exactly as reported by Discord.
        excluded_titles: Optional iterable of movie titles to skip.

    Returns:
        A list of ``(title, vote_count)`` tuples. Duplicate nominations are
        preserved as separate entries, matching the original Discord handler
        behavior.
    """
    excluded_titles = set(excluded_titles or [])
    votes = []

    for message in messages:
        content = message["content"]
        reaction_counts = message["reaction_counts"]

        if len(reaction_counts) > 0 and content not in excluded_titles:
            votes.append((content, sum(reaction_counts)))

    return votes


def count_total_votes(messages, excluded_titles=None):
    """Return the total number of votes across reacted nominations."""
    return sum(vote_count for _, vote_count in calculate_vote_totals(messages, excluded_titles))


def build_weighted_wheel_titles(vote_totals):
    """Return movie titles repeated once per vote.

    Args:
        vote_totals: Iterable of ``(title, vote_count)`` tuples.

    Returns:
        A list of titles suitable for Wheel of Names weighting. Duplicate title
        entries are preserved, matching the original handler behavior.
    """
    weighted_titles = []

    for title, vote_count in vote_totals:
        for _ in range(vote_count):
            weighted_titles.append(title)

    return weighted_titles


def build_wheel_entries(weighted_titles):
    """Return Wheel of Names entry dictionaries for weighted titles."""
    entries = []

    for title in weighted_titles:
        entries.append({'text': title})

    return entries


def build_wheel_text_chunks(vote_totals, max_length=2000):
    """Return Discord message chunks for a text wheel list.

    This preserves the existing .wheel2/fallback behavior: each movie is added
    as a repeated block of ``"<title>\n"`` lines, and the current chunk is
    emitted when adding the next block would make its length greater than or
    equal to ``max_length``.
    """
    chunks = []
    wheel_list = ""

    for title, vote_count in vote_totals:
        next_block = (title + "\n") * vote_count

        if len(wheel_list + next_block) >= max_length:
            chunks.append(wheel_list)
            wheel_list = ""

        wheel_list = wheel_list + next_block

    chunks.append(wheel_list)

    return chunks


def classify_rollover_and_fallen(
    nominations,
    excluded_titles=None,
    ignored_fallen_titles=None,
    minimum_unique_voters=2,
):
    """Classify nominations into rollover and fallen title lists.

    Args:
        nominations: Iterable of dictionaries with ``content`` and
            ``unique_voter_count`` keys.
        excluded_titles: Optional iterable of titles to skip entirely.
        ignored_fallen_titles: Optional iterable of titles to omit from the
            fallen list. ``None`` uses the current default control messages;
            an explicitly empty collection ignores nothing.
        minimum_unique_voters: Number of unique voters required for rollover.

    Returns:
        ``(rollover_titles, fallen_titles)``. Duplicate nominations are
        preserved during classification, matching the original handler
        behavior.
    """
    excluded_titles = set(excluded_titles or [])

    if ignored_fallen_titles is None:
        ignored_fallen_titles = {"Next Week on the Wheel:", ".rollover"}
    else:
        ignored_fallen_titles = set(ignored_fallen_titles)

    rollover_titles = []
    fallen_titles = []

    for nomination in nominations:
        content = nomination["content"]
        unique_voter_count = nomination["unique_voter_count"]

        if content in excluded_titles:
            continue

        if unique_voter_count >= minimum_unique_voters:
            rollover_titles.append(content)
        elif content not in ignored_fallen_titles:
            fallen_titles.append(content)

    return rollover_titles, fallen_titles


def merge_fallen_titles(existing_fallen_titles, new_fallen_titles):
    """Return sorted unique fallen titles from existing and new titles."""
    return sorted(set(existing_fallen_titles).union(new_fallen_titles))
