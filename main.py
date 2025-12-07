import discord
import os
import random
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv
from discord import app_commands, Poll, Embed
from discord.utils import sleep_until, utcnow
from discord.ext import commands
from rich.console import Console

console = Console()

enticipation_sentence_list = [
    "## Attention, mesdames et messieurs, préparez-vous à accueillir… un(e) grand(e) gagnant(e) ! Le suspense est insoutenable…",
    "## Le sort a parlé ! Mais qui est l’élu(e) de cette grande cérémonie de… hasard total ?",
    "## Roulement de tambour... 🥁 Et la personne choisie est…",
    "## Je scanne la liste… Je réfléchis… Voilà, c’est décidé ! Voici le(la) chanceux(se) du jour !",
    "## C’est parti pour l’annonce ! Est-ce que ça sera toi ? Ou toi ? Non, c’est…",
]
selection_sentence_list = [
    "## **Bravo à {nom}, tu viens d’être choisi(e) 🎯 !** On espère que tu es prêt(e) à relever le défi !",
    "## Et c’est {nom} qui l’emporte cette fois-ci ! Applaudissements pour cette performance de pure chance ! 👏",
    "## **Félicitations à {nom} !** Comme on dit, la roue tourne… 🛞 et elle vient de s’arrêter sur toi !",
    "## Wow, {nom}, tu es l’heureux(se) élu(e) ! Va jouer au loto 🎰 aujourd’hui, c’est ton jour de chance !",
    "## **Attention, attention… {nom} vient de gagner la couronne 👑!** Oui, c’est toi ! 🎉",
]

# TODO: Reorganize functions in different files + clean backup if API calls are not working anymore

load_dotenv()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

def search_imdb_titles(query: str):
    url = "https://api.imdbapi.dev/search/titles"
    params = {"query": query}

    response = requests.get(url, params=params, headers={"accept": "application/json"})
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Request failed with status code {response.status_code}"}

def get_imdb_title_details(title_id: str):
    url = f"https://api.imdbapi.dev/titles/{title_id}"

    response = requests.get(url, headers={"accept": "application/json"})
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Request failed with status code {response.status_code}"}

def first_result_title_details(query: str):
    search_results = search_imdb_titles(query)
    if "titles" in search_results and len(search_results["titles"]) > 0:
        first_title_id = search_results["titles"][0]["id"]
        return get_imdb_title_details(first_title_id)
    else:
        console.print(f"No titles found for query: {query}")
        console.print(search_results)
        return {"error": "No titles found for the given query."}

def prepare_message(title_details: dict):
    if "error" in title_details:
        console.print(f"Error retrieving details for the movie: {title_details['error']}")
        return title_details["error"]
    
    genres = title_details.get('genres', [])
    genres = [genre if genre!="Horror" else "**Horror(Careful for those who are easily scared!)**" for genre in genres]

    
    message = f"## {title_details.get('primaryTitle')}\n"
    message += f"Plot: ||**{title_details.get('plot')}**||\n"
    message += f"Rating: **{title_details.get('rating').get('aggregateRating')}** (This is the IMDB rating, above *7* is usually good)\n"
    message += f"Genres: {', '.join(genres)}\n"
    # message += f"{title_details.get('primaryImage').get('url')}/\n"
    
    # embed = Embed(title=title_details.get('primaryTitle'), description=title_details.get('plot'))
    embed = Embed()
    embed.set_image(url=title_details.get('primaryImage').get('url'))
    
    return message, embed

def get_role_id_from_mention(mention: str) -> int:
    return int(mention.replace("<@&", "").replace(">", ""))


def get_user_id_from_mention(mention: str) -> int:
    return int(mention.replace("<@", "").replace(">", ""))


def check_if_user_exist(user_id: int, all_user: list) -> bool:
    print(all_user)
    for user in all_user:
        if user.id == user_id:
            return True
    return False

def prochain_mercredi(date_reference: datetime = None) -> datetime:
    """
    Retourne la date du prochain mercredi à 21h15 à partir de la date de référence donnée.
    Si aucune date de référence n'est fournie, utilise la date actuelle.
    
    :param date_reference: Une date de référence optionnelle (datetime).
    :return: Un objet datetime représentant le prochain mercredi à 21h15.
    """
    date_reference = date_reference if date_reference else datetime.today()
    
    # Calcul des jours à ajouter pour atteindre mercredi (mercredi = 2)
    jours_a_ajouter = (2 - date_reference.weekday()) % 7 or 7  # Assure le mercredi suivant
    
    return datetime.combine(date_reference.date() + timedelta(days=jours_a_ajouter), datetime.min.time().replace(hour=20, minute=30))

def discord_timestamps(date: datetime, format: str = 'f') -> str:
    """
    Génère un timestamp Discord à partir d'une date.
    
    :param date: Un objet datetime
    :param format: Format du timestamp Discord ('F', 'f', 'D', 'd', 'T', 't', 'R')
    :return: Une chaîne de caractères compatible avec Discord
    """
    accepted_formats = {'F', 'f', 'D', 'd', 'T', 't', 'R'}
    
    if format not in accepted_formats:
        raise ValueError(f"Format non pris en charge. Formats acceptés : {', '.join(accepted_formats)}")
    
    timestamp = int(date.timestamp())  # Convertir en timestamp Unix
    return f'<t:{timestamp}:{format}>'

async def publish_discord_message(message: str, interaction: discord.Interaction, show_message: bool = True):
    """
    Envoie un message sur Discord via une interaction.

    Cette fonction envoie un message en réponse à une interaction Discord. Si la réponse a
    déjà été envoyée, elle utilise `followup.send()`, sinon elle utilise `response.send_message()`.

    :param message: Le message à envoyer sur Discord.
    :param interaction: contenant l'état de l'interaction Discord
    :param show_message: Détermine si le message est visible pour tous (`True`) ou seulement pour l'utilisateur (`False`).
    
    :raises KeyError: Si l'interaction n'est pas trouvée dans l'état fourni.
    """
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=not show_message)
    else:
        await interaction.response.send_message(message, ephemeral=not show_message)

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
                f"Role {role_mention} does not exist.", interaction, show_message=show_message
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

    random_preparation_sentence = random.choice(enticipation_sentence_list)
    await publish_discord_message(
        random_preparation_sentence, interaction, show_message=show_message
    )

    await sleep_until(utcnow() + timedelta(seconds=3))

    random_selection_sentence = random.choice(selection_sentence_list)

    # Send a response with all selected members
    await publish_discord_message(
        random_selection_sentence.format(nom=f"<@{selected_member}>"),
        interaction,
        show_message = show_message,
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
            show_message = show_message,
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
        show_message = show_message,
    )

@bot.tree.command(name="movie_night")
@app_commands.describe(
    movies_list = "la liste des films a proposer"
)
async def create_poll(
    interaction: discord.Interaction,
    movies_list: str,
):
    """
    Commande pour organiser une soirée film
    """
    movie_night_role_id = 777544183736565801

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

    await interaction.response.send_message(poll=poll,silent=False)

    with console.status("Getting movie infos..."):
        for movie in list_movies:
            console.print(f"Getting info for movie: {movie}")
            info = first_result_title_details(movie)
            message, embed = prepare_message(info)
            await interaction.followup.send(message, embed=embed, ephemeral=False)
    
    reminder_message = (
        f"## Hey <@&{movie_night_role_id}> ! N'oubliez pas de voter pour le film de la watchparty !" 
        f"La soirée film aura lieu {discord_timestamps(prochain_mercredi())}" 
        f"({discord_timestamps(prochain_mercredi(), format='R')}).")
    await publish_discord_message(
        reminder_message,
        interaction,
        show_message=True,
    )
    return True


bot.run(os.getenv("DISCORD_TOKEN"))