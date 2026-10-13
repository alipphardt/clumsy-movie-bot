# Clumsy Movie Bot Refactor Notes

## Purpose

The refactor has focused on making the bot easier to maintain, test, and safely operate during movie night. The main pattern is to keep Discord command handlers responsible for I/O while moving deterministic rules and service-specific formatting into small helper modules.

Command handlers should generally:

1. Read Discord messages/reactions or CSV-backed state.
2. Convert framework objects into plain Python data.
3. Call pure helper functions.
4. Perform side effects such as Discord sends, CSV writes, HTTP requests, or image generation.

## Significant Changes Made

### Business logic extraction

Voting, wheel, rollover, holdover, movie-count, and oldest-title rules have been extracted into `voting_logic.py`.

Notable extracted behavior includes:

- vote total calculation from Discord reaction counts
- total vote counting
- movie nomination counting since rollover
- weighted Wheel of Names title expansion
- manual wheel fallback text chunking
- holdover eligibility
- rollover vs. Fallen classification
- Fallen-list merge/deduplication
- `.oldest` title collection, first-seen lookup, sorting, and output formatting

These helpers are Discord-independent and covered by unit tests.

### Service-specific helper modules

Wheel of Names helper logic now lives in `wheel_of_names.py`:

- v3 API constants
- entry and payload construction
- share/list/delete URL helpers
- response path extraction
- local title sanitization for terms known to be rejected by Wheel of Names

TMDB helper logic now lives in `tmdb.py`:

- auth header construction
- search/details/find URL construction
- TMDB web/poster URL construction
- search result parsing and formatting
- movie summary parsing
- random-candidate filtering

HTTP requests remain in `clumsy-movie-bot.py` for now, keeping external side effects at the command-handler boundary.

### Discord formatting helpers

`discord_helpers.py` contains framework-free Discord formatting helpers, currently including:

- `chunk_lines()` for splitting long output into Discord-safe message chunks

This is used by longer text-output commands such as `.oldest`, `.winners`, and `.fallen`.

### Command behavior improvements

The following command-level behavior has been improved:

- `.wheel2` was removed; `.wheel` now provides fallback text output when the Wheel of Names API fails.
- `.wheel` and `.wheel_fallen` use Wheel of Names v3 payload helpers.
- `.wheel` and `.wheel_fallen` sanitize known Wheel of Names rejected terms by replacing vowels with asterisks before submission.
- `.wheel_purge` uses Wheel of Names v3 list/delete helpers.
- `.tally` now handles the no-votes/no-nominations case gracefully.
- `.tally` graph generation now uses explicit figure/axis handling, bounded figure height, higher DPI output, tighter bounding boxes, and closes figures after saving.
- `.oldest` uses pure helper logic and still stops scanning history once all current titles have been found.
- `.moviecount` counts nominations since last rollover, excluding the rollover header.
- `.holdover` updates the in-memory `holdover_df` after writing `holdover.csv`, so `.print_holdover` works without a restart.
- `.samples` can only be invoked from `DISCORD_TERMINAL_CHANNEL` and writes sample nominations to `DISCORD_TEST_CHANNEL`.
- `.bingo` now saves scorecards as PNG, uses `fig.savefig()`, saves at 150 DPI with `bbox_inches="tight"`, and closes figures after saving.

### Startup/data loading cleanup

Startup and global state handling have been incrementally cleaned up:

- `main()` guards `client.run(TOKEN)`.
- `load_config()` centralizes environment-variable parsing.
- `load_dataframes()` centralizes CSV-backed dataframe loading.
- dataframe globals now consistently use `_df` suffixes, such as `fallen_df`, `holdover_df`, `winners_df`, and `bmovies_df`.

### Fallen-list maintenance skill

A project-local Pi skill was added inside the `clumsy-movie-bot` repository at:

```text
.agents/skills/clean-fallen-list/SKILL.md
```

It supports safely reconciling `fallen.csv` against `clumsy-movie-winners.csv` with one-at-a-time user approval before removing titles.

A helper script lives with the skill at:

```text
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py
```

The script can identify exact/normalized/fuzzy candidates and apply explicitly approved removals with a timestamped backup.

### Fallen-list cleanup performed

The following already-watched titles were removed from `fallen.csv` after explicit approval:

- `Arena`
- `Earth Girls are Easy`
- `Hackers`
- `Lair of the White Worm`
- `Sinners`
- `Surrogates`
- `Titane (2021)`
- `Xtro (1982)`

A backup was created before modification.

## Tests and Verification

Focused unit tests now cover extracted helper behavior in:

- `tests/test_voting_logic.py`
- `tests/test_wheel_of_names.py`
- `tests/test_tmdb.py`
- `tests/test_discord_helpers.py`

Latest focused test run:

```bash
python -m pytest tests/test_wheel_of_names.py tests/test_voting_logic.py tests/test_tmdb.py tests/test_discord_helpers.py
```

Result:

```text
68 passed
```

Syntax verification has also been run with:

```bash
python -m py_compile voting_logic.py wheel_of_names.py tmdb.py discord_helpers.py clumsy-movie-bot.py
```

## Current Boundaries

Current good boundaries:

- Pure voting/rollover/oldest rules live in `voting_logic.py`.
- Wheel of Names payload/URL/sanitization helpers live in `wheel_of_names.py`.
- TMDB URL/parsing helpers live in `tmdb.py`.
- Discord message formatting helpers live in `discord_helpers.py`.
- Discord object handling, CSV writes, image generation, and HTTP requests remain in `clumsy-movie-bot.py`.

## Remaining Opportunities

Potential future improvements:

1. Add `.status`, `.preview_wheel`, and `.preview_rollover` commands to reduce live-operation risk.
2. Continue reducing import-time side effects by moving environment loading, CSV loading, and bot construction behind a factory or `main()` path.
3. Consider small HTTP client wrappers for Wheel of Names and TMDB only if request logic grows.
4. Add command-handler integration tests after import-time side effects are reduced.
5. Consider in-memory image generation for `.tally` and `.bingo` to avoid fixed filenames.

Wait for explicit instruction before making further code changes.
