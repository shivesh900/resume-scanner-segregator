"""Tiny SQLite persistence layer (stdlib only)."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    profile TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    score REAL NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_candidates_job ON candidates(job_id);
"""

STATUSES = {"new", "shortlisted", "rejected"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str = ":memory:"):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    # jobs -----------------------------------------------------------------
    def add_job(self, title: str, description: str, profile: dict) -> dict:
        job = {"id": uuid.uuid4().hex[:12], "title": title, "description": description,
               "profile": profile, "created_at": _now()}
        with self._lock, self.conn:
            self.conn.execute("INSERT INTO jobs VALUES (?,?,?,?,?)",
                              (job["id"], title, description, json.dumps(profile), job["created_at"]))
        return job

    def _job_row(self, row) -> dict:
        d = dict(row)
        d["profile"] = json.loads(d["profile"])
        counts = {p: 0 for p in ("High", "Medium", "Low")}
        for r in self.conn.execute(
                "SELECT priority, COUNT(*) n FROM candidates WHERE job_id=? GROUP BY priority", (d["id"],)):
            counts[r["priority"]] = r["n"]
        d["counts"] = counts
        return d

    def list_jobs(self) -> List[dict]:
        rows = self.conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [self._job_row(r) for r in rows]

    def get_job(self, job_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job_row(row) if row else None

    def delete_job(self, job_id: str) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        return cur.rowcount > 0

    # candidates -------------------------------------------------------------
    def add_candidate(self, job_id: str, data: dict) -> dict:
        cid = uuid.uuid4().hex[:12]
        created = _now()
        with self._lock, self.conn:
            self.conn.execute("INSERT INTO candidates VALUES (?,?,?,?,?,?,?)",
                              (cid, job_id, json.dumps(data), data["score"], data["priority"], "new", created))
        return {**data, "id": cid, "job_id": job_id, "status": "new", "created_at": created}

    def _cand_row(self, row) -> dict:
        d = json.loads(row["data"])
        d.update(id=row["id"], job_id=row["job_id"], status=row["status"], created_at=row["created_at"])
        return d

    def list_candidates(self, job_id: str, priority: Optional[str] = None) -> List[dict]:
        q, args = "SELECT * FROM candidates WHERE job_id=?", [job_id]
        if priority:
            q += " AND priority=?"
            args.append(priority)
        q += " ORDER BY score DESC"
        return [self._cand_row(r) for r in self.conn.execute(q, args).fetchall()]

    def get_candidate(self, cid: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        return self._cand_row(row) if row else None

    def set_status(self, cid: str, status: str) -> Optional[dict]:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        with self._lock, self.conn:
            self.conn.execute("UPDATE candidates SET status=? WHERE id=?", (status, cid))
        return self.get_candidate(cid)
