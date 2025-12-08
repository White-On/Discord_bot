"""
IMDB API integration for movie information
"""

import requests
import asyncio
from discord import Embed
from rich.console import Console

console = Console()

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds (will exponentially increase)
RATE_LIMIT_STATUS_CODE = 429


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
                        f"[yellow]⚠ Rate limit hit. Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})[/yellow]"
                    )
                    await asyncio.sleep(wait_time)  # Non-blocking sleep
                    continue
                else:
                    console.print(f"[red]✗ API rate limit exceeded after {max_retries} retries[/red]")
                    return {"error": "API rate limit exceeded after multiple retries"}
            else:
                console.print(f"[red]✗ API request failed with status code {response.status_code}[/red]")
                return {
                    "error": f"Request failed with status code {response.status_code}"
                }

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2**attempt)
                console.print(
                    f"[yellow]⚠ Request timeout. Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})[/yellow]"
                )
                await asyncio.sleep(wait_time)  # Non-blocking sleep
                continue
            else:
                console.print(f"[red]✗ Request timeout after {max_retries} retries[/red]")
                return {"error": "Request timeout after multiple retries"}

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2**attempt)
                console.print(
                    f"[yellow]⚠ Request error: {str(e)}. Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})[/yellow]"
                )
                await asyncio.sleep(wait_time)  # Non-blocking sleep
                continue
            else:
                console.print(f"[red]✗ Request failed after {max_retries} retries: {str(e)}[/red]")
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


async def first_result_title_details(query: str):
    """Get the first search result's details from IMDB"""
    search_results = await search_imdb_titles(query)
    if "titles" in search_results and len(search_results["titles"]) > 0:
        first_title_id = search_results["titles"][0]["id"]
        return await get_imdb_title_details(first_title_id)
    else:
        console.print(f"[yellow]⚠ No titles found for query: {query}[/yellow]")
        return {"error": "No titles found for the given query."}


def prepare_message(title_details: dict):
    """Prepare a Discord message with movie information"""
    if "error" in title_details:
        console.print(
            f"[red]✗ Error retrieving details:[/red] {title_details['error']}"
        )
        return None, None

    try:
        genres = title_details.get("genres", [])
        genres = [
            genre if genre != "Horror" else "**:warning: Horror :warning:**"
            for genre in genres
        ]

        message = f"## {title_details.get('primaryTitle', 'Unknown')}\n"
        message += f"Plot: ||*{title_details.get('plot', 'N/A')}*||\n"
        
        rating = title_details.get('rating', {})
        agg_rating = rating.get('aggregateRating', 'N/A') if isinstance(rating, dict) else 'N/A'
        message += f"Rating: **{agg_rating}** (IMDB rating, >7 is usually good)\n"
        message += f"Genres: {', '.join(genres) if genres else 'N/A'}\n"

        embed = Embed()
        primary_image = title_details.get("primaryImage")
        if primary_image:
            image_url = primary_image.get("url") if isinstance(primary_image, dict) else primary_image
            if image_url:
                embed.set_image(url=image_url)

        return message, embed
    
    except Exception as e:
        console.print(f"[red]✗ Error preparing message:[/red] {e}")
        return None, None
