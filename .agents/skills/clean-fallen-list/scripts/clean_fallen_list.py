#!/usr/bin/env python3
"""Helpers for reconciling The Fallen list against watched winners.

This script is intended to support the clean-fallen-list skill. It can identify
candidate Fallen rows that appear in the winners list, and it can apply an
explicitly approved removal list with a timestamped backup.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_WINNERS_PATH = Path("clumsy-movie-winners.csv")
DEFAULT_FALLEN_PATH = Path("fallen.csv")
DEFAULT_WINNER_COLUMN = "title"
DEFAULT_FALLEN_COLUMN = "Movie"


@dataclass(frozen=True)
class Candidate:
    fallen_row: int
    fallen_title: str
    winner_title: str
    match_type: str
    confidence: str
    score: float
    reason: str


def normalize_unicode(text: str) -> str:
    """Normalize Unicode punctuation/accents where practical."""
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(character for character in normalized if not unicodedata.combining(character))


def normalize_basic_title(title: str) -> str:
    """Normalize title for high-confidence year/punctuation/case matching."""
    title = normalize_unicode(title).casefold().strip()
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def normalize_title(title: str) -> str:
    """Normalize title for conservative fuzzy matching."""
    title = normalize_unicode(title).casefold().strip()
    title = re.sub(r"\s*\(\d{4}(?:[^)]*)?\)\s*$", "", title)
    title = re.sub(r"\b(?:the|a|an)\b", " ", title)
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def require_column(rows: list[dict[str, str]], column: str, path: Path) -> None:
    if not rows:
        return
    if column not in rows[0]:
        raise ValueError(f"{path} does not contain required column: {column}")


def unique_titles(rows: list[dict[str, str]], column: str) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()

    for row in rows:
        title = (row.get(column) or "").strip()
        if not title or title in seen:
            continue
        titles.append(title)
        seen.add(title)

    return titles


def find_candidates(
    winners_rows: list[dict[str, str]],
    fallen_rows: list[dict[str, str]],
    winner_column: str = DEFAULT_WINNER_COLUMN,
    fallen_column: str = DEFAULT_FALLEN_COLUMN,
    fuzzy: bool = True,
) -> list[Candidate]:
    """Return likely Fallen removals, sorted by Fallen row order."""
    winner_titles = unique_titles(winners_rows, winner_column)
    exact_winners = {title.casefold().strip(): title for title in winner_titles}

    basic_winners: dict[str, str] = {}
    normalized_winners: dict[str, str] = {}

    for title in winner_titles:
        basic_winners.setdefault(normalize_basic_title(title), title)
        normalized_winners.setdefault(normalize_title(title), title)

    candidates: list[Candidate] = []
    matched_pairs: set[tuple[str, str]] = set()

    for row_number, row in enumerate(fallen_rows, start=1):
        fallen_title = (row.get(fallen_column) or "").strip()
        if not fallen_title:
            continue

        exact_key = fallen_title.casefold().strip()
        if exact_key in exact_winners:
            winner_title = exact_winners[exact_key]
            candidates.append(Candidate(
                row_number,
                fallen_title,
                winner_title,
                "exact title match",
                "high",
                1.0,
                "case-insensitive titles match exactly",
            ))
            matched_pairs.add((fallen_title, winner_title))
            continue

        basic_key = normalize_basic_title(fallen_title)
        if basic_key in basic_winners:
            winner_title = basic_winners[basic_key]
            candidates.append(Candidate(
                row_number,
                fallen_title,
                winner_title,
                "normalized title match",
                "high",
                0.98,
                "matches after case, punctuation, and trailing-year normalization",
            ))
            matched_pairs.add((fallen_title, winner_title))
            continue

        normalized_key = normalize_title(fallen_title)
        if normalized_key in normalized_winners:
            winner_title = normalized_winners[normalized_key]
            candidates.append(Candidate(
                row_number,
                fallen_title,
                winner_title,
                "normalized title match",
                "high",
                0.96,
                "matches after article, punctuation, and year normalization",
            ))
            matched_pairs.add((fallen_title, winner_title))

    if fuzzy:
        winner_norms = [(normalize_title(title), title) for title in winner_titles]

        for row_number, row in enumerate(fallen_rows, start=1):
            fallen_title = (row.get(fallen_column) or "").strip()
            fallen_norm = normalize_title(fallen_title)
            if not fallen_norm or len(fallen_norm) < 5:
                continue

            best: tuple[float, str, str, bool] | None = None

            for winner_norm, winner_title in winner_norms:
                if not winner_norm or len(winner_norm) < 5:
                    continue
                if (fallen_title, winner_title) in matched_pairs:
                    continue

                ratio = difflib.SequenceMatcher(None, fallen_norm, winner_norm).ratio()
                containment = (
                    (fallen_norm in winner_norm or winner_norm in fallen_norm)
                    and min(len(fallen_norm), len(winner_norm)) / max(len(fallen_norm), len(winner_norm)) >= 0.65
                )

                if ratio >= 0.92 or containment:
                    if best is None or ratio > best[0]:
                        best = (ratio, winner_title, winner_norm, containment)

            if best:
                score, winner_title, _winner_norm, containment = best
                reason = "normalized titles are highly similar"
                if containment:
                    reason = "one normalized title contains the other with similar length"
                candidates.append(Candidate(
                    row_number,
                    fallen_title,
                    winner_title,
                    "fuzzy title match",
                    "medium",
                    score,
                    reason,
                ))
                matched_pairs.add((fallen_title, winner_title))

    return sorted(candidates, key=lambda candidate: candidate.fallen_row)


def print_candidates_text(candidates: list[Candidate]) -> None:
    if not candidates:
        print("No likely already-watched Fallen titles were identified.")
        return

    print(f"Found {len(candidates)} candidate(s):")
    for index, candidate in enumerate(candidates, start=1):
        print()
        print(f"[{index}] Fallen row: {candidate.fallen_row}")
        print(f"    Fallen:  {candidate.fallen_title}")
        print(f"    Winner:  {candidate.winner_title}")
        print(f"    Match:   {candidate.match_type} ({candidate.confidence}, score={candidate.score:.3f})")
        print(f"    Reason:  {candidate.reason}")


def apply_removals(
    fallen_path: Path,
    approved_titles: set[str],
    fallen_column: str = DEFAULT_FALLEN_COLUMN,
    dry_run: bool = False,
) -> tuple[Path | None, list[str], int]:
    """Remove approved Fallen titles, preserving order and CSV schema."""
    rows = read_csv_rows(fallen_path)
    require_column(rows, fallen_column, fallen_path)

    removed = [row[fallen_column] for row in rows if row.get(fallen_column) in approved_titles]
    remaining = [row for row in rows if row.get(fallen_column) not in approved_titles]

    if dry_run:
        return None, removed, len(remaining)

    backup_path = fallen_path.with_name(f"{fallen_path.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(fallen_path, backup_path)

    fieldnames = list(rows[0].keys()) if rows else [fallen_column]
    with fallen_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(remaining)

    return backup_path, removed, len(remaining)


def read_approved_titles(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find/apply Fallen titles already present in winners.")
    parser.add_argument("--winners", type=Path, default=DEFAULT_WINNERS_PATH, help="Path to winners CSV")
    parser.add_argument("--fallen", type=Path, default=DEFAULT_FALLEN_PATH, help="Path to Fallen CSV")
    parser.add_argument("--winner-column", default=DEFAULT_WINNER_COLUMN, help="Winner title column")
    parser.add_argument("--fallen-column", default=DEFAULT_FALLEN_COLUMN, help="Fallen title column")
    parser.add_argument("--no-fuzzy", action="store_true", help="Only report exact and normalized matches")
    parser.add_argument("--json", action="store_true", help="Output candidates as JSON")
    parser.add_argument("--apply-approved", type=Path, help="Text file of approved Fallen titles to remove, one per line")
    parser.add_argument("--dry-run", action="store_true", help="With --apply-approved, report removals without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.apply_approved:
        approved_titles = read_approved_titles(args.apply_approved)
        backup_path, removed, remaining_count = apply_removals(
            args.fallen,
            approved_titles,
            args.fallen_column,
            args.dry_run,
        )
        print(f"removed_count={len(removed)}")
        print(f"remaining_count={remaining_count}")
        if backup_path:
            print(f"backup={backup_path}")
        else:
            print("backup=<dry-run>")
        print("removed=")
        for title in removed:
            print(title)
        return 0

    winners_rows = read_csv_rows(args.winners)
    fallen_rows = read_csv_rows(args.fallen)
    require_column(winners_rows, args.winner_column, args.winners)
    require_column(fallen_rows, args.fallen_column, args.fallen)

    candidates = find_candidates(
        winners_rows,
        fallen_rows,
        args.winner_column,
        args.fallen_column,
        fuzzy=not args.no_fuzzy,
    )

    if args.json:
        print(json.dumps([asdict(candidate) for candidate in candidates], indent=2, ensure_ascii=False))
    else:
        print_candidates_text(candidates)

    return 0


if __name__ == "__main__":
    sys.exit(main())
