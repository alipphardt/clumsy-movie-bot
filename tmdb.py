"""TMDB API helpers for Clumsy Movie Bot.

This module contains deterministic TMDB-specific URL, header, and response
parsing helpers. It intentionally does not perform HTTP requests or create
Discord objects.
"""

from urllib.parse import quote

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_WEB_BASE_URL = "https://www.themoviedb.org/movie/"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"


def build_auth_headers(token):
    """Return TMDB bearer-token authorization headers."""
    return {"Authorization": f"Bearer {token}"}


def build_search_movie_url(query):
    """Return the TMDB movie search URL for a query string."""
    return f"{TMDB_API_BASE_URL}/search/movie?query={quote(query)}"


def build_movie_details_url(movie_id):
    """Return the TMDB movie details URL for a TMDB movie ID."""
    return f"{TMDB_API_BASE_URL}/movie/{movie_id}"


def build_find_by_imdb_id_url(imdb_id):
    """Return the TMDB find URL for an IMDB ID."""
    return f"{TMDB_API_BASE_URL}/find/{imdb_id}"


def build_tmdb_movie_url(movie_id):
    """Return the public TMDB movie URL for a TMDB movie ID."""
    return f"{TMDB_WEB_BASE_URL}{movie_id}"


def build_poster_url(poster_path):
    """Return a TMDB poster image URL, or an empty string when no path exists."""
    if poster_path in (None, ''):
        return ''

    return f"{TMDB_IMAGE_BASE_URL}{poster_path}"


def format_search_result_title(movie):
    """Return the bot's display title for a TMDB search result."""
    return f"{movie.get('title', 'N/A')} ({movie.get('release_date', 'N/A')[:4]})"


def parse_search_results(data, limit=10):
    """Return the bot's stored movie list shape from a TMDB search response."""
    movies = []

    for movie in data['results'][:limit]:
        movies.append({
            'title': format_search_result_title(movie),
            'id': movie.get('id','')
        })

    return movies


def format_search_results_message(search_results):
    """Return the Discord text shown for TMDB search results."""
    results = "Top 10 Search Results from TMDB:\n"

    for index, movie in enumerate(search_results):
        results += "[" + str(index+1) + "] " + movie['title'] + "\n"

    return results


def parse_movie_summary(movie):
    """Return summary fields used by TMDB summary/random embeds."""
    poster_path = movie.get('poster_path','')

    return {
        'title': movie.get('title', 'Unavailable'),
        'description': movie.get('overview', ["Unavailable"]),
        'release_date': str(movie.get('release_date', 'N/A')),
        'runtime': str(movie.get('runtime','N/A')),
        'poster_path': poster_path,
        'poster_url': build_poster_url(poster_path),
    }


def extract_first_movie_result_id(find_response):
    """Return the first TMDB movie ID from a find-by-IMDB-ID response."""
    return find_response['movie_results'][0]['id']


def is_random_candidate_allowed(movie, minimum_year=1950):
    """Return whether a random TMDB movie matches the bot's current filters."""
    release_year = str(movie.get('release_date', 'N/A'))[:4]
    release_year = release_year if release_year != 'N/A' else 0
    adult = movie.get('adult',False)

    return not adult and int(release_year) >= minimum_year
