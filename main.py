import audioop
import json
import os
import queue
import sqlite3
import threading
import time
from typing import Iterable

import dotenv
import discord
from discord.ext import commands
from discord.ext import voice_recv
from vosk import KaldiRecognizer, Model, SetLogLevel


dotenv.load_dotenv(".env")

def chunk_lines(lines: Iterable[str], max_len: int = 1900) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_len and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

KEYWORDS = {w.strip().lower() for w in os.getenv("KEYWORDS", "hello,hi").split(",") if w.strip()}
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "./vosk-model")
DEBUG_VOICE = os.getenv("DEBUG_VOICE", "0") == "1"
keyword_lock = threading.Lock()
keyword_counts: dict[tuple[int, str], int] = {}
user_names: dict[int, str] = {}
if not os.path.isdir(VOSK_MODEL_PATH):
    raise SystemExit(
        "VOSK_MODEL_PATH invalide. Télécharge un modèle Vosk puis "
        "définis VOSK_MODEL_PATH vers le dossier du modèle."
    )

if (not os.path.exists("./data/db.sql")):
    f = open("./data/db.sql", "w")
    f.close()


db_lock = threading.Lock()
db_conn = sqlite3.connect("./data/db.sql", check_same_thread=False)
db_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS keyword_counts (
        user_id INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY (user_id, keyword)
    )
    """
)
db_conn.execute(
    """
    CREATE TABLE IF NOT EXISTS user_names (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )
    """
)
db_conn.commit()


def load_counts_from_db() -> None:
    with db_lock:
        rows = db_conn.execute("SELECT user_id, keyword, count FROM keyword_counts").fetchall()
        name_rows = db_conn.execute("SELECT user_id, name FROM user_names").fetchall()
    with keyword_lock:
        keyword_counts.clear()
        user_names.clear()
        for user_id, keyword, count in rows:
            keyword_counts[(int(user_id), str(keyword))] = int(count)
        for user_id, name in name_rows:
            user_names[int(user_id)] = str(name)


def save_hit_to_db(user_id: int, user_name: str, keyword: str) -> None:
    with db_lock:
        db_conn.execute(
            """
            INSERT INTO keyword_counts (user_id, keyword, count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, keyword)
            DO UPDATE SET count = count + 1
            """,
            (user_id, keyword),
        )
        db_conn.execute(
            """
            INSERT INTO user_names (user_id, name)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET name = excluded.name
            """,
            (user_id, user_name),
        )
        db_conn.commit()


class Transcriber(threading.Thread):
    def __init__(self, keyword_set: set[str], model: Model) -> None:
        super().__init__(daemon=True)
        self.keyword_set = keyword_set
        self.model = model
        self.q: "queue.Queue[tuple[int, str, bytes]]" = queue.Queue()
        self.recognizers: dict[int, KaldiRecognizer] = {}
        self.resample_state: dict[int, object] = {}
        self.last_hit: dict[tuple[int, str], float] = {}

        self.sample_rate = 16000
        self.sample_width = 2

    def submit(self, user_id: int, user_name: str, pcm: bytes) -> None:
        self.q.put((user_id, user_name, pcm))

    def _check_keywords(self, user_id: int, user_name: str, text: str) -> None:
        if not text:
            return
        text = text.lower()
        now = time.time()
        for kw in self.keyword_set:
            if kw and kw in text:
                key = (user_id, kw)
                if now - self.last_hit.get(key, 0.0) < 2.0:
                    continue
                self.last_hit[key] = now
                with keyword_lock:
                    user_names[user_id] = user_name
                    keyword_counts[key] = keyword_counts.get(key, 0) + 1
                save_hit_to_db(user_id, user_name, kw)
                print(f"[VOICE] {user_name}: mot-clé détecté -> {kw} | texte: {text}")

    def run(self) -> None:
        while True:
            user_id, user_name, pcm = self.q.get()
            if not pcm:
                continue

            mono = audioop.tomono(pcm, 2, 0.5, 0.5)
            state = self.resample_state.get(user_id)
            data_16k, new_state = audioop.ratecv(mono, 2, 1, 48000, self.sample_rate, state)
            self.resample_state[user_id] = new_state

            rec = self.recognizers.get(user_id)
            if rec is None:
                rec = KaldiRecognizer(self.model, self.sample_rate)
                self.recognizers[user_id] = rec

            if rec.AcceptWaveform(data_16k):
                result = json.loads(rec.Result())
                self._check_keywords(user_id, user_name, result.get("text", ""))
            else:
                partial = json.loads(rec.PartialResult()).get("partial", "")
                self._check_keywords(user_id, user_name, partial)


SetLogLevel(-1)
_model = Model(VOSK_MODEL_PATH)
load_counts_from_db()
_transcriber = Transcriber(KEYWORDS, _model)
_transcriber.start()


def channel_has_nonbot(channel: discord.VoiceChannel | discord.StageChannel) -> bool:
    return any(not m.bot for m in channel.members)


@bot.event
async def on_ready() -> None:
    print(f"Connected as {bot.user}")


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState | None,
    after: discord.VoiceState | None,
) -> None:
    if member.bot:
        return

    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if voice_client and voice_client.channel and not channel_has_nonbot(voice_client.channel):
        await voice_client.disconnect(force=True)
        return

    if after is None or after.channel is None:
        return

    if voice_client and voice_client.channel == after.channel:
        return

    if voice_client and not isinstance(voice_client, voice_recv.VoiceRecvClient):
        await voice_client.disconnect(force=True)
        voice_client = None

    if voice_client:
        await voice_client.move_to(after.channel)
    else:
        voice_client = await after.channel.connect(cls=voice_recv.VoiceRecvClient)

    if isinstance(voice_client, voice_recv.VoiceRecvClient) and not voice_client.is_listening():
        if DEBUG_VOICE:
            print(f"[VOICE] Listening in {after.channel.name}")
        voice_client.listen(KeywordSink(_transcriber))


class KeywordSink(voice_recv.AudioSink):
    def __init__(self, transcriber: Transcriber) -> None:
        super().__init__()
        self.transcriber = transcriber

    def wants_opus(self) -> bool:
        return False

    def write(self, user: discord.Member | discord.User | None, data: voice_recv.VoiceData) -> None:
        if user is None or user.bot:
            return
        if data.pcm:
            self.transcriber.submit(user.id, user.display_name, data.pcm)
        elif DEBUG_VOICE:
            print(f"[VOICE] no pcm from {getattr(user, 'display_name', 'unknown')}")

    def cleanup(self) -> None:
        return



@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    guild_name = message.guild.name if message.guild else "DM"
    channel_name = message.channel.name if isinstance(message.channel, discord.TextChannel) else "Unknown"
    print(f"[{guild_name} | #{channel_name}] {message.author}: {message.content}")

    await bot.process_commands(message)


@bot.command(name="list")
async def list_members(ctx: commands.Context) -> None:
    if ctx.guild is None:
        await ctx.send("Cette commande doit être utilisée dans un serveur.")
        return

    with keyword_lock:
        items = [((user_id, kw), count) for (user_id, kw), count in keyword_counts.items()]

    if not items:
        await ctx.send("Aucun mot-clé détecté pour l'instant.")
        return

    items.sort(key=lambda it: it[1], reverse=True)
    rank_emojis = ["🥇", "🥈", "🥉"]
    lines: list[str] = []
    for idx, ((user_id, _), count) in enumerate(items, start=1):
        medal = rank_emojis[idx - 1] if idx <= 3 else "🏅"
        name = user_names.get(user_id, f"User {user_id}")
        lines.append(f"{medal} #{idx} — {name} x{count}")

    for chunk in chunk_lines(lines):
        await ctx.send(chunk)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN manquant dans les variables d'environnement.")
    bot.run(token)


if __name__ == "__main__":
    main()
