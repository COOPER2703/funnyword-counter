import os

KEYWORD = os.getenv("KEYWORD", "hello")
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "./vosk-model")