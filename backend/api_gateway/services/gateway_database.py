import sqlite3

from backend.shared.config import DATABASE_PATH


def get_gateway_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection
