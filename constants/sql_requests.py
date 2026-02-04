
CREATE_KEYWORDS_TABLE_REQUEST = """
  CREATE TABLE IF NOT EXISTS keyword_counts (
    discord_id INTEGER NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (discord_id)
  );
"""

GET_KEYWORD_COUNTS_REQUEST = """
  SELECT *
  FROM keyword_counts kc;
"""

GET_KEYWORD_COUNT_REQUEST = """
  SELECT *
  FROM keyword_counts kc
  WHERE discord_id = ?;
"""


CREATE_KEYWORD_COUNT_REQUEST = """
  INSERT INTO keyword_counts
  VALUES (?, ?);
"""

INCREMENT_KEYWORD_COUNT_REQUEST = """
  UPDATE keyword_counts
  SET count = count + ?
  WHERE discord_id = ?;
"""