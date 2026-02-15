import discord
import os
import random
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo
from pathlib import Path

from dotenv import load_dotenv
from discord import app_commands, Poll, EntityType, AllowedMentions
from discord.utils import sleep_until, utcnow
from discord.ext import commands
from rich.table import Table

from src.constants import (
    ENTICIPATION_SENTENCE_LIST,
    SELECTION_SENTENCE_LIST,
    MOVIE_NIGHT_ROLE_ID,
    VOICE_CHANNEL_ID,
    PLAYERS_VALORANT_MAPPING,
)
from src import *
from src.imdb import first_result_title_details, prepare_message, test_imdb_api, Movie
from src.renderer import render_html, generate_image
from schemas import LeaderboardPlayer


from src.display_helper import console, success_style, error_style, warning_style
from src.valorant import RiotAPIClient

PARIS_TZ = ZoneInfo("Europe/Paris")

load_dotenv()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())


@bot.tree.command(name="random_choice_user")
@app_commands.describe(
    mentions="List of role mentions and/or user mentions separated by spaces"
)
async def random_choice_user(
    interaction: discord.Interaction, mentions: str
):
    """
    Randomly select a user from a list of role mentions and/or user mentions.
    - Parse mentions to get user IDs
    - Randomly select one user
    - Send a message announcing the selected user
    """
    # Validate input
    if not mentions or not mentions.strip():
        await interaction.response.send_message(
            "You must provide at least one mention (role or user).", ephemeral=True
        )
        return

    # Extract mentions
    mentions = mentions.split()
    members_mentions, role_mentions = parse_mentions(
        mentions, interaction.guild.members
    )

    # Process role mentions to get user IDs
    for role_mention in role_mentions:
        members_in_role = fetch_user_from_role(role_mention, interaction.guild.members)
        members_mentions += members_in_role

    members_mentions = list(set([int(user_id) for user_id in members_mentions]))

    # Check if any members were selected
    if not members_mentions:
        console.print("No members found for the provided mentions", style=warning_style)
        await interaction.response.send_message(
            "No members found for the provided mentions.", ephemeral=True
        )
        return

    # Randomly select a member
    selected_member = random.choice(members_mentions)
    random_preparation_sentence = random.choice(ENTICIPATION_SENTENCE_LIST)
    random_selection_sentence = random.choice(SELECTION_SENTENCE_LIST)

    # Send a preparation message
    await interaction.response.send_message(
        random_preparation_sentence,
    )

    # Wait for 3 seconds before announcing the selected user
    await sleep_until(utcnow() + timedelta(seconds=3))

    # Send a response with all selected members
    await interaction.followup.send(
        f"{random_selection_sentence}".format(nom=f"<@{selected_member}>!"),
        allowed_mentions=AllowedMentions(users=True, roles=False, everyone=False),
    )

    console.print(f"Random user selected: {selected_member}")


@bot.tree.command(name="poll_decision")
@app_commands.describe(poll_message_id="ID of the poll message to evaluate")
async def poll_decision(
    interaction: discord.Interaction, poll_message_id: str
):
    """
    Get the poll results and make a random choice in case of a tie.
    - get the poll from the message ID
    - check if the poll is finalized
    - check if there are answers
    - check for ties
    - randomly select one of the tied answers
    - send the result as a message

    """
    # Validate poll_message_id format
    if not poll_message_id.isdigit():
        await interaction.response.send_message(
            "Error: Poll message ID must be a numeric value.",
            ephemeral=True,
        )

    # Get the poll message
    try:
        poll_message = await interaction.channel.fetch_message(int(poll_message_id))
    except discord.NotFound:
        await interaction.response.send_message(
            f"Error: Message with ID {poll_message_id} not found.",
            ephemeral=True,
        )
        console.print(f"Message not found: {poll_message_id}", style=error_style)
        return

    # Check if message has a poll
    if not poll_message.poll:
        await interaction.response.send_message(
            "Error: The specified message does not contain a poll.",
            ephemeral=True,
        )
        return

    poll = poll_message.poll
    console.print(f"Poll found: {poll.question}")

    # Is the poll finished
    if not poll.is_finalized():
        await interaction.response.send_message(
            "Error: The poll is not finalized yet.",
            ephemeral=True,
        )
        return

    # Check if there are answers
    if not poll.answers:
        await interaction.response.send_message(
            "Error: The poll has no answers.",
            ephemeral=True,
        )
        return

    total_vote = {str(answer): answer.vote_count for answer in poll.answers}

    # check if there is equality
    max_vote = max(total_vote.values())

    # look for all answers with the maximum value
    answers_equality = [key for key, value in total_vote.items() if value == max_vote]

    # coin flip if there is equality
    coin_flip_answer = random.choice(answers_equality)
    console.print(f"Poll decision made: {coin_flip_answer}")

    await interaction.response.send_message(
        f"## To resolve the tie found in the poll *{poll.question}*, I randomly chose to break the tie and therefore **{coin_flip_answer}** is your final choice!",
    )


@bot.tree.command(name="movie_night")
@app_commands.describe(movies_list="the list of movies to propose")
async def movie_night(
    interaction: discord.Interaction,
    movies_list: str,
):
    """
    Create a movie night poll and scheduled event.
    - Validate input
    - Calculate time until next Wednesday at 20:30
    - Create a poll with the provided movies
    - Fetch movie details from IMDB API
    - Create a scheduled event in the guild
    - Send confirmation message
    """
    # Validate input
    if not movies_list or not movies_list.strip():
        await interaction.response.send_message(
            "Error: You must provide a list of movies separated by '|'.",
            interaction,
            show_message=True,
        )
        return

    list_movies = [movie.strip() for movie in movies_list.split("|") if movie.strip()]

    if not list_movies:
        interaction.response.send_message(
            "Error: No valid movies found in the provided list.",
            interaction,
            show_message=True,
        )
        return

    console.print(f"Movies list: {list_movies}")
    next_wenesday = next_wednesday()
    time_until_next_wenesday = next_wenesday - datetime.now()
    console.print(f"Time until next wednesday: {time_until_next_wenesday}")

    poll = Poll(
        question="What movie do you want to watch for the movie night?",
        duration=time_until_next_wenesday,
        multiple=True,
    )

    for movie_title in list_movies:
        poll.add_answer(text=movie_title)

    poll_return = await interaction.response.send_message(poll=poll, silent=False)
    console.print(f"Poll created with {len(list_movies)} movies")

    # Verify IMDB API availability before fetching details
    api_ok, api_error = await test_imdb_api()
    if not api_ok:
        console.print(f"IMDB API test failed: {api_error}")
        await interaction.followup.send(
            f"Warning: IMDB API is not reachable. Movie details will not be fetched. Error: {api_error}",
            ephemeral=True,
        )
    else:
        img_url_list: list[str] = []
        console.print("IMDB API is reachable")
        with console.status("[cyan]Getting movie infos..."):
            for movie_title in list_movies:
                console.print(f"[cyan]→[/cyan] Getting info for movie: {movie_title}")
                # Function over here
                movie_info = await first_result_title_details(movie_title)

                if not movie_info or "error" in movie_info:
                    console.print(
                        f"Error retrieving movie info for '{movie_title}': {movie_info.get('error', 'Unknown error')}",
                        style=warning_style,
                    )
                    continue

                message, embed = prepare_message(movie_info)
                if message and embed:
                    await interaction.followup.send(embed=embed, ephemeral=False)

                # Collect image URL
                if movie_info.image_url:
                    img_url_list.append(movie_info.image_url)

    reminder_message = (
        f"## Hey <@&{MOVIE_NIGHT_ROLE_ID}> ! Don't forget to vote for the movie night!\n"
        f"The movie night will take place {discord_timestamps(next_wednesday() + timedelta(hours=1))} "
        f"({discord_timestamps(next_wednesday() + timedelta(hours=1), format='R')})."
    )
    mention = AllowedMentions(roles=True, users=False, everyone=False)
    await interaction.followup.send(
        reminder_message,
        allowed_mentions=mention,
    )

    voice_channel = bot.get_channel(VOICE_CHANNEL_ID)
    if voice_channel is None:
        console.print(f"Voice channel with ID {VOICE_CHANNEL_ID} not found")
        return True

    description = (
        "Join us for a movie night! The movie will be chosen based on votes!\n"
        "Don't forget to vote in the poll! 🍿🎬\n"
        "You can vote directly in the poll message here: "
        f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{poll_return.id}"
    )

    # Limit to 8 images for the event banner
    img_url_list = img_url_list[:8]
    image_bytes = images_urls_to_bytes_horizontal(img_url_list, target_height=300)

    await interaction.guild.create_scheduled_event(
        name=interaction.channel.name,
        description=description,
        start_time=next_wednesday().astimezone(PARIS_TZ) + timedelta(hours=1),
        end_time=next_wednesday().astimezone(PARIS_TZ) + timedelta(hours=3),
        privacy_level=discord.PrivacyLevel.guild_only,
        entity_type=EntityType.voice,
        image=image_bytes,
        channel=voice_channel,
    )
    return True

async def get_account_info(member: discord.Member) -> dict | None:
    """
    Simulate fetching account info for a member from a database.
    """
    print(f"Fetching account info for member: {member.display_name}")
    for attribute in dir(member):
        if not attribute.startswith("_"):
            print(f" - {attribute}: {getattr(member, attribute)}")

    return member


@bot.tree.command(name="ranking_valorant")
async def ranking_valorant(
    interaction: discord.Interaction,
):
    """
    Command to display the Valorant ranking leaderboard.
    - Fetch player data from Riot API
    - Build a leaderboard embed
    - Send the embed as a response
    """
    await interaction.response.defer()
    riot_client = RiotAPIClient()
    leaderboard_players: list[dict] = []
    console.print("Fetching player data from Riot API...")
    with console.status("[cyan]Fetching player data from Riot API..."):
        for player in PLAYERS_VALORANT_MAPPING:
            try:
                player_info = riot_client.get_rank_carrier(player["name"], "eu",player["tag"], "pc").get("data", {})
                console.print(f"Fetched data for {player['name']}: {player_info}")
                nb_games = sum(season.get("games", 0) for season in player_info.get("seasonal", []))
                nb_win = sum(season.get("wins", 0) for season in player_info.get("seasonal", []))
                leaderboard_players.append({
                    "name": player_info.get("account", {}).get("name", player["name"]),
                    "rank": player_info.get("current", {}).get("tier", {}).get("name", "N/A"),
                    "rr": player_info.get("current", {}).get("rr", "N/A"),
                    "winrate": (nb_win / nb_games * 100) if nb_games > 0 else 0,
                    "games": nb_games,
                    "rank_id": player_info.get("current", {}).get("tier", {}).get("id", "0"),
                    "discord_id": player["discord_id"],
                    "tag": player["tag"],
                })
            except Exception as e:
                console.print(f"Error fetching data for {player['name']}: {e}", style=error_style)
    leaderboard_players.sort(key=lambda x: (x["rank_id"], x["rr"]), reverse=True)
    for player in leaderboard_players:
        # Get the player's discord member object        
        member = interaction.guild.get_member(player["discord_id"])
        if member:
            player["avatar"] = str(member.display_avatar.url)
        else:
            player["avatar"] = None
        valorant_account = riot_client.get_player_info(player["name"], player["tag"])
        player["card"] = valorant_account.get("card", {}).get("large", None)
    
    leaderboard_players = [LeaderboardPlayer(**player) for player in leaderboard_players]
    console.print(leaderboard_players)
    templates_path = Path("templates")
    render_path = Path("rendered")
    rendered_file_path = render_html(templates_path, render_path, leaderboard_players, "Acte 2")
    
    leaderboard_img_path = await generate_image(rendered_file_path)
    await interaction.followup.send(file=discord.File(leaderboard_img_path), ephemeral=False)


@bot.event
async def on_ready():
    """
    Called when the bot is ready.
    """
    try:
        console.print(f"Logged on as {bot.user}!", style=success_style)
        synced = await bot.tree.sync()
        console.print(f"Synced {len(synced)} command(s)", style=success_style)

        # display commands table
        table = Table(title="Registered Commands")
        table.add_column("Command Name", style="cyan", no_wrap=True)
        for command in bot.tree.walk_commands():
            table.add_row(command.name)
        console.print(table)

    except Exception as e:
        console.print(f"Error during bot initialization: {e}", style=error_style)


@bot.event
async def on_error(event, *args, **kwargs):
    """
    Global error handler for bot events
    """
    console.print("Global error handler triggered")
    console.print_exception()


try:
    bot.run(os.getenv("DISCORD_TOKEN"))
except ValueError:
    console.print("DISCORD_TOKEN not found in .env file")
except Exception as e:
    console.print(f"Failed to start bot: {e}", style=error_style)
