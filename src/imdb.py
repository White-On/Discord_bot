"""
IMDB API integration for movie information
"""

import requests
import asyncio
from discord import Embed
from rich.console import Console
from pydantic import BaseModel
from typing import Any

console = Console()

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds (will exponentially increase)
RATE_LIMIT_STATUS_CODE = 429


class Movie(BaseModel):
    id: str
    primaryTitle: str
    originalTitle: str
    theme: list[str]
    plot: str
    image_url: str
    rating: Any


async def _make_request_with_retry(
    url: str, params: dict = None, max_retries: int = MAX_RETRIES
):
    """
    Make an HTTP GET request with automatic retry logic for rate limits.
    Uses asyncio.sleep() instead of time.sleep() to avoid blocking the event loop.

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
                        f"Rate limit hit. Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)  # Non-blocking sleep
                    continue
                else:
                    console.print(
                        f"API rate limit exceeded after {max_retries} retries"
                    )
                    return {"error": "API rate limit exceeded after multiple retries"}
            else:
                console.print(
                    f"API request failed with status code {response.status_code}"
                )
                return {
                    "error": f"Request failed with status code {response.status_code}"
                }

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2**attempt)
                console.print(
                    f"Request timeout. Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)  # Non-blocking sleep
                continue
            else:
                console.print(f"Request timeout after {max_retries} retries")
                return {"error": "Request timeout after multiple retries"}

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2**attempt)
                console.print(
                    f"Request error: {str(e)}. Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)  # Non-blocking sleep
                continue
            else:
                console.print(f"Request failed after {max_retries} retries: {str(e)}")
                return {"error": f"Request failed: {str(e)}"}

    return {"error": "All retry attempts failed"}


async def search_imdb_titles(query: str):
    """Search for movie titles on IMDB"""
    url = "https://api.imdbapi.dev/search/titles"
    params = {"query": query}
    return await _make_request_with_retry(url, params)


async def get_imdb_title_details(title_id: str):
    """Get detailed information about a movie from IMDB"""
    url = f"https://api.imdbapi.dev/titles/{title_id}"
    return await _make_request_with_retry(url)


async def first_result_title_details(movie_title: str):
    """Get the first search result's details from IMDB"""
    search_results = await search_imdb_titles(movie_title)
    if "titles" in search_results and len(search_results["titles"]) > 0:
        first_title_id = search_results["titles"][0]["id"]
        response = await get_imdb_title_details(first_title_id)
        if "error" in response:
            return None
        return Movie(
            id=response.get("id", ""),
            primaryTitle=response.get("primaryTitle", ""),
            originalTitle=response.get("originalTitle", ""),
            theme=response.get("theme", ["N/A"]),
            plot=response.get("plot", "N/A"),
            image_url=(
                response.get("primaryImage", {}).get("url", "")
                if response.get("primaryImage")
                else ""
            ),
            rating=response.get("ratings", {}),
        )
    else:
        console.print(f"No titles found for query: {movie_title}")
        return {"error": "No titles found for the given query."}


def prepare_message(movie: Movie):
    """Prepare a Discord message with movie information"""
    genres = movie.theme
    # Highlight Horror genre
    color = 0x0000FF  # Default color (Blue)
    genres = [
        genre if genre != "Horror" else "**:warning: Horror :warning:**"
        for genre in genres
    ]

    message = f"## {movie.primaryTitle}\n"
    message += f"Plot: ||*{movie.plot}*||\n"

    rating = movie.rating
    agg_rating = (
        rating.get("aggregateRating", "N/A") if isinstance(rating, dict) else "N/A"
    )
    message += f"Rating: **{agg_rating}** (IMDB rating, >7 is usually good)\n"
    message += f"Genres: {', '.join(genres) if genres else 'N/A'}\n"

    # calculate the color based on rating
    if agg_rating != "N/A":
        rating_value = float(agg_rating)
        if rating_value >= 7.0:
            color = 0x00FF00  # Green
        elif 5.0 <= rating_value < 7.0:
            color = 0xFFFF00  # Yellow
        else:
            color = 0xFF0000  # Red

    embed = Embed()
    embed.description = message
    embed.color = color

    primary_image = movie.image_url
    if primary_image:
        embed.set_image(url=primary_image)

    return message, embed


async def test_imdb_api() -> tuple[bool, str | None]:
    """Test if the IMDB API search endpoint is reachable.

    Returns a tuple `(ok, error_message)` where `ok` is True if the API responded
    successfully and `error_message` contains details on failure when `ok` is False.
    """
    url = "https://api.imdbapi.dev/search/titles"
    params = {"query": "test"}

    res = await _make_request_with_retry(url, params=params, max_retries=1)

    # _make_request_with_retry returns a dict with an "error" key on failures
    if isinstance(res, dict) and res.get("error"):
        console.print(f"IMDB API test failed: {res.get('error')}")
        return False, res.get("error")

    console.print("[green]✓ IMDB API reachable[/green]")
    return True, None
