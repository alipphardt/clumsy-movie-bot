"""Pure voting helpers for Clumsy Movie Bot.

This module intentionally avoids importing discord.py or accessing external
services so vote-counting behavior can be tested independently.
"""


DEFAULT_OLDEST_EXCLUDED_TITLES = {
    "Random b-movie (by bot)",
    "Next Week on the Wheel:",
    "Random movie from The Fallen List",
}


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


def build_holdover_titles(messages, excluded_titles=None):
    """Return sorted titles eligible for the holdover list.

    Holdover eligibility matches vote-total eligibility: a nomination must have
    at least one reaction and must not be in the excluded title list. Duplicate
    nominations are preserved, matching the original handler behavior.
    """
    return sorted(title for title, _ in calculate_vote_totals(messages, excluded_titles))


def count_movie_nominations(messages, excluded_titles=None):
    """Return the count of movie nomination messages.

    Movie count intentionally does not require reactions. Bot-generated rollover
    nominations count as movie nominations. By default, only the rollover header
    message is excluded.
    """
    if excluded_titles is None:
        excluded_titles = {"Next Week on the Wheel:"}
    else:
        excluded_titles = set(excluded_titles)

    return sum(1 for message in messages if message["content"] not in excluded_titles)


def collect_current_nomination_titles(messages, excluded_titles=None):
    """Return unique current nomination titles from message records.

    This is used by the oldest-nominations command. It intentionally does not
    require reactions; unvoted nominations still count as current nominations.
    """
    excluded_titles = set(excluded_titles or [])
    current_titles = set()

    for message in messages:
        content = message["content"]

        if content and content not in excluded_titles:
            current_titles.add(content)

    return current_titles


def find_first_seen_titles(messages, current_titles):
    """Return earliest timestamps for current titles from ordered messages.

    ``messages`` should be supplied in oldest-first order. Each message record
    must contain ``content`` and ``created_at`` keys.
    """
    current_titles = set(current_titles)
    first_seen = {}

    for message in messages:
        content = message["content"]

        if content in current_titles and content not in first_seen:
            first_seen[content] = message["created_at"]

        if len(first_seen) == len(current_titles):
            break

    return first_seen


def top_oldest_titles(first_seen, limit=10):
    """Return ``(title, timestamp)`` pairs sorted by oldest timestamp."""
    return sorted(first_seen.items(), key=lambda x: x[1])[:limit]


def format_oldest_title_lines(oldest_titles):
    """Return Discord output lines for oldest-title results."""
    lines = []

    for i, (movie, timestamp) in enumerate(oldest_titles):
        date_str = timestamp.strftime("%Y-%m-%d")
        lines.append(f"[{i+1}] {movie} (first seen: {date_str})\n")

    return lines


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


def build_wheel_text_chunks(vote_totals, max_length=2000):
    """Return Discord message chunks for a text wheel list.

    This preserves the existing .wheel fallback behavior: each movie is added
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
