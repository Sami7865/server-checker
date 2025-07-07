import sys
# Patch for Python 3.13+ missing audioop module
if sys.version_info >= (3, 13):
    import types
    sys.modules['audioop'] = types.SimpleNamespace()

import discord
from discord.ext import commands, tasks
import asyncio
import os
from keep_alive import keep_alive

# Intents
intents = discord.Intents.default()
intents.members = True
intents.guilds = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Environment config
NSFW_GUILD_ID = int(os.getenv("NSFW_GUILD_ID"))
MAIN_GUILD_ID = int(os.getenv("MAIN_GUILD_ID"))
ACCESS_ROLE_ID = int(os.getenv("ACCESS_ROLE_ID"))
ACCESS_CHANNEL_ID = int(os.getenv("ACCESS_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
MAIN_SERVER_INVITE = os.getenv("MAIN_SERVER_INVITE", "https://discord.gg/YOUR_LINK")
TOKEN = os.getenv("DISCORD_TOKEN")

# Runtime config
config = {
    "wait_minutes": float(os.getenv("WAIT_MINUTES", 10)),
    "auto_scan_interval": int(os.getenv("AUTO_SCAN_INTERVAL", 30))
}

@bot.event
async def on_ready():
    print(f"[READY] Logged in as {bot.user}")
    check_main_server_membership.start()
    auto_scan_all_members.change_interval(minutes=config["auto_scan_interval"])
    auto_scan_all_members.start()
    try:
        await tree.sync()
        print("[SYNCED] Slash commands")
    except Exception as e:
        print(f"[ERROR] Slash command sync failed: {e}")

@bot.event
async def on_member_join(member):
    if member.guild.id != NSFW_GUILD_ID:
        return
    channel = bot.get_channel(ACCESS_CHANNEL_ID)
    if channel:
        await channel.send(f"Hey <@{member.id}>, please join our Main Server to unlock access: {MAIN_SERVER_INVITE}")
    await asyncio.sleep(config["wait_minutes"] * 60)

    main_guild = bot.get_guild(MAIN_GUILD_ID)
    if not main_guild:
        return
    if main_guild.get_member(member.id):
        role = member.guild.get_role(ACCESS_ROLE_ID)
        if role:
            await member.add_roles(role, reason="Verified via join check")

@tasks.loop(minutes=10)
async def check_main_server_membership():
    nsfw = bot.get_guild(NSFW_GUILD_ID)
    main = bot.get_guild(MAIN_GUILD_ID)
    role = nsfw.get_role(ACCESS_ROLE_ID)
    log = bot.get_channel(LOG_CHANNEL_ID)

    for member in role.members:
        if not main.get_member(member.id):
            try:
                await member.remove_roles(role, reason="Left Main Server")
                if log:
                    await log.send(f"<@{member.id}> has left the Main Server, so access was removed.")
            except Exception as e:
                print(f"[ERROR] remove role: {e}")

@tasks.loop(minutes=config["auto_scan_interval"])
async def auto_scan_all_members():
    print("[AUTO SCAN] Running...")
    nsfw = bot.get_guild(NSFW_GUILD_ID)
    main = bot.get_guild(MAIN_GUILD_ID)
    role = nsfw.get_role(ACCESS_ROLE_ID)
    log = bot.get_channel(LOG_CHANNEL_ID)
    added, removed = 0, 0

    for m in nsfw.members:
        if m.bot:
            continue
        in_main = main.get_member(m.id)
        has_role = role in m.roles
        try:
            if in_main and not has_role:
                await m.add_roles(role, reason="Auto-scan verified")
                added += 1
                if log: await log.send(f"✅ Access given to <@{m.id}> via auto-scan")
            elif not in_main and has_role:
                await m.remove_roles(role, reason="Auto-scan cleanup")
                removed += 1
                if log: await log.send(f"❌ Access removed from <@{m.id}> (not in Main Server)")
        except Exception as e:
            print(f"[ERROR] Auto-scan: {e}")
    print(f"[AUTO SCAN DONE] ✅ {added} added, ❌ {removed} removed")

# Slash command: Show config
@tree.command(name="config_status", description="Show current bot config")
async def config_status(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"🔧 Current Config:\n• Wait Time: **{config['wait_minutes']}** min\n• Auto-Scan Interval: **{config['auto_scan_interval']}** min",
        ephemeral=True
    )

# Slash command: Set wait time
@tree.command(name="set_wait_time", description="Set wait time (in minutes) before checking user")
async def set_wait_time(interaction: discord.Interaction, minutes: float):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
        return

    config['wait_minutes'] = minutes
    await interaction.response.send_message(f"⏱️ Wait time updated to **{minutes}** minutes.", ephemeral=True)

# Slash command: Set auto-scan interval
@tree.command(name="set_auto_scan_interval", description="Set how often auto-scan runs (in minutes)")
async def set_auto_scan_interval(interaction: discord.Interaction, minutes: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
        return

    config['auto_scan_interval'] = minutes
    auto_scan_all_members.change_interval(minutes=minutes)
    await interaction.response.send_message(f"🔁 Auto-scan interval updated to **{minutes}** minutes.", ephemeral=True)

# Slash command: Manual scan
@tree.command(name="scan_existing", description="Manually scan all NSFW members for Main Server access")
async def scan_existing(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions.", ephemeral=True)
        return

    await interaction.response.send_message("🔍 Scanning NSFW server...", ephemeral=True)
    nsfw = bot.get_guild(NSFW_GUILD_ID)
    main = bot.get_guild(MAIN_GUILD_ID)
    role = nsfw.get_role(ACCESS_ROLE_ID)
    log = bot.get_channel(LOG_CHANNEL_ID)

    added = 0
    for m in nsfw.members:
        if m.bot:
            continue
        if main.get_member(m.id) and role not in m.roles:
            try:
                await m.add_roles(role, reason="Manual scan")
                added += 1
                if log:
                    await log.send(f"✅ Access given to <@{m.id}> via manual scan")
            except Exception as e:
                print(f"[ERROR] Manual scan: {e}")

    await interaction.followup.send(f"✅ Manual scan complete. Access given to **{added}** users.", ephemeral=True)

# Run bot with keep_alive
keep_alive()
bot.run(TOKEN)
