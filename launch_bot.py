import discord

from discord.utils import sleep_until, utcnow
from dotenv import load_dotenv
import os
from discord import app_commands, Poll, PollMedia, Emoji
from discord.ext import commands, tasks
import random

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, create_react_agent
from datetime import datetime, timedelta
from langchain_tavily import TavilySearch



# https://discord.com/developers/applications/1319294811471085662/information

# task doc
# https://discordpy.readthedocs.io/en/stable/ext/tasks/index.html?highlight=task#discord.ext.tasks.loop
# https://discordpy.readthedocs.io/en/latest/ext/tasks/
# https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html

preparation_sentence_list = [
    "## Attention, mesdames et messieurs, préparez-vous à accueillir… un(e) grand(e) gagnant(e) ! Le suspense est insoutenable…",
    "## Le sort a parlé ! Mais qui est l’élu(e) de cette grande cérémonie de… hasard total ?",
    "## Roulement de tambour... 🥁 Et la personne choisie est…",
    "## Je scanne la liste… Je réfléchis… Voilà, c’est décidé ! Voici le(la) chanceux(se) du jour !",
    "## C’est parti pour l’annonce ! Est-ce que ça sera toi ? Ou toi ? Non, c’est…",
]
selection_sentence_list = [
    "## **Bravo à [NOM], tu viens d’être choisi(e) 🎯 !** On espère que tu es prêt(e) à relever le défi !",
    "## Et c’est [NOM] qui l’emporte cette fois-ci ! Applaudissements pour cette performance de pure chance ! 👏",
    "## **Félicitations à [NOM] !** Comme on dit, la roue tourne… 🛞 et elle vient de s’arrêter sur toi !",
    "## Wow, [NOM], tu es l’heureux(se) élu(e) ! Va jouer au loto 🎰 aujourd’hui, c’est ton jour de chance !",
    "## **Attention, attention… [NOM] vient de gagner la couronne 👑!** Oui, c’est toi ! 🎉",
]



# get TOKEN
load_dotenv()
discord_token = os.getenv("DISCORD_TOKEN")
google_API_TOKEN = os.getenv("GOOGLE_API_KEY")
tavily_API_KEY = os.getenv("TAVILY_API_KEY")

bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

# Instantiation The tool accepts various parameters during instantiation:

# max_results (optional, int): Maximum number of search results to return. Default is 5.
# topic (optional, str): Category of the search. Can be "general", "news", or "finance". Default is "general".
# include_answer (optional, bool): Include an answer to original query in results. Default is False.
# include_raw_content (optional, bool): Include cleaned and parsed HTML of each search result. Default is False.
# include_images (optional, bool): Include a list of query related images in the response. Default is False.
# include_image_descriptions (optional, bool): Include descriptive text for each image. Default is False.
# search_depth (optional, str): Depth of the search, either "basic" or "advanced". Default is "basic".
# time_range (optional, str): The time range back from the current date to filter results - "day", "week", "month", or "year". Default is None.
# include_domains (optional, List[str]): List of domains to specifically include. Default is None.
# exclude_domains (optional, List[str]): List of domains to specifically exclude. Default is None.

tavily_search_tool  = TavilySearch(
    max_results=5,
    topic="general",
    # include_answer=False,
    # include_raw_content=False,
    include_images=False,
    # include_image_descriptions=False,
    # search_depth="basic",
    # time_range="day",
    # include_domains=None,
    # exclude_domains=None
)


@bot.event
async def on_ready():
    print(f"Logged on as {bot.user}!")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

    # goes with tasks
    # slow_count.start()


# Message lisen
# @bot.event
# async def on_message(message):
#   if message.author == bot.user:
#     return
#   print(f'Message from {message.author}: {message.content}')


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


@bot.tree.command(name="random_choice_user")
@app_commands.describe(
    all_mentions="Liste des roles et utilisateur (e.g., @Role1 @Role2 @User1 ...). séparé d'un espace. **Carefull, @everyone and @here not supported**"
)
@app_commands.describe(
    show_message="Affiche le message pour tous le monde (par défaut, le message ne sera visible que pour vous)"
)
async def random_choice_user(
    interaction: discord.Interaction, all_mentions: str, show_message: bool = False
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

    random_preparation_sentence = random.choice(preparation_sentence_list)
    await publish_discord_message(
        random_preparation_sentence, interaction, show_message=show_message
    )

    await sleep_until(utcnow() + timedelta(seconds=3))

    random_selection_sentence = random.choice(selection_sentence_list)

    # Send a response with all selected members
    await publish_discord_message(
        random_selection_sentence.replace("[NOM]", f"<@{selected_member}>", 1),
        interaction,
        show_message = show_message,
    )


@bot.tree.command(name="poll_decision")
@app_commands.describe(poll_message_id="Identifiant du message avec un sondage *fini*")
@app_commands.describe(
    show_message="Affiche le message pour tous le monde (par défaut, le message ne sera visible que pour vous)"
)
async def poll_decision(
    interaction: discord.Interaction, poll_message_id: str, show_message: bool = False
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


@bot.tree.command(name="interract_with_chatbot")
@app_commands.describe(human_query="Message a destination du LLM")
@app_commands.describe(
    show_message="Affiche le message pour tous le monde (par défaut, le message ne sera visible que pour vous)"
)
async def interract_with_chatbot(
    interaction: discord.Interaction, human_query: str, show_message: bool = True
):
    # Split roles mentions into a list of role strings
    # role_id_list = [1311644566109028432]
    role_id_list = [1311644566109028432]
    nasty_users = []

    for role_id in role_id_list:
        role = discord.utils.get(interaction.guild.roles, id=role_id)
        if role is None:
            await publish_discord_message(
                f"Role {role_id} does not exist.", interaction, show_message=show_message
            )
            return

        # Get all members with this role
        members_in_role = [
            member.id for member in interaction.guild.members if role in member.roles
        ]
        if not members_in_role:
            await publish_discord_message(
                f"**Attention !** Aucun utilisateur trouvé ayant le role :{role_id}.",
                interaction,
                show_message=True,
            )
            return
        nasty_users += members_in_role

    user_sending_query = interaction.user.id

    await publish_discord_message(
        f"<@{user_sending_query}> viens de me demander **{human_query}**", interaction, show_message=show_message
    )

    system_oder = SystemMessage(
            "Tu es un bot discord pouvant interragir avec les utilisateurs de facon familière. Tu es amical et peux parfois faire des blagues. Tu essayeras d'être concie dans tes réponses, donc pas le droit de dépaser les 10 phrases"
        )

    if user_sending_query in nasty_users:
        query = [system_oder, HumanMessage("Tu vas me répondre en prétendant que tu ne parles pas aux perdant du jeu Valorant et plutot te moquer narquoisement sur mon mauvais niveau sur le jeu Valorant. Sois sarcastique et drôle. Tu peux par exemple critiquer ma précision digne d'un bronze, ou bien mes tactique déplorable ou encore aussi à parler du mauvais système de point pour les parties classé qui semble fortement me défavoriser. Ta réponse dois être relativement cours et ne pas dépaser deux phrases")]
    else:
        query = [system_oder, HumanMessage(human_query)]

    chatbot_response = AIMessage("Une erreur est survenue en appelant l'API qui me permet de parler ! J'en suis désolé :(")
    try:
        chatbot_response = await llm.ainvoke(query)
    except Exception as e:
        print(f"An Error occured when calling the chatbot:{e}")

    await publish_discord_message(
        f"{chatbot_response.content}", interaction, show_message=show_message
    )


# @bot.tree.command(name="create_poll")
# @app_commands.describe(
#     question="La question du sondage",
#     answers="Les choix de réponse, séparés par un espace",
#     duration="Durée du sondage en heure (optionnel, par défaut 24 heures)",
#     answers_emoji="Les emojies liée a chaque choix de réponses",
#     multiple="Plusieurs réponses acceptés"
# )
# async def create_poll(
#     interaction: discord.Interaction,
#     question: str,
#     answers: str,
#     duration: int = 24,
#     answers_emoji: str = None,
#     multiple: bool =True,
# ):
#     """
#     Commande pour créer un sondage avec réactions.
#     """
#     answers = answers.split('|')
#     answers_emoji = answers_emoji.split()
#     if len(answers) < 2:
#         await publish_discord_message(
#             "Merci d'ajouter au moins deux choix pour le sondage !", interaction, show_message=True
#         )
#         return None
    
#     poll = Poll(question,datetime.timedelta(hours=duration),multiple=multiple)

#     for answer, emoji in zip(answers, answers_emoji):
#         print(f'Answers :{answer},{emoji}')
#         poll.add_answer(text=answer, emoji=emoji)
    
#     await publish_discord_message(poll=poll)

@tool
async def publish_poll(
    question: str,
    answers: str,
    state: Annotated[dict, InjectedState],
    duration: int = 48,
    answers_emoji: str = None,
    multiple: bool =True,
):
    """
    Commande pour créer un sondage avec réactions.
    """
    # print(f"{question = }, {answers.split('|') = }, {duration = }")
    interaction: discord.Interaction = state["interaction"]
    answers = answers.split('|')
    answers_emoji = answers_emoji.split() if answers_emoji is not None else [f"number_{idx}" for idx in range(len(answers))]
    if len(answers) < 2:
        await publish_discord_message(
            "Merci d'ajouter au moins deux choix pour le sondage !", interaction, show_message=True
        )
        return None
    
    poll = Poll(question,timedelta(hours=duration), multiple=multiple)

    # for answer, emoji in zip(answers, answers_emoji):
    #     print(f'Answers :{answer},{emoji}')
    #     poll.add_answer(text=answer, emoji=emoji)

    for answer in answers:
        poll.add_answer(text=answer)
    
    await interaction.response.send_message(poll=poll)
    return True

class State(AgentState):
    interaction: discord.Interaction

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
    
    return datetime.combine(date_reference.date() + timedelta(days=jours_a_ajouter), datetime.min.time().replace(hour=21, minute=15))

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

@tool
async def publish_discord_message_tool(message: str, state: Annotated[dict, InjectedState], show_message: bool = True):
    """
    Envoie un message sur Discord via une interaction.

    Cette fonction envoie un message en réponse à une interaction Discord. Si la réponse a
    déjà été envoyée, elle utilise `followup.send()`, sinon elle utilise `response.send_message()`.

    :param message: Le message à envoyer sur Discord.
    :param state: Un dictionnaire contenant l'état de l'interaction Discord, incluant l'objet `interaction`.
    :param show_message: Détermine si le message est visible pour tous (`True`) ou seulement pour l'utilisateur (`False`).
    
    :raises KeyError: Si l'interaction n'est pas trouvée dans l'état fourni.
    """
    interaction: discord.Interaction = state["interaction"]

    await publish_discord_message(message, interaction, show_message)
    return True


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


    movie_night_prompt = f"Crée un sondage engageant pour une soirée film en utilisant les outils à ta disposition.\
    Rédige une question courte et conviviale, comme : 'On regarde quoi pour la soirée film ? :)' ou une formulation similaire.\
    Utilise une liste de titres de films séparés par des barres verticales '|' pour les choix de réponse.\
    La liste des films est la suivante : '{movies_list}'.\
    Une fois le sondage publié, effectue une recherche sur internet avec Tavily pour obtenir un synopsis idéalement en français de chaque film présent dans le sondage.\
    Publie ensuite un message sur discord en utilisant les sondage récupéré en suivant ce modèle : ## <Nom du film> :\n ||<synopsis du film>||\
    Et enfin, termine en publiant sur discord le message final suivant :'## Hey <@&{movie_night_role_id}> ! N'oubliez pas de voter pour le film de la \
    watchparty ! La soirée film aura lieu {discord_timestamps(prochain_mercredi())} ({discord_timestamps(prochain_mercredi(), format='R')}).'\
    Ne publie ce message qu’après avoir posté les synopsis. Suis cet ordre strictement et n’invente pas de date ou d’informations supplémentaires."


    tools = [publish_poll,publish_discord_message_tool, tavily_search_tool]
    tool_node = ToolNode(tools)
    agent = create_react_agent(llm, tools=tool_node, state_schema=State)

    query = {
        "messages": [{"type": "user", "content": movie_night_prompt}],
        "interaction": interaction,
    }

    respond = await agent.ainvoke(query, stream_mode="values")
    respond = respond["messages"]

    for msg in respond:
        msg.pretty_print()

# @tasks.loop(seconds=5.0, count=5)
# async def slow_count():
#     print(slow_count.current_loop)


bot.run(discord_token)
