import os
import discord
import asyncio
from dotenv import load_dotenv
from src.constants import USER_TO_NOTIFY

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def main():
    await client.login(TOKEN)
    # Fetch the user by ID and send them a notification
    for user_id in USER_TO_NOTIFY:
        user = await client.fetch_user(user_id)
        
        notification_message = (
        "Hello! This is a notification to tell you that"
        "I've been updated with new features!\n"
        "You can go check out over here: https://github.com/White-On/Discord_bot"
        "Here is a quick recap how to fetch the latest version of the bot and launch it:\n" 
        "1. Pull the latest version of the code from the GitHub repository.\n" 
        "```git pull```\n"
        "2. Create a virtual environment and activate it.\n"
        "3. Install the required dependencies\n"
        "```pip install uv```\n"
        "```uv sync```\n"
        "4. Run the bot\n"
        "```uv run main.py```\n"
        )

        await user.send(notification_message)
        print(f"Notification sent to {user.id}")
    await client.close()

asyncio.run(main())