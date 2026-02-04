import os
import sqlite3
from constants.sql_requests import CREATE_KEYWORDS_TABLE_REQUEST, GET_KEYWORD_COUNTS_REQUEST, GET_KEYWORD_COUNT_REQUEST, CREATE_KEYWORD_COUNT_REQUEST, INCREMENT_KEYWORD_COUNT_REQUEST
from models.keyword_count import KeywordCount

class Database:

  def __init__(self):
    if (not os.path.exists('./data')):
      os.mkdir("./data", 711)
    self.conn = sqlite3.connect("./data/db.sql", check_same_thread=False)
    self.create_database()

  def create_database(self) -> None:
    self.conn.execute(CREATE_KEYWORDS_TABLE_REQUEST)
    self.conn.commit()

  def get_keywords_counts(self) -> list[KeywordCount]:
    request = self.conn.execute(GET_KEYWORD_COUNTS_REQUEST)
    keyword_counts: list[KeywordCount] = []
    for row in request.fetchall():
      current = KeywordCount(row[0], row[1])
      keyword_counts.append(current)
    return keyword_counts

  def addKeyword(self, discord_id: int, addCount: int):
    request = self.conn.execute(GET_KEYWORD_COUNT_REQUEST, (discord_id,)) # type: ignore
    if (request.fetchone() is None):
      self.conn.execute(CREATE_KEYWORD_COUNT_REQUEST, (discord_id,addCount))  # type: ignore
    else:
      self.conn.execute(INCREMENT_KEYWORD_COUNT_REQUEST, (addCount,discord_id)) # type: ignore
    self.conn.commit()