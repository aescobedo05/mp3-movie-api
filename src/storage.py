import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(self.db_path)

    def save(self, df):
        """Replace all movie rows in one transaction."""
        connection = get_connection(self.db_path)
        try:
            df = df.astype(object).where(pd.notna(df), None)
            sql_statement = "DELETE FROM movies"
            connection.execute(sql_statement)
            sql_statement = "INSERT INTO movies (title, release_year, rating, genre) VALUES (?, ?, ?, ?)"
            connection.executemany(sql_statement, df.itertuples(index=False, name=None))
            connection.commit()
            logger.debug("Stored movies in SQLite: rows=%s", len(df))
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self):
        """Return the four movie columns as a DataFrame, ordered by id."""
        connection = get_connection(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            sql_statement = "SELECT title, release_year, rating, genre FROM movies ORDER BY id"
            rows = connection.execute(sql_statement).fetchall()
            return pd.DataFrame([dict(row) for row in rows], columns=MOVIE_COLUMNS)
        finally:
            connection.close()


    def select_columns(self, columns, limit=5):
        """Return id plus the requested movie columns, ordered by id."""
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error("Unsupported column: %s", column)
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            sql_statement = f"SELECT {selected_columns} FROM movies ORDER BY id LIMIT ?"
            rows = connection.execute(sql_statement, (limit,)).fetchall()
            logger.debug("rows from %s=%s", columns, len(rows))
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def count_movies(self):
        """Return the number of stored movies using SQL COUNT(*)."""
        connection = get_connection(self.db_path)
        try:
            sql_statement = "SELECT COUNT(*) AS total FROM movies"
            row = connection.execute(sql_statement).fetchone()
            return (row["total"])
        finally:
            connection.close()

    def query_movies(self, columns, min_rating, limit):
        """Return selected fields from matching movies using SQL."""
        self.select_columns(columns)
        connection = get_connection(self.db_path)
        selected_columns = ", ".join(["id"] + columns)
        try:
            sql_statement = f"SELECT {selected_columns} FROM movies WHERE rating >= ? ORDER BY rating desc, id LIMIT ?"
            rows = connection.execute(sql_statement, (min_rating, limit,)).fetchall()
            logger.debug("rows from %s=%s", columns, len(rows))
            return [dict(row) for row in rows]
        finally:
            connection.close()
