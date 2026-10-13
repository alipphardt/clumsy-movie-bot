---
name: clean-fallen-list
description: Identify and clean titles from fallen.csv that appear to have already been watched according to clumsy-movie-winners.csv. Use when reconciling The Fallen list against the winners list, especially when removals require one-at-a-time user approval.
---

# Clean Fallen List

You help reconcile `fallen.csv` against `clumsy-movie-winners.csv` in the clumsy-movie-bot repository.

## Goal

Find Fallen movies that may already have been watched and recorded in the winners list. Do not remove anything without explicit user approval.

## Default files

Use these files unless the user specifies alternatives:

- `clumsy-movie-winners.csv`
  - winner title column: `title`
- `fallen.csv`
  - fallen title column: `Movie`

## Helper script

A helper script is available at `scripts/clean_fallen_list.py` relative to this skill directory.

Use it from the repository root unless the user specifies alternate paths:

```bash
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py --no-fuzzy
```

Useful modes:

```bash
# Show exact and normalized candidates only
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py --no-fuzzy

# Include conservative fuzzy candidates
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py

# Emit candidate data as JSON
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py --json

# Apply approved removals listed one per line in a text file
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py --apply-approved /path/to/approved.txt

# Preview approved removals without writing
.agents/skills/clean-fallen-list/scripts/clean_fallen_list.py --apply-approved /path/to/approved.txt --dry-run
```

The script is only a helper. Still follow the approval workflow below: present candidates one at a time and do not apply removals without explicit user approval and final confirmation.

## Workflow

1. Read both CSV files or use the helper script to identify candidates.
2. Compare Fallen titles against winner titles.
3. Identify candidates using:
   - exact title match
   - normalized title match
   - fuzzy title match, if useful
4. Present candidates to the user one at a time.
5. For each candidate, show:
   - Fallen title
   - matched winner title
   - match type
   - confidence/reason
6. Ask the user whether to remove the Fallen title.
7. Accept simple responses:
   - `y`, `yes`, `remove` means approve removal
   - `n`, `no`, `keep` means reject removal
   - `stop`, `quit`, `cancel` means stop reviewing candidates
8. Track approved removals.
9. Before writing changes:
   - summarize approved removals
   - create a timestamped backup of `fallen.csv`
10. Edit only `fallen.csv`.
11. Preserve the CSV schema and column name `Movie`.

## Matching guidance

Normalize titles by:

- casefolding
- trimming whitespace
- collapsing repeated whitespace
- removing punctuation
- normalizing Unicode punctuation where practical
- removing a trailing year in parentheses, e.g. `(1994)`

Prefer exact and normalized matches over fuzzy matches.

Use fuzzy matching conservatively. Good reasons to propose a fuzzy match include:

- punctuation-only differences
- year suffix differences
- alternate spacing differences
- small typographical differences

Do not propose extremely weak fuzzy matches just to be exhaustive.

## Candidate review format

Use a compact one-at-a-time format like:

```text
Potential removal 1 of 4

Fallen:
  On Deadly Ground (1994, Seagal)

Matched winner:
  On Deadly Ground

Match:
  fuzzy title match, high confidence

Reason:
  normalized titles are very similar after removing year/extra descriptor text.

Remove this from fallen.csv? [y/n/stop]
```

Wait for the user's answer before showing the next candidate.

## Applying approved removals

After candidate review, if at least one removal was approved:

1. Show the approved removals.
2. Ask for final confirmation before modifying `fallen.csv`.
3. Create a backup named like:
   - `fallen.csv.bak-YYYYMMDD-HHMMSS`
4. Remove only the approved Fallen rows.
5. Write `fallen.csv` with the original `Movie` column.
6. Report:
   - number of rows removed
   - number of rows remaining
   - backup path

## Safety rules

- Never modify `clumsy-movie-winners.csv`.
- Never remove from `fallen.csv` without explicit user approval.
- Never write changes until the user gives final confirmation after review.
- If the user stops the workflow, do not write changes unless they explicitly ask to apply already-approved removals.
- Preserve all Fallen titles that were rejected or not reviewed.
- Preserve the order of remaining Fallen titles.
- If no candidates are found, report that no likely already-watched Fallen titles were identified.
