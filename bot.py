from discord import Intents, Status, Game
from discord.ext import commands

class Bot(commands.Bot):

  def __init__(self):
    intents = Intents.default()
    intents.members = True
    intents.guilds = True
    intents.message_content = True
    intents.voice_states = True
    super().__init__(command_prefix="!", intents=intents)

  async def on_ready(self):
    print("Bot ready")
    await self.change_presence(status=Status.online, activity=Game("Counting..."))