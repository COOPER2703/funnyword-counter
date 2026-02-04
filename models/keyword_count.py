
from dataclasses import dataclass


@dataclass()
class KeywordCount:
  discord_id: int
  count: int