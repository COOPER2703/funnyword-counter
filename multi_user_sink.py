from discord.ext.voice_recv import AudioSink, VoiceData # type: ignore
from discord import Member, User

from database import Database
from user_audio_worker import UserAudioWorker
from vosk import Model; # type: ignore

class MultiUserSink(AudioSink):
  def __init__(self, model: Model, database: Database):
    self.model = model
    self.database = database
    self.workers: dict[int, UserAudioWorker] = {}

  def wants_opus(self):
    return False  # PCM brut

  def write(self, user: Member | User | None, data: VoiceData):
    if user is None:
      return

    if user.id not in self.workers:
      worker = UserAudioWorker(user, self.model, self.database)
      self.workers[user.id] = worker
      worker.start()

    try:
      self.workers[user.id].queue.put(data.pcm)
    except Exception as e:
        print(f"[AUDIO] Erreur audio ignorée pour {user}: {e}")


  def cleanup(self):
    for worker in self.workers.values():
      worker.stop()

