from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "cleanroom.sqlite3"
        with self.connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evidence (digest TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, digest TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS crawl_cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (job_id TEXT, seq INTEGER, payload TEXT NOT NULL,
                                                  PRIMARY KEY(job_id, seq));
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def save_job(self, job):
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?, ?)",
                (job["id"], json.dumps(job, ensure_ascii=False)),
            )

    def jobs(self):
        with self.connect() as conn:
            return [json.loads(row[0]) for row in conn.execute("SELECT payload FROM jobs")]

    def cached(self, key, now):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM crawl_cache WHERE key=? AND at>?", (key, now - 86400)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def put_evidence(self, key, payload, now):
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO evidence VALUES (?, ?)",
                (payload["sha256"], json.dumps(payload, ensure_ascii=False)),
            )
            if payload.get("status") == 200:
                conn.execute(
                    "INSERT OR REPLACE INTO crawl_cache VALUES (?, ?, ?)",
                    (key, json.dumps(payload, ensure_ascii=False), now),
                )

    def evidence(self, digest):
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM evidence WHERE digest=?", (digest,)).fetchone()
            return json.loads(row[0]) if row else None

    def append_event(self, job_id, event):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO events VALUES (?, ?, ?)",
                (job_id, event["seq"], json.dumps(event, ensure_ascii=False)),
            )

    def events(self, job_id, after=0, limit=None):
        query = "SELECT payload FROM events WHERE job_id=? AND seq>? ORDER BY seq"
        params = [job_id, after]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            return [json.loads(row[0]) for row in conn.execute(query, params)]

    def last_seq(self, job_id):
        with self.connect() as conn:
            return conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM events WHERE job_id=?", (job_id,)
            ).fetchone()[0]
