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
    Return the next Wednesday at 20:30 from a given date.
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
    Create a Discord timestamp string from a datetime object.
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
    Publish a message in Discord, either as an initial response or a follow-up.
    """
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=not show_message, **kwargs)
    else:
        await interaction.response.send_message(
            message, ephemeral=not show_message, **kwargs
        )


def images_urls_to_bytes_horizontal(
    urls: list[str], target_height: int | None = None, background=(255, 255, 255, 0)
) -> bytes:
    """
    Download images from URLs, resize them to the same height, concatenate them horizontally, and return the result as bytes.
    """

    images: list[Image.Image] = []

    
    for url in urls:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGBA")
        images.append(img)

    if not images:
        raise ValueError("Aucune image fournie")

    
    if target_height is None:
        target_height = max(img.height for img in images)

    
    resized_images: list[Image.Image] = []
    total_width = 0

    for img in images:
        ratio = target_height / img.height
        new_width = int(img.width * ratio)
        resized = img.resize((new_width, target_height), Image.LANCZOS)
        resized_images.append(resized)
        total_width += new_width

    
    final_img = Image.new("RGBA", (total_width, target_height), background)

    x_offset = 0
    for img in resized_images:
        final_img.paste(img, (x_offset, 0), img)
        x_offset += img.width

    
    buffer = BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.getvalue()

def parse_mentions(
    mentions: list[str],
    all_users: list[discord.Member],
    console,
    warning_style,
) -> tuple[list[int], list[str]]:
    """
    Parse a list of Discord mentions and separate user mentions from role mentions.
    """
    selected_members: list[int] = []
    role_mentions: list[str] = []

    for mention in mentions:
        # Skip @everyone and @here mentions
        if mention == "@everyone" or mention == "@here":
            console.print(
                f"⚠ Mention '{mention}' not supported, skipping...", style=warning_style
            )
            continue
        if not mention.startswith("<@&"):
            # User mention
            user_id = get_user_id_from_mention(mention)
            if check_if_user_exist(user_id, all_users):
                # User exists
                selected_members.append(user_id)
            else:
                console.print(
                    f"⚠ User {mention} not found in server", style=warning_style
                )
        else:
            role_mentions.append(mention)

    return selected_members, role_mentions

def fetch_user_from_role(
    role_mention: str,
    all_users: list[discord.Member],
    console,
    warning_style,
) -> list[int]:
    """
    Collect user IDs of all members who have a specific role.
    """
    role_id = get_role_id_from_mention(role_mention)
    selected_members: list[int] = []

    for member in all_users:
        if any(role.id == role_id for role in member.roles):
            selected_members.append(member.id)

    if not selected_members:
        console.print(
            f"⚠ No users found with role {role_mention}", style=warning_style
        )

    return selected_members