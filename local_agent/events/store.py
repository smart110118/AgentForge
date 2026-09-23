"""SQLite-based Event Store with WAL mode, indices, and time-series query capabilities."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from local_agent.events.schema import StandardAgentEvent


class EventStore:
    """Thread-safe SQLite-backed store for Standard Agent Events."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._mem_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high-concurrency read/write
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _close_connection(self, conn: sqlite3.Connection) -> None:
        if conn is not self._mem_conn:
            conn.close()


    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS events (
                            event_id TEXT PRIMARY KEY,
                            timestamp REAL NOT NULL,
                            client TEXT NOT NULL,
                            observer TEXT NOT NULL,
                            session_id TEXT NOT NULL,
                            event_type TEXT NOT NULL,
                            payload_json TEXT NOT NULL,
                            correlation_id TEXT NOT NULL,
                            parent_event_id TEXT,
                            confidence REAL NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_events_corr ON events(correlation_id);"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);"
                    )
            finally:
                self._close_connection(conn)

    def append(self, event: StandardAgentEvent) -> None:
        """Insert a single SAE event."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    src = event.source.to_dict()
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO events (
                            event_id, timestamp, client, observer, session_id,
                            event_type, payload_json, correlation_id, parent_event_id, confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event.event_id,
                            event.timestamp,
                            src.get("client", ""),
                            src.get("observer", ""),
                            src.get("session_id", ""),
                            str(event.type.value if hasattr(event.type, "value") else event.type),
                            json.dumps(event.payload, ensure_ascii=False),
                            event.correlation_id,
                            event.parent_event_id,
                            event.confidence,
                        ),
                    )
            finally:
                self._close_connection(conn)

    def append_batch(self, events: Iterable[StandardAgentEvent]) -> None:
        """Insert multiple SAE events in a single transaction."""
        records = []
        for e in events:
            src = e.source.to_dict()
            records.append(
                (
                    e.event_id,
                    e.timestamp,
                    src.get("client", ""),
                    src.get("observer", ""),
                    src.get("session_id", ""),
                    str(e.type.value if hasattr(e.type, "value") else e.type),
                    json.dumps(e.payload, ensure_ascii=False),
                    e.correlation_id,
                    e.parent_event_id,
                    e.confidence,
                )
            )
        if not records:
            return

        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO events (
                            event_id, timestamp, client, observer, session_id,
                            event_type, payload_json, correlation_id, parent_event_id, confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        records,
                    )
            finally:
                self._close_connection(conn)

    def query(
        self,
        *,
        session_id: str | None = None,
        correlation_id: str | None = None,
        event_type: str | None = None,
        start_ts: float | None = None,
        end_ts: float | None = None,
        limit: int = 100,
        descending: bool = False,
    ) -> list[StandardAgentEvent]:
        """Query stored events with filtering options."""
        conditions = []
        params: list[Any] = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if correlation_id is not None:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if start_ts is not None:
            conditions.append("timestamp >= ?")
            params.append(start_ts)
        if end_ts is not None:
            conditions.append("timestamp <= ?")
            params.append(end_ts)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_dir = "DESC" if descending else "ASC"
        query_sql = f"""
            SELECT event_id, timestamp, client, observer, session_id,
                   event_type, payload_json, correlation_id, parent_event_id, confidence
            FROM events
            {where_clause}
            ORDER BY timestamp {order_dir}
            LIMIT ?
        """
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(query_sql, params).fetchall()
                results: list[StandardAgentEvent] = []
                for row in rows:
                    payload = json.loads(row["payload_json"])
                    event = StandardAgentEvent.from_dict(
                        {
                            "event_id": row["event_id"],
                            "timestamp": row["timestamp"],
                            "source": {
                                "client": row["client"],
                                "observer": row["observer"],
                                "session_id": row["session_id"],
                            },
                            "type": row["event_type"],
                            "payload": payload,
                            "correlation_id": row["correlation_id"],
                            "parent_event_id": row["parent_event_id"],
                            "confidence": row["confidence"],
                        }
                    )
                    results.append(event)
                return results
            finally:
                self._close_connection(conn)

    def count(self) -> int:
        """Return the total number of events recorded."""
        with self._lock:
            conn = self._get_connection()
            try:
                res = conn.execute("SELECT COUNT(1) FROM events").fetchone()
                return int(res[0]) if res else 0
            finally:
                self._close_connection(conn)
