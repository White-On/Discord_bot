import discord
import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from discord import app_commands, Poll
from discord.utils import sleep_until, utcnow
from discord.ext import commands
from rich.console import Console

from src.constants import (
    ENTICIPATION_SENTENCE_LIST,
    SELECTION_SENTENCE_LIST,
    MOVIE_NIGHT_ROLE_ID,
)
from src.utils import (
    get_role_id_from_mention,
    get_user_id_from_mention,
    check_if_user_exist,
    prochain_mercredi,
    discord_timestamps,
    publish_discord_message,
)
from src.imdb import first_result_title_details, prepare_message, test_imdb_api

console = Console()

# TODO: Clean backup if API calls are not working anymore

load_dotenv()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())


@bot.event
async def on_ready():
    """
    Called when the bot is ready.
    """
    try:
        console.print(f"[green]✓[/green] Logged on as {bot.user}!")

        synced = await bot.tree.sync()
        console.print(f"[green]✓[/green] Synced {len(synced)} command(s)")
    except Exception as e:
        console.print(f"[red]✗ Error during bot initialization:[/red] {e}")


@bot.tree.command(name="random_choice_user")
@app_commands.describe(
    all_mentions="Liste des roles et utilisateur (e.g., @Role1 @Role2 @User1 ...). séparé d'un espace. **Attention, @everyone et @here pas supporté**"
)
@app_commands.describe(
    show_message="Affiche le message pour tous le monde (par défaut, le message ne sera visible que pour vous)"
)
async def random_choice_user(
    interaction: discord.Interaction, all_mentions: str, show_message: bool = True
):
    try:
        # Validate input
        if not all_mentions or not all_mentions.strip():
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Veuillez fournir au moins une mention (rôle ou utilisateur).",
                interaction,
                show_message=show_message,
            )
            return

        # Split roles mentions into a list of role strings
        all_mentions = all_mentions.split()
        role_mentions = []
        selected_members = []

        for mention in all_mentions:
            if mention == "@everyone" or mention == "@here":
                console.print(
                    f"[yellow]⚠[/yellow] Mention '{mention}' not supported, skipping..."
                )
                continue

            try:
                if not mention.startswith("<@&"):
                    # then it's a user mention
                    user_id = get_user_id_from_mention(mention)
                    if check_if_user_exist(user_id, interaction.guild.members):
                        selected_members.append(user_id)
                    else:
                        console.print(
                            f"[yellow]⚠[/yellow] User {mention} not found in server"
                        )
                else:
                    role_mentions.append(mention)
            except Exception as e:
                console.print(
                    f"[yellow]⚠[/yellow] Error processing mention {mention}: {e}"
                )
                continue

        # Process role mentions
        for role_mention in role_mentions:
            try:
                role = discord.utils.get(
                    interaction.guild.roles, id=get_role_id_from_mention(role_mention)
                )
                if role is None:
                    await publish_discord_message(
                        f"[red]✗ Erreur:[/red] Role {role_mention} does not exist.",
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
                        f"[yellow]⚠[/yellow] No members found with role {role_mention}"
                    )
                    await publish_discord_message(
                        f"[yellow]⚠[/yellow] **Attention !** Aucun utilisateur trouvé ayant le role :{role_mention}.",
                        interaction,
                        show_message=True,
                    )
                    continue

                selected_members += members_in_role
            except Exception as e:
                console.print(f"[red]✗ Error processing role {role_mention}:[/red] {e}")
                await publish_discord_message(
                    f"[red]✗ Erreur lors du traitement du rôle {role_mention}[/red]",
                    interaction,
                    show_message=show_message,
                )
                return

        # Check if any members were selected
        if not selected_members:
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Aucun utilisateur trouvé correspondant à vos mentions.",
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
        console.print(f"[green]✓[/green] Random user selected: {selected_member}")

    except Exception as e:
        console.print(
            f"[red]✗ Error in random_choice_user command:[/red] {e}", style="bold red"
        )
        await publish_discord_message(
            "[red]✗ Une erreur est survenue lors de la sélection aléatoire[/red]",
            interaction,
            show_message=show_message,
        )


@bot.tree.command(name="poll_decision")
@app_commands.describe(poll_message_id="Identifiant du message avec un sondage *fini*")
@app_commands.describe(
    show_message="Affiche le message pour tous le monde (par défaut, le message ne sera visible que pour vous)"
)
async def poll_decision(
    interaction: discord.Interaction, poll_message_id: str, show_message: bool = True
):
    try:
        # Validate poll_message_id format
        if not poll_message_id.isdigit():
            await publish_discord_message(
                "[red]✗ Erreur:[/red] L'ID du message doit être un nombre.",
                interaction,
                show_message=show_message,
            )
            return

        # Get the poll message
        try:
            poll_message = await interaction.channel.fetch_message(int(poll_message_id))
        except discord.NotFound:
            await publish_discord_message(
                f"[red]✗ Erreur:[/red] Message avec l'ID {poll_message_id} non trouvé.",
                interaction,
                show_message=show_message,
            )
            console.print(f"[red]✗ Message not found:[/red] {poll_message_id}")
            return
        except discord.Forbidden:
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Pas de permission pour accéder à ce message.",
                interaction,
                show_message=show_message,
            )
            return

        # Check if message has a poll
        if not poll_message.poll:
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Ce message ne contient pas de sondage.",
                interaction,
                show_message=show_message,
            )
            return

        poll = poll_message.poll
        console.print(f"[green]✓[/green] Poll found: {poll.question}")

        # Is the poll finished
        if not poll.is_finalized():
            await publish_discord_message(
                "Ce sondage n'est pas fini, voyons ! Un peu de patience 😊",
                interaction,
                show_message=show_message,
            )
            return

        # Check if there are answers
        if not poll.answers:
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Le sondage ne contient pas de réponses.",
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

        console.print(f"[green]✓[/green] Poll decision made: {coin_flip_answer}")

        await publish_discord_message(
            f"# Pour résoudre le problème d'égalité trouvé pour le sondage *{poll.question}*, j'ai choisi au hasard pour départager et donc **{coin_flip_answer}** est votre choix final !",
            interaction,
            show_message=show_message,
        )

    except Exception as e:
        console.print(
            f"[red]✗ Error in poll_decision command:[/red] {e}", style="bold red"
        )
        await publish_discord_message(
            "[red]✗ Une erreur est survenue lors du traitement du sondage[/red]",
            interaction,
            show_message=show_message,
        )


@bot.tree.command(name="movie_night")
@app_commands.describe(movies_list="la liste des films a proposer")
async def create_poll(
    interaction: discord.Interaction,
    movies_list: str,
):
    """
    Commande pour organiser une soirée film
    """
    try:
        # Validate input
        if not movies_list or not movies_list.strip():
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Veuillez fournir au moins un film (séparés par |).",
                interaction,
                show_message=True,
            )
            return

        next_wenesday = prochain_mercredi()
        time_until_next_wenesday = next_wenesday - datetime.now()

        if time_until_next_wenesday.total_seconds() <= 0:
            console.print("[yellow]⚠[/yellow] Next wednesday is in the past")
            await publish_discord_message(
                "[yellow]⚠[/yellow] Attention : la date du prochain mercredi semble incorrecte.",
                interaction,
                show_message=True,
            )
            return

        console.print(
            f"[green]✓[/green] Time until next wednesday: {time_until_next_wenesday}"
        )

        list_movies = [
            movie.strip() for movie in movies_list.split("|") if movie.strip()
        ]

        if not list_movies:
            await publish_discord_message(
                "[red]✗ Erreur:[/red] Aucun film valide fourni.",
                interaction,
                show_message=True,
            )
            return

        console.print(f"[green]✓[/green] Movies list: {list_movies}")

        poll = Poll(
            question="On regarde quoi pour la soirée film ? :)",
            duration=time_until_next_wenesday,
            multiple=True,
        )

        for movie in list_movies:
            poll.add_answer(text=movie)

        await interaction.response.send_message(poll=poll, silent=False)
        console.print(f"[green]✓[/green] Poll created with {len(list_movies)} movies")

        # Verify IMDB API availability before fetching details
        api_ok, api_error = await test_imdb_api()
        if not api_ok:
            console.print(f"[red]✗[/red] IMDB API test failed: {api_error}")
            await publish_discord_message(
                f"Impossible de récupérer les informations des films car l'API IMDB n'est pas joignable : {api_error}",
                interaction,
                show_message=True,
            )
        else:
            console.print("[green]✓[/green] IMDB API is reachable")
            with console.status("[cyan]Getting movie infos..."):
                for movie in list_movies:
                    try:
                        console.print(f"[cyan]→[/cyan] Getting info for movie: {movie}")
                        info = await first_result_title_details(
                            movie
                        )  # ← Ajouter await

                        if not info or "error" in info:
                            console.print(
                                f"[yellow]⚠[/yellow] No info found for movie: {movie}"
                            )
                            continue

                        message, embed = prepare_message(info)
                        if message and embed:
                            await interaction.followup.send(
                                message, embed=embed, ephemeral=False
                            )
                    except Exception as e:
                        console.print(
                            f"[yellow]⚠[/yellow] Error getting info for {movie}: {e}"
                        )
                    continue

        # Check if MOVIE_NIGHT_ROLE_ID is set
        if not MOVIE_NIGHT_ROLE_ID:
            console.print("[yellow]⚠[/yellow] MOVIE_NIGHT_ROLE_ID not set in constants")
            return True

        reminder_message = (
            f"## Hey <@&{MOVIE_NIGHT_ROLE_ID}> ! N'oubliez pas de voter pour le film de la watchparty !\n"
            f"La soirée film aura lieu {discord_timestamps(prochain_mercredi())}"
            f"({discord_timestamps(prochain_mercredi(), format='R')})."
        )
        await publish_discord_message(
            reminder_message,
            interaction,
            show_message=True,
        )

        console.print("[green]✓[/green] Movie night poll created successfully")
        return True

    except Exception as e:
        console.print(
            f"[red]✗ Error in create_poll command:[/red] {e}", style="bold red"
        )
        await publish_discord_message(
            "[red]✗ Une erreur est survenue lors de la création du sondage de film[/red]",
            interaction,
            show_message=True,
        )
        return False


@bot.event
async def on_error(event, *args, **kwargs):
    """
    Global error handler for bot events
    """
    console.print("[red]✗ Global error handler triggered[/red]")
    console.print_exception()


try:
    bot.run(os.getenv("DISCORD_TOKEN"))
except ValueError:
    console.print("[red]✗ DISCORD_TOKEN not found in .env file[/red]")
except Exception as e:
    console.print(f"[red]✗ Failed to start bot:[/red] {e}", style="bold red")
