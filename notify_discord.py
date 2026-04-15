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
        "I've been updated with new features!"
        "Feel free to check them out and let me know what you think!"
        )
        
        await user.send(notification_message)
        print(f"Notification sent to {user.id}")
    await client.close()

asyncio.run(main())