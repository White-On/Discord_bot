import discord
import os
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from discord import app_commands, Poll, EntityType, AllowedMentions
from discord.utils import sleep_until, utcnow
from discord.ext import commands
from rich.console import Console
from rich.table import Table

from src.constants import (
    ENTICIPATION_SENTENCE_LIST,
    SELECTION_SENTENCE_LIST,
    MOVIE_NIGHT_ROLE_ID,
)
from src.utils import (
    get_role_id_from_mention,
    prochain_mercredi,
    discord_timestamps,
    publish_discord_message,
    images_urls_to_bytes_horizontal,
    parse_mentions,
)
from src.imdb import first_result_title_details, prepare_message, test_imdb_api

# TODO:
# - chunck commands in functions to reduce size of main.py
# - pydantic models for imdb responses
# - update README with new commands

from src.display_helper import console, success_style, error_style, warning_style

PARIS_TZ = ZoneInfo("Europe/Paris")

load_dotenv()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())


@bot.event
async def on_ready():
    """
    Called when the bot is ready.
    """
    try:
        console.print(f"✓ Logged on as {bot.user}!", style=success_style)

        synced = await bot.tree.sync()
        console.print(f"✓ Synced {len(synced)} command(s)", style=success_style)

        # list commands
        table = Table(title="Registered Commands")
        table.add_column("Command Name", style="cyan", no_wrap=True)
        for command in bot.tree.walk_commands():
            table.add_row(command.name)
        console.print(table)

    except Exception as e:
        console.print(f"✗ Error during bot initialization: {e}", style=error_style)


@bot.tree.command(name="Radom Choice User")
@app_commands.describe(
    mentions="List of role mentions and/or user mentions separated by spaces"
)
@app_commands.describe(
    show_message="Display the message to everyone (by default, the message will only be visible to you)"
)
async def random_choice_user(
    interaction: discord.Interaction, mentions: str, show_message: bool = True
):
    # Validate the input
    # extract role mentions and user mentions
    # extract user IDs from mentions
    # unique the list of user IDs
    # randomly select one user ID

    if not mentions or not mentions.strip():
        await interaction.response.send_message(
            "You must provide at least one mention (role or user).",
            ephemeral=True
        )
        return
    
    # Split roles mentions into a list of role strings
    mentions = mentions.split()
    
    selected_members, role_mentions = parse_mentions(
        mentions, interaction.guild.members
    )

    # Process role mentions
    for role_mention in role_mentions:
        role = discord.utils.get(
            interaction.guild.roles, id=get_role_id_from_mention(role_mention)
        )
        if role is None:
            await publish_discord_message(
                f"✗ Error: Role {role_mention} does not exist.",
                interaction,
                show_message=show_message,
            )
            return

        # Get all members with this role
        members_in_role = [
            member.id
            for member in interaction.guild.members
            if role in member.roles
        ]
        if not members_in_role:
            console.print(
                f"⚠ No members found with role {role_mention}"
            )
            await publish_discord_message(
                f"⚠ **No members found with role {role_mention}**",
                interaction,
                show_message=True,
            )
            continue

        selected_members += members_in_role

    # Check if any members were selected
    if not selected_members:
        await publish_discord_message(
            "✗ Error: No users found matching your mentions.",
            interaction,
            show_message=show_message,
        )
        return

    # Remove duplicates and select a random member
    selected_member = random.choice(list(set(selected_members)))

    random_preparation_sentence = random.choice(ENTICIPATION_SENTENCE_LIST)
    await publish_discord_message(
        random_preparation_sentence, interaction, show_message=show_message
    )

    await sleep_until(utcnow() + timedelta(seconds=3))

    random_selection_sentence = random.choice(SELECTION_SENTENCE_LIST)

    # Send a response with all selected members
    await publish_discord_message(
        random_selection_sentence.format(nom=f"<@{selected_member}>"),
        interaction,
        show_message=show_message,
    )
    console.print(f"✓ Random user selected: {selected_member}")



@bot.tree.command(name="poll_decision")
@app_commands.describe(poll_message_id="ID of the poll message to evaluate")
@app_commands.describe(
    show_message="Display the message to everyone (by default, the message will only be visible to you)"
)
async def poll_decision(
    interaction: discord.Interaction, poll_message_id: str, show_message: bool = True
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
    try:
        # Validate poll_message_id format
        if not poll_message_id.isdigit():
            await publish_discord_message(
                "✗ Error: The message ID must be a number.",
                interaction,
                show_message=show_message,
            )
            return

        # Get the poll message
        try:
            poll_message = await interaction.channel.fetch_message(int(poll_message_id))
        except discord.NotFound:
            await publish_discord_message(
                f"✗ Error: Message with ID {poll_message_id} not found.",
                interaction,
                show_message=show_message,
            )
            console.print(f"✗ Message not found: {poll_message_id}")
            return
        except discord.Forbidden:
            await publish_discord_message(
                "✗ Error: Missing permissions to fetch the message.",
                interaction,
                show_message=show_message,
            )
            return

        # Check if message has a poll
        if not poll_message.poll:
            await publish_discord_message(
                "✗ Error: The specified message does not contain a poll.",
                interaction,
                show_message=show_message,
            )
            return

        poll = poll_message.poll
        console.print(f"✓ Poll found: {poll.question}")

        # Is the poll finished
        if not poll.is_finalized():
            await publish_discord_message(
                "The poll is not finalized yet. Please wait until it ends.",
                interaction,
                show_message=show_message,
            )
            return

        # Check if there are answers
        if not poll.answers:
            await publish_discord_message(
                "✗ Error: The poll does not contain any answers.",
                interaction,
                show_message=show_message,
            )
            return

        total_vote = {str(answer): answer.vote_count for answer in poll.answers}

        # check if there is equality
        # Trouver la valeur maximale dans le dictionnaire
        valeur_maximale = max(total_vote.values())

        # Filtrer les clés ayant la valeur maximale
        answers_equality = [
            cle for cle, valeur in total_vote.items() if valeur == valeur_maximale
        ]

        # Choisir aléatoirement parmi les clés maximales
        coin_flip_answer = random.choice(answers_equality)

        console.print(f"✓ Poll decision made: {coin_flip_answer}")

        await publish_discord_message(
            f"# To resolve the tie found in the poll *{poll.question}*, I randomly chose to break the tie and therefore **{coin_flip_answer}** is your final choice!",
            interaction,
            show_message=show_message,
        )

    except Exception as e:
        console.print(
            f"✗ Error in poll_decision command: {e}", style="bold red"
        )
        await publish_discord_message(
            "✗ An error occurred while processing the poll decision.",
            interaction,
            show_message=show_message,
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
    try:
        # Validate input
        if not movies_list or not movies_list.strip():
            await publish_discord_message(
                "✗ Error: You must provide a list of movies separated by '|'.",
                interaction,
                show_message=True,
            )
            return

        next_wenesday = prochain_mercredi()
        time_until_next_wenesday = next_wenesday - datetime.now()

        if time_until_next_wenesday.total_seconds() <= 0:
            console.print("⚠ Next wednesday is in the past")
            await publish_discord_message(
                "⚠ Error: The next Wednesday at 20:30 is in the past.",
                interaction,
                show_message=True,
            )
            return

        console.print(
            f"✓ Time until next wednesday: {time_until_next_wenesday}"
        )

        list_movies = [
            movie.strip() for movie in movies_list.split("|") if movie.strip()
        ]

        if not list_movies:
            await publish_discord_message(
                "✗ Error: No valid movies provided.",
                interaction,
                show_message=True,
            )
            return

        console.print(f"✓ Movies list: {list_movies}")

        poll = Poll(
            question="What movie do you want to watch for the movie night?",
            duration=time_until_next_wenesday,
            multiple=True,
        )

        for movie in list_movies:
            poll.add_answer(text=movie)

        poll_return = await interaction.response.send_message(poll=poll, silent=False)
        console.print(f"✓ Poll created with {len(list_movies)} movies")

        # Verify IMDB API availability before fetching details
        api_ok, api_error = await test_imdb_api()
        if not api_ok:
            console.print(f"✗ IMDB API test failed: {api_error}")
            await publish_discord_message(
                f"✗ IMDB API is not reachable: {api_error}",
                interaction,
                show_message=True,
            )
        else:
            img_url_list: list[str] = []

            console.print("✓ IMDB API is reachable")
            with console.status("[cyan]Getting movie infos..."):
                for movie in list_movies:
                    try:
                        console.print(f"[cyan]→[/cyan] Getting info for movie: {movie}")
                        info = await first_result_title_details(
                            movie
                        )  # ← Ajouter await

                        if not info or "error" in info:
                            console.print(
                                f"⚠ No info found for movie: {movie}"
                            )
                            continue

                        message, embed = prepare_message(info)
                        if message and embed:
                            await interaction.followup.send(
                                embed=embed, ephemeral=False
                            )

                        # Collect image URL
                        primary_image = info.get("primaryImage")
                        if primary_image:
                            image_url = (
                                primary_image.get("url")
                                if isinstance(primary_image, dict)
                                else primary_image
                            )
                            if image_url:
                                img_url_list.append(image_url)

                    except Exception as e:
                        console.print(
                            f"⚠ Error getting info for {movie}: {e}"
                        )
                    continue

        # Check if MOVIE_NIGHT_ROLE_ID is set
        if not MOVIE_NIGHT_ROLE_ID:
            console.print("⚠ MOVIE_NIGHT_ROLE_ID not set in constants")
            return True

        reminder_message = (
            f"## Hey <@&{MOVIE_NIGHT_ROLE_ID}> ! Don't forget to vote for the movie night!\n"
            f"The movie night will take place {discord_timestamps(prochain_mercredi() + timedelta(hours=1))} "
            f"({discord_timestamps(prochain_mercredi() + timedelta(hours=1), format='R')})."
        )
        mention = AllowedMentions(roles=True, users=False, everyone=False)
        await publish_discord_message(
            reminder_message,
            interaction,
            show_message=True,
            allowed_mentions=mention,
        )

        console.print("✓ Movie night poll created successfully")

        # voice_channel_id = 585547683389898756
        voice_channel_id = 667070663038861312
        voice_channel = bot.get_channel(voice_channel_id)
        if voice_channel is None:
            console.print(
                f"✗ Voice channel with ID {voice_channel_id} not found"
            )
            return True

        description = (
            "Join us for a movie night! The movie will be chosen based on votes!\n"
            "Don't forget to vote in the poll! 🍿🎬\n"
            "You can vote directly in the poll message here: "
            f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{poll_return.id}"
        )

        image_bytes = images_urls_to_bytes_horizontal(img_url_list, target_height=300)

        await interaction.guild.create_scheduled_event(
            name=interaction.channel.name,
            description=description,
            start_time=prochain_mercredi().astimezone(PARIS_TZ) + timedelta(hours=1),
            end_time=prochain_mercredi().astimezone(PARIS_TZ) + timedelta(hours=3),
            privacy_level=discord.PrivacyLevel.guild_only,
            entity_type=EntityType.voice,
            image=image_bytes,
            channel=voice_channel,
            # location="En ligne",
        )

        await publish_discord_message(
            "Événement créé avec succès !", interaction, show_message=False
        )

        return True

    except Exception as e:
        console.print(
            f"✗ Error in create_poll command: {e}", style="bold red"
        )
        await publish_discord_message(
            "✗ An error occurred while creating the movie night poll.",
            interaction,
            show_message=False,
        )
        return False


@bot.event
async def on_error(event, *args, **kwargs):
    """
    Global error handler for bot events
    """
    console.print("✗ Global error handler triggered")
    console.print_exception()


try:
    bot.run(os.getenv("DISCORD_TOKEN"))
except ValueError:
    console.print("✗ DISCORD_TOKEN not found in .env file")
except Exception as e:
    console.print(f"✗ Failed to start bot: {e}", style="bold red")
