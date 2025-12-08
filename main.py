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
from src.imdb import first_result_title_details, prepare_message

console = Console()

# TODO: Clean backup if API calls are not working anymore

load_dotenv()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())


@bot.event
async def on_ready():
    """
    Called when the bot is ready.
    """
    print(f"Logged on as {bot.user}!")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


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
    # Split roles mentions into a list of role strings
    all_mentions = all_mentions.split()
    role_mentions = []
    selected_members = []

    for mention in all_mentions:
        if mention == "@everyone" or mention == "@here":
            continue
        if not mention.startswith("<@&"):
            # then it's a user mention
            # check if the user in the server
            if check_if_user_exist(
                get_user_id_from_mention(mention), interaction.guild.members
            ):
                selected_members.append(get_user_id_from_mention(mention))
        else:
            role_mentions.append(mention)

    for role_mention in role_mentions:
        # Get the role from the mention
        # print(f'role mention : {role_mention}')
        # print(get_role_id_from_mention(role_mention))
        role = discord.utils.get(
            interaction.guild.roles, id=get_role_id_from_mention(role_mention)
        )
        if role is None:
            await publish_discord_message(
                f"Role {role_mention} does not exist.",
                interaction,
                show_message=show_message,
            )
            return

        # Get all members with this role
        members_in_role = [
            member.id for member in interaction.guild.members if role in member.roles
        ]
        if not members_in_role:
            await publish_discord_message(
                f"**Attention !** Aucun utilisateur trouvé ayant le role :{role_mention}.",
                interaction,
                show_message=True,
            )
        selected_members += members_in_role

    # Select a random member from the role
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


@bot.tree.command(name="poll_decision")
@app_commands.describe(poll_message_id="Identifiant du message avec un sondage *fini*")
@app_commands.describe(
    show_message="Affiche le message pour tous le monde (par défaut, le message ne sera visible que pour vous)"
)
async def poll_decision(
    interaction: discord.Interaction, poll_message_id: str, show_message: bool = True
):
    # Get the poll message
    poll_message = await interaction.channel.fetch_message(poll_message_id)
    # poll_message = await poll_message.fetch()
    poll = poll_message.poll
    print(poll)

    # Is the poll finished
    if not poll.is_finalized():
        await publish_discord_message(
            "Ce sondage n'est pas fini, voyons ! Un peu de patience 😊",
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

    await publish_discord_message(
        f"# Pour résoudre le problème d'égalité trouvé pour le sondage *{poll.question}*, j'ai choisi au hasard pour départager et donc **{coin_flip_answer}** est votre choix final !",
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
    next_wenesday = prochain_mercredi()
    time_until_next_wenesday = next_wenesday - datetime.now()

    console.print(f"time until next wednesday: {time_until_next_wenesday}")

    list_movies = [movie.strip() for movie in movies_list.split("|")]
    console.print(f"list movies: {list_movies}")

    poll = Poll(
        question="On regarde quoi pour la soirée film ? :)",
        duration=time_until_next_wenesday,
        multiple=True,
    )

    for movie in list_movies:
        poll.add_answer(text=movie)

    await interaction.response.send_message(poll=poll, silent=False)

    with console.status("Getting movie infos..."):
        for movie in list_movies:
            console.print(f"Getting info for movie: {movie}")
            info = first_result_title_details(movie)
            message, embed = prepare_message(info)
            await interaction.followup.send(message, embed=embed, ephemeral=False)

    reminder_message = (
        f"## Hey <@&{MOVIE_NIGHT_ROLE_ID}> ! N'oubliez pas de voter pour le film de la watchparty !"
        f"La soirée film aura lieu {discord_timestamps(prochain_mercredi())}"
        f"({discord_timestamps(prochain_mercredi(), format='R')})."
    )
    await publish_discord_message(
        reminder_message,
        interaction,
        show_message=True,
    )
    return True


bot.run(os.getenv("DISCORD_TOKEN"))
