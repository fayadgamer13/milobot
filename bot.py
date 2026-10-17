import datetime
import os
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 1. Setup Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for member join/leave, role tracking, and timeouts

bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)

# --- Auto-Mod Configuration ---
BAD_WORDS = ["fuck", "bitch", "nigger", "jackass", "motherfucker", "jack ass", "mother fucker", "pussy", "penis"]


# --- Helper Function for Admin/Leader Check ---
def is_admin():
  async def predicate(ctx):
    role_names = [role.name for role in ctx.author.roles]
    if "Admin" not in role_names and "Leader" not in role_names:
      await ctx.send(
          "❌ You must have the `@Admin` or `@Leader` role to use this command.",
          delete_after=5,
      )
      return False
    return True

  return commands.check(predicate)


# --- Event: Bot Ready ---
@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  print("------")


# ==========================================
# 📋 LOGGING & AUTO-MOD EVENTS
# ==========================================


async def send_log(guild, message):
  """Helper to send messages to the 'logs' channel."""
  logs_channel = discord.utils.get(guild.text_channels, name="logs")
  if logs_channel:
    await logs_channel.send(message)


@bot.event
async def on_message(message):
  """Handles message events for Auto-Moderation and commands."""
  if message.author == bot.user:
    return

  # --- Auto-Moderation (Bad Word Filter) ---
  if message.guild and not message.author.bot:
    role_names = [role.name for role in message.author.roles]
    is_privileged = "Admin" in role_names or "Leader" in role_names

    if not is_privileged:
      content_lower = message.content.lower()
      if any(word in content_lower for word in BAD_WORDS):
        try:
          await message.delete()
          duration = datetime.timedelta(minutes=5)
          await message.author.timeout(
              duration, reason="Auto-mod: Used a prohibited word."
          )
          await send_log(
              message.guild,
              f"🛑 **Auto-Mod Log:** {message.author.mention} was timed out for"
              " **5 minutes** for using a prohibited word in"
              f" {message.channel.mention}.\n> *Message:* `{message.content}`",
          )
        except discord.Forbidden:
          print("Missing permissions to timeout the user or delete messages.")
        except discord.HTTPException:
          pass
        return

  await bot.process_commands(message)


@bot.event
async def on_command(ctx):
  """Logs when any user runs a command."""
  await send_log(
      ctx.guild,
      f"💻 **Command Log:** `{ctx.message.content}` executed by"
      f" {ctx.author.mention} in {ctx.channel.mention}",
  )


@bot.event
async def on_member_join(member):
  """Logs when a user joins the server."""
  await send_log(
      member.guild, f"📥 **Member Joined:** {member.mention} has joined the server."
  )


@bot.event
async def on_member_remove(member):
  """Logs when a user leaves the server."""
  await send_log(
      member.guild, f"📤 **Member Left:** {member.mention} has left the server."
  )


@bot.event
async def on_member_update(before, after):
  """Logs timeouts and untimeouts."""
  if before.timed_out_until != after.timed_out_until:
    if after.timed_out_until:
      await send_log(
          after.guild,
          f"⏳ **Timeout Log:** {after.mention} has been timed out until"
          f" {after.timed_out_until.strftime('%Y-%m-%d %H:%M:%S UTC')}.",
      )
    else:
      await send_log(
          after.guild,
          f"🔊 **Untimeout Log:** Timeout was removed for {after.mention}.",
      )


# ==========================================
# 🛡️ ADMIN/LEADER COMMANDS
# ==========================================


@bot.command(name="ban")
@is_admin()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
  await member.ban(reason=reason)
  await ctx.send(f"✅ Banned {member.mention}. Reason: {reason}")


@bot.command(name="unban")
@is_admin()
async def unban(ctx, *, member_name):
  banned_users = await ctx.guild.bans()
  member_name, *discriminator = member_name.split("#")

  for ban_entry in banned_users:
    user = ban_entry.user
    if user.name == member_name:
      await ctx.guild.unban(user)
      await ctx.send(f"✅ Unbanned {user.mention}.")
      return
  await ctx.send(f"❌ User `{member_name}` not found in ban list.")


@bot.command(name="timeout")
@is_admin()
async def timeout(
    ctx, member: discord.Member, minutes: int, *, reason="No reason provided"
):
  duration = datetime.timedelta(minutes=minutes)
  await member.timeout(duration, reason=reason)
  await ctx.send(
      f"✅ Timed out {member.mention} for {minutes} minute(s). Reason: {reason}"
  )


@bot.command(name="untimeout")
@is_admin()
async def untimeout(ctx, member: discord.Member, *, reason="No reason provided"):
  await member.timeout(None, reason=reason)
  await ctx.send(f"✅ Removed timeout from {member.mention}. Reason: {reason}")


@bot.command(name="unlockall")
@is_admin()
async def unlockall(ctx):
  """Unlocks all text channels in the server so everyone can chat."""
  guild = ctx.guild
  for channel in guild.text_channels:
    await channel.set_permissions(guild.default_role, send_messages=True)

  await ctx.send(
      "🔓 **Server Unlocked:** All text channels have been unlocked for"
      " everyone."
  )
  await send_log(
      guild,
      f"🔓 **Server Unlocked:** All text channels were unlocked by"
      f" {ctx.author.mention}.",
  )


@bot.command(name="help")
async def custom_help(ctx):
  role_names = [role.name for role in ctx.author.roles]
  is_user_privileged = "Admin" in role_names or "Leader" in role_names

  embed = discord.Embed(
      title="🤖 Bot Command Directory", color=discord.Color.blue()
  )

  embed.add_field(
      name="👤 Member Commands",
      value=(
          "`?roles` - View and select/de-select available roles\n`?report"
          " @username [reason]` - Report a user to staff\n`?joke` - Get a random"
          " daily joke"
      ),
      inline=False,
  )

  if is_user_privileged:
    embed.add_field(
        name="🛠️ Staff Commands (Admin/Leader Only)",
        value=(
            "`?ban @username [reason]` - Ban a user\n`?unban @username` - Unban"
            " a user\n`?timeout @username [minutes] [reason]` - Timeout a"
            " user\n`?untimeout @username [reason]` - Remove timeout\n`?unlockall`"
            " - Unlock all text channels in the server\n`?help` - Show this"
            " help menu"
        ),
        inline=False,
    )
  else:
    embed.add_field(
        name="🛠️ Staff Commands",
        value=(
            "*You do not have the `@Admin` or `@Leader` role to view admin"
            " commands.* Restricted."
        ),
        inline=False,
    )

  await ctx.send(embed=embed)


# ==========================================
# 👥 USER COMMANDS
# ==========================================


@bot.command(name="joke")
async def joke(ctx):
  """Fetches a random joke from an API."""
  async with aiohttp.ClientSession() as session:
    async with session.get(
        "https://official-joke-api.appspot.com/random_joke"
    ) as response:
      if response.status == 200:
        data = await response.json()
        setup = data["setup"]
        punchline = data["punchline"]
        await ctx.send(f"😂 **{setup}**\n||{punchline}||")
      else:
        await ctx.send("❌ Couldn't fetch a joke right now. Try again later!")


class RoleSelectView(discord.ui.View):

  def __init__(self, guild):
    super().__init__(timeout=180)
    self.guild = guild
    self.add_role_select()

  def add_role_select(self):
    roles = [
        r
        for r in self.guild.roles
        if r.name not in ["Admin", "Leader"]
        and r != self.guild.default_role
        and not r.managed
    ]

    if not roles:
      return

    options = [
        discord.SelectOption(label=role.name, value=str(role.id))
        for role in roles[:25]
    ]

    select = discord.ui.Select(
        placeholder="Select or de-select your roles...",
        min_values=0,
        max_values=len(options),
        options=options,
    )
    select.callback = self.select_callback
    self.add_item(select)

  async def select_callback(self, interaction: discord.Interaction):
    selected_role_ids = [int(val) for val in interaction.data["values"]]
    member = interaction.user

    all_selectable_roles = [
        r
        for r in self.guild.roles
        if r.name not in ["Admin", "Leader"]
        and r != self.guild.default_role
        and not r.managed
    ]

    added = []
    removed = []

    for role in all_selectable_roles:
      if role.id in selected_role_ids:
        if role not in member.roles:
          await member.add_roles(role)
          added.append(role.name)
      else:
        if role in member.roles:
          await member.remove_roles(role)
          removed.append(role.name)

    msg = "Roles updated successfully!"
    if added:
      msg += f"\nAdded: {', '.join(added)}"
    if removed:
      msg += f"\nRemoved: {', '.join(removed)}"

    await interaction.response.send_message(msg, ephemeral=True)


@bot.command(name="roles")
async def roles(ctx):
  view = RoleSelectView(ctx.guild)
  if not view.children:
    await ctx.send(
        "❌ There are no configurable roles available other than staff roles."
    )
    return
  await ctx.send(
      "👇 **Role Selector:** Choose your desired roles from the menu below.",
      view=view,
  )


@bot.command(name="report")
async def report(ctx, member: discord.Member, *, reason: str):
  await ctx.message.delete()

  report_message = (
      f"🚨 **User Report:**\n"
      f"• **Offender:** {member.mention} (`{member.id}`)\n"
      f"• **Reported By:** {ctx.author.mention}\n"
      f"• **Reason:** {reason}\n"
      f"• **Channel:** {ctx.channel.mention}"
  )

  await send_log(ctx.guild, report_message)
  await ctx.send(
      f"✅ Thank you {ctx.author.mention}, your report has been sent to staff.",
      delete_after=5,
  )


# --- Run the Bot ---
bot.run(TOKEN)