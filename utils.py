from typing import Iterable
from discord import VoiceChannel, StageChannel

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

def channel_has_nonbot(channel: VoiceChannel | StageChannel) -> bool:
    return any(not m.bot for m in channel.members)
