import os
import dotenv
from vosk import Model # type: ignore
from discord.ext import commands, voice_recv
from discord import Member, VoiceState, VoiceClient

from constants.environment import VOSK_MODEL_PATH

from multi_user_sink import MultiUserSink
from utils import chunk_lines
from database import Database
from bot import Bot

dotenv.load_dotenv(".env")

bot = Bot()
database = Database()
model = Model(VOSK_MODEL_PATH)

@bot.command(name="list")
async def list_keyword_counts(ctx: commands.Context[Bot]) -> None:
  if ctx.guild is None:
      await ctx.send("Cette commande doit être utilisée dans un serveur.")
      return

  keyword_counts = database.get_keywords_counts()
  if not keyword_counts:
      await ctx.send("Aucun mot-clé détecté pour l'instant.")
      return

  keyword_counts.sort(key=lambda it: it.count, reverse=True)
  rank_emojis = ["🥇", "🥈", "🥉"]
  lines: list[str] = []
  for idx, keyword_count in enumerate(keyword_counts, start=1):
      medal = rank_emojis[idx - 1] if idx <= 3 else "🏅"
      user = await bot.fetch_user(keyword_count.discord_id)
      lines.append(f"{medal} #{idx} — {user.name} x{keyword_count.count}")

  for chunk in chunk_lines(lines):
      await ctx.send(chunk)


@bot.event
async def on_voice_state_update(
    member: Member,
    before: VoiceState | None,
    after: VoiceState | None,
) -> None:
    if member.bot:
        return

    voice_clients: list[VoiceClient] = []
    for voice_client in bot.voice_clients:
        vc = VoiceClient(voice_client.client, voice_client.channel)
        voice_clients.append(vc)

    if after and after.channel and after.channel.id:
        print(f"[VOICE] Connected to {after.channel.name}")
        voice_client = await after.channel.connect(cls=voice_recv.VoiceRecvClient)
        sink = MultiUserSink(model, database)
        voice_client.listen(sink)

    for vc in voice_clients:
        if len(vc.channel.members) == 1:
            await vc.disconnect(force=True)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN manquant dans les variables d'environnement.")
    bot.run(token)


if __name__ == "__main__":
    main()