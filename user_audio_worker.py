import json
from threading import Thread
from discord import User, Member
from queue import Queue, Empty
import numpy as np
from vosk import Model, KaldiRecognizer # type: ignore
from scipy.signal import resample_poly # type: ignore
from database import Database

from constants.environment import KEYWORD

class UserAudioWorker(Thread):
    def __init__(self, user: User | Member, model: Model, database: Database):
        super().__init__(daemon=True)
        self.recognizer = KaldiRecognizer(model, 16000)
        self.user = user
        self.queue: Queue[bytes] = Queue()
        self.database = database
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.queue.get(timeout=1)
                self.process_audio(data)
            except Empty:
                continue

    def process_48_to_16K_audio(self, data: bytes) -> bytes:
        audio = np.frombuffer(data, dtype=np.int16)

        # stéréo → mono
        audio = audio.reshape(-1, 2)
        mono = audio.mean(axis=1).astype(np.int16)

        # 48kHz → 16kHz
        downsampled = resample_poly(mono, up=1, down=3) # type: ignore

        return downsampled.astype(np.int16).tobytes() # type: ignore


    def process_audio(self, data: bytes):
        if (not data):
            return

        audio16k = self.process_48_to_16K_audio(data)

        self.recognizer.AcceptWaveform(audio16k) # type: ignore

        partial = json.loads(self.recognizer.PartialResult()) # type: ignore
        text = partial.get("partial", "")

        if text:
            if KEYWORD in text:
                self.database.addKeyword(int(self.user.id))
            self.recognizer.Reset()

    def stop(self):
        self.running = False
