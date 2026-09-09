import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
import psycopg
from psycopg.rows import dict_row

from app.utils.config import settings
from app.utils.logger import logger


class PostgresClientError(Exception):
    """Base exception for PostgreSQL client errors."""
    pass


class PostgresClient:
    """
    Direct PostgreSQL database client using psycopg 3.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host if host is not None else settings.POSTGRES_HOST
        self.port = port if port is not None else settings.POSTGRES_PORT
        self.dbname = dbname if dbname is not None else settings.POSTGRES_DB
        self.user = user if user is not None else settings.POSTGRES_USER
        
        if password is not None:
            self.password = password
        elif settings.POSTGRES_PASSWORD:
            self.password = settings.POSTGRES_PASSWORD.get_secret_value()
        else:
            self.password = ""

    def _get_connection_kwargs(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "connect_timeout": settings.REQUEST_TIMEOUT,
        }

    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection, None, None]:
        try:
            conn = psycopg.connect(**self._get_connection_kwargs())
            try:
                yield conn
            finally:
                conn.close()
        except Exception as exc:
            logger.error(f"PostgreSQL connection error: {exc}")
            raise PostgresClientError(f"PostgreSQL connection failure: {exc}") from exc

    @contextmanager
    def get_cursor(self, row_factory=None) -> Generator[psycopg.Cursor, None, None]:
        with self.get_connection() as conn:
            rf = row_factory if row_factory is not None else dict_row
            with conn.cursor(row_factory=rf) as cur:
                try:
                    yield cur
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    logger.error(f"PostgreSQL transaction error, rolled back: {exc}")
                    raise PostgresClientError(f"PostgreSQL execution error: {exc}") from exc

    def check_connection(self) -> Dict[str, Any]:
        """
        Perform a safe, non-destructive read query to verify PostgreSQL connection and database/user identity.
        """
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT current_database(), current_user;")
                res = cur.fetchone()
                if not res:
                    raise PostgresClientError("No result from identity query.")
                curr_db = res.get("current_database") or res.get("current_user") # depending on key name
                # Handle dictionary keys
                if isinstance(res, dict):
                    curr_db = res.get("current_database")
                    curr_user = res.get("current_user")
                else:
                    curr_db, curr_user = res[0], res[1]

                return {
                    "status": "connected",
                    "database": curr_db,
                    "user": curr_user,
                    "host": self.host,
                    "port": self.port,
                }
        except Exception as exc:
            raise PostgresClientError(f"PostgreSQL health check failed: {exc}") from exc

    def execute(self, query: str, params: Optional[Union[List[Any], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        with self.get_cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            return []
