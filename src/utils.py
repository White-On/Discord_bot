"""
Utility functions for the Discord bot
"""

import discord
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PIL import Image
from io import BytesIO


PARIS_TZ = ZoneInfo("Europe/Paris")


def get_role_id_from_mention(mention: str) -> int:
    """Extract role ID from a Discord role mention string"""
    return int(mention.replace("<@&", "").replace(">", ""))


def get_user_id_from_mention(mention: str) -> int:
    """Extract user ID from a Discord user mention string"""
    return int(mention.replace("<@", "").replace(">", ""))


def check_if_user_exist(user_id: int, all_user: list) -> bool:
    """Check if a user exists in a list of users"""
    print(all_user)
    for user in all_user:
        if user.id == user_id:
            return True
    return False


def prochain_mercredi(date_reference: datetime = None) -> datetime:
    """
    Retourne la date du prochain mercredi à 20h30 à partir de la date de référence donnée.
    Si aucune date de référence n'est fournie, utilise la date actuelle.

    :param date_reference: Une date de référence optionnelle (datetime).
    :return: Un objet datetime représentant le prochain mercredi à 20h30.
    """
    date_reference = date_reference if date_reference else datetime.today()

    # Calcul des jours à ajouter pour atteindre mercredi (mercredi = 2)
    jours_a_ajouter = (
        2 - date_reference.weekday()
    ) % 7 or 7  # Assure le mercredi suivant

    return datetime.combine(
        date_reference.date() + timedelta(days=jours_a_ajouter),
        datetime.min.time().replace(hour=20, minute=30),

    )


def discord_timestamps(date: datetime, format: str = "f") -> str:
    """
    Génère un timestamp Discord à partir d'une date.

    :param date: Un objet datetime
    :param format: Format du timestamp Discord ('F', 'f', 'D', 'd', 'T', 't', 'R')
    :return: Une chaîne de caractères compatible avec Discord
    """
    accepted_formats = {"F", "f", "D", "d", "T", "t", "R"}

    if format not in accepted_formats:
        raise ValueError(
            f"Format non pris en charge. Formats acceptés : {', '.join(accepted_formats)}"
        )

    timestamp = int(date.timestamp())  # Convertir en timestamp Unix
    return f"<t:{timestamp}:{format}>"


async def publish_discord_message(
    message: str, interaction: discord.Interaction, show_message: bool = True, **kwargs
):
    """
    Envoie un message sur Discord via une interaction.

    Cette fonction envoie un message en réponse à une interaction Discord. Si la réponse a
    déjà été envoyée, elle utilise `followup.send()`, sinon elle utilise `response.send_message()`.

    :param message: Le message à envoyer sur Discord.
    :param interaction: contenant l'état de l'interaction Discord
    :param show_message: Détermine si le message est visible pour tous (`True`) ou seulement pour l'utilisateur (`False`).
    """
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=not show_message, **kwargs)
    else:
        await interaction.response.send_message(message, ephemeral=not show_message, **kwargs)

def images_urls_to_bytes_horizontal(
    urls: list[str],
    target_height: int | None = None,
    background=(255, 255, 255, 0)
) -> bytes:
    """
    Télécharge des images depuis des URLs, les colle horizontalement
    et retourne l'image finale en bytes (PNG).
    """

    images: list[Image.Image] = []

    # 1. Télécharger les images
    for url in urls:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGBA")
        images.append(img)

    if not images:
        raise ValueError("Aucune image fournie")

    # 2. Déterminer la hauteur cible
    if target_height is None:
        target_height = max(img.height for img in images)

    # 3. Redimensionner à hauteur identique
    resized_images: list[Image.Image] = []
    total_width = 0

    for img in images:
        ratio = target_height / img.height
        new_width = int(img.width * ratio)
        resized = img.resize((new_width, target_height), Image.LANCZOS)
        resized_images.append(resized)
        total_width += new_width

    # 4. Créer l'image finale
    final_img = Image.new("RGBA", (total_width, target_height), background)

    x_offset = 0
    for img in resized_images:
        final_img.paste(img, (x_offset, 0), img)
        x_offset += img.width

    # 5. Conversion en bytes
    buffer = BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.getvalue()
