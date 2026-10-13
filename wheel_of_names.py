"""Wheel of Names API helpers for Clumsy Movie Bot.

This module contains deterministic Wheel of Names-specific payload and response
helpers. It intentionally does not perform HTTP requests.
"""

import re


WHEEL_API_V3_URL = "https://wheelofnames.com/api/v3/wheels"
WHEEL_LIST_FIELDS = "path"
WHEEL_SHARE_BASE_URL = "https://wheelofnames.com/"
WHEEL_OF_NAMES_REJECTED_TERMS = {
    "hitler",
    "fuck",
    "pussy",
    "goon",
    "jizz",
    "tits",
}
VOWELS = "aeiouAEIOU"


def find_rejected_wheel_terms(titles, rejected_terms=None):
    """Return titles that contain terms known to be rejected by Wheel of Names."""
    rejected_terms = rejected_terms or WHEEL_OF_NAMES_REJECTED_TERMS
    matches = []

    for title in titles:
        matched_terms = sorted(
            term for term in rejected_terms
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", title, re.IGNORECASE)
        )

        if matched_terms:
            matches.append({"title": title, "terms": matched_terms})

    return matches


def censor_vowels(text):
    """Return text with English vowels replaced by asterisks."""
    return ''.join('*' if character in VOWELS else character for character in text)


def sanitize_title_for_wheel(title, rejected_terms=None):
    """Censor vowels in titles containing terms rejected by Wheel of Names."""
    if find_rejected_wheel_terms([title], rejected_terms):
        return censor_vowels(title)

    return title


def build_sanitized_wheel_title_lines(titles, rejected_terms=None):
    """Return readable lines showing titles sanitized before wheel submission."""
    lines = []

    for match in find_rejected_wheel_terms(titles, rejected_terms):
        title = match["title"]
        sanitized_title = sanitize_title_for_wheel(title, rejected_terms)
        terms = ", ".join(match["terms"])
        lines.append(f"- {title} -> {sanitized_title} (matched: {terms})\n")

    return lines


def build_wheel_entries(weighted_titles):
    """Return Wheel of Names entry dictionaries for weighted titles."""
    entries = []

    for title in weighted_titles:
        entries.append({'text': sanitize_title_for_wheel(title)})

    return entries


def build_wheel_payload(entries):
    """Return the Wheel of Names v3 payload used by the bot."""
    return {
        "title": "Clumsy Movie Night",
        "description": "First movie to 3 spins wins. Click 'Copy this Wheel' to customize.",
        "shareMode": "copyable",
        "wheelConfigs": [{
            "title": "Clumsy Movie Night",
            "description": "First movie to 3 spins wins. Click 'Copy this Wheel' to customize.",
            "displayWinnerDialog": True,        
            "allowDuplicates": True,
            "maxNames": 50,                    
            "entries": entries
        }]
    }


def extract_wheel_path(response_json):
    """Extract the share path from a Wheel of Names response body."""
    return response_json['data']['path']


def build_wheel_share_url(path):
    """Return the public Wheel of Names URL for a response path."""
    return WHEEL_SHARE_BASE_URL + path


def build_list_wheels_params(fields=WHEEL_LIST_FIELDS):
    """Return query parameters for listing wheels.

    The purge command only needs wheel paths, so request the smallest useful
    response from the v3 API.
    """
    return {'fields': fields}


def extract_wheel_paths(response_json):
    """Extract wheel paths from a Wheel of Names list response body."""
    return [wheel['path'] for wheel in response_json['data']['wheels']]


def build_delete_wheel_url(path):
    """Return the v3 URL for deleting a Wheel of Names wheel by path."""
    return f"{WHEEL_API_V3_URL}/{path}"
