"""
IMDB API integration for movie information
"""

import requests
import time
from discord import Embed
from rich.console import Console

console = Console()

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds (will exponentially increase)
RATE_LIMIT_STATUS_CODE = 429


def _make_request_with_retry(
    url: str, params: dict = None, max_retries: int = MAX_RETRIES
):
    """
    Make an HTTP GET request with automatic retry logic for rate limits.

    :param url: The URL to request
    :param params: Optional query parameters
    :param max_retries: Maximum number of retry attempts
    :return: Response JSON if successful, error dict otherwise
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url, params=params, headers={"accept": "application/json"}, timeout=10
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == RATE_LIMIT_STATUS_CODE:
                # Rate limited - retry with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = RETRY_DELAY * (2**attempt)
                    console.print(
                        f"[yellow]Rate limit hit. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})[/yellow]"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    return {"error": "API rate limit exceeded after multiple retries"}
            else:
                # Other errors don't warrant retry
                return {
                    "error": f"Request failed with status code {response.status_code}"
                }

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2**attempt)
                console.print(
                    f"[yellow]Request timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})[/yellow]"
                )
                time.sleep(wait_time)
                continue
            else:
                return {"error": "Request timeout after multiple retries"}

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2**attempt)
                console.print(
                    f"[yellow]Request error: {str(e)}. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})[/yellow]"
                )
                time.sleep(wait_time)
                continue
            else:
                return {"error": f"Request failed: {str(e)}"}

    return {"error": "All retry attempts failed"}


def search_imdb_titles(query: str):
    """Search for movie titles on IMDB"""
    url = "https://api.imdbapi.dev/search/titles"
    params = {"query": query}
    return _make_request_with_retry(url, params)


def get_imdb_title_details(title_id: str):
    """Get detailed information about a movie from IMDB"""
    url = f"https://api.imdbapi.dev/titles/{title_id}"
    return _make_request_with_retry(url)


def first_result_title_details(query: str):
    """Get the first search result's details from IMDB"""
    search_results = search_imdb_titles(query)
    if "titles" in search_results and len(search_results["titles"]) > 0:
        first_title_id = search_results["titles"][0]["id"]
        return get_imdb_title_details(first_title_id)
    else:
        console.print(f"No titles found for query: {query}")
        console.print(search_results)
        return {"error": "No titles found for the given query."}


def prepare_message(title_details: dict):
    """Prepare a Discord message with movie information"""
    if "error" in title_details:
        console.print(
            f"Error retrieving details for the movie: {title_details['error']}"
        )
        return title_details["error"]

    genres = title_details.get("genres", [])
    genres = [
        genre if genre != "Horror" else "**:warning: Horror :warning:**"
        for genre in genres
    ]

    message = f"## {title_details.get('primaryTitle')}\n"
    message += f"Plot: ||*{title_details.get('plot')}*||\n"
    message += f"Rating: **{title_details.get('rating').get('aggregateRating')}** (This is the IMDB rating, above *7* is usually good)\n"
    message += f"Genres: {', '.join(genres)}\n"

    embed = Embed()
    embed.set_image(url=title_details.get("primaryImage").get("url"))

    return message, embed
