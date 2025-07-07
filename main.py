import discord
from discord.ext import commands, tasks
import asyncio
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🔧 CONFIGURATION FROM ENV
NSFW_GUILD_ID = int(os.getenv("NSFW_GUILD_ID"))
MAIN_GUILD_ID = int(os.getenv("MAIN_GUILD_ID"))
ACCESS_ROLE_ID = int(os.getenv("ACCESS_ROLE_ID"))
ACCESS_CHANNEL_ID = int(os.getenv("ACCESS_CHANNEL_ID"))  # Message to new users
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))        # Logging channel
MAIN_SERVER_INVITE = os.getenv("MAIN_SERVER_INVITE", "https://discord.gg/YOUR_LINK")
WAIT_MINUTES = int(os.getenv("WAIT_MINUTES", 10))

@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user}")
    check_main_server_membership.start()

@bot.event
async def on_member_join(member):
    if member.guild.id != NSFW_GUILD_ID:
        return

    channel = bot.get_channel(ACCESS_CHANNEL_ID)
    if channel:
        await channel.send(
            f"Hey <@{member.id}>, please join our Main Server to unlock access: {MAIN_SERVER_INVITE}"
        )

    await asyncio.sleep(WAIT_MINUTES * 60)

    main_guild = bot.get_guild(MAIN_GUILD_ID)
    if not main_guild:
        print("[ERROR] Main Guild not found.")
        return

    if main_guild.get_member(member.id):
        role = member.guild.get_role(ACCESS_ROLE_ID)
        if role:
            await member.add_roles(role, reason="Verified in Main Server")
            print(f"[ACCESS GRANTED] {member.name}")
    else:
        print(f"[NOT FOUND] {member.name} not in Main Server.")

@tasks.loop(minutes=10)
async def check_main_server_membership():
    nsfw_guild = bot.get_guild(NSFW_GUILD_ID)
    main_guild = bot.get_guild(MAIN_GUILD_ID)
    if not nsfw_guild or not main_guild:
        print("[ERROR] One of the guilds not found.")
        return

    role = nsfw_guild.get_role(ACCESS_ROLE_ID)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    if not role:
        print("[ERROR] Access role not found.")
        return

    for member in role.members:
        if not main_guild.get_member(member.id):
            try:
                await member.remove_roles(role, reason="Left Main Server")
                if log_channel:
                    await log_channel.send(
                        f"<@{member.id}> has left the Main Server, so their access has been removed."
                    )
                print(f"[ACCESS REMOVED] {member.name}")
            except Exception as e:
                print(f"[ERROR] Could not remove role from {member.name}: {e}")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
