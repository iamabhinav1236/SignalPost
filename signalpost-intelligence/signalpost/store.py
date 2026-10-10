"""SQLite persistence with current profile and append-only snapshot history."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any
from .models import CompanyProfile

class ProfileStore:
    def __init__(self, path: str = "data/signalpost.sqlite3"):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS profiles (
          org_number TEXT PRIMARY KEY, name TEXT NOT NULL, profile_json TEXT NOT NULL,
          content_hash TEXT NOT NULL, retrieved_at TEXT NOT NULL, source_updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS snapshots (
          id INTEGER PRIMARY KEY AUTOINCREMENT, org_number TEXT NOT NULL, name TEXT NOT NULL,
          profile_json TEXT NOT NULL, content_hash TEXT NOT NULL, retrieved_at TEXT NOT NULL,
          changed INTEGER NOT NULL, FOREIGN KEY(org_number) REFERENCES profiles(org_number)
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_org_time ON snapshots(org_number, retrieved_at);
        """)
        self.conn.commit()

    @staticmethod
    def _hash(profile: dict[str, Any]) -> str:
        import hashlib
        stable = {k: v for k, v in profile.items() if k != "retrieved_at"}
        stable["facts"] = [{k: v for k, v in f.items() if k != "retrieved_at"} for f in stable.get("facts", [])]
        return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def upsert(self, profile: CompanyProfile) -> dict[str, Any]:
        data = profile.to_dict()
        digest = self._hash(data)
        prior = self.conn.execute("SELECT content_hash FROM profiles WHERE org_number=?", (profile.org_number,)).fetchone()
        changed = prior is None or prior["content_hash"] != digest
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
        self.conn.execute("""INSERT INTO profiles(org_number,name,profile_json,content_hash,retrieved_at,source_updated_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(org_number) DO UPDATE SET name=excluded.name, profile_json=excluded.profile_json,
          content_hash=excluded.content_hash, retrieved_at=excluded.retrieved_at, source_updated_at=excluded.source_updated_at""",
          (profile.org_number, profile.name, encoded, digest, profile.retrieved_at, profile.source_updated_at))
        # Store a snapshot on first ingestion or when facts change; avoid noisy duplicate history.
        if changed:
            self.conn.execute("INSERT INTO snapshots(org_number,name,profile_json,content_hash,retrieved_at,changed) VALUES(?,?,?,?,?,?)",
                              (profile.org_number, profile.name, encoded, digest, profile.retrieved_at, 1 if prior else 0))
        self.conn.commit()
        return {"org_number": profile.org_number, "name": profile.name, "changed": changed, "is_new": prior is None}

    def get(self, org_number: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT profile_json FROM profiles WHERE org_number=?", (org_number,)).fetchone()
        return json.loads(row["profile_json"]) if row else None

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0])

    def history(self, org_number: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT retrieved_at, changed, profile_json FROM snapshots WHERE org_number=? ORDER BY id", (org_number,)).fetchall()
        return [{"retrieved_at": r["retrieved_at"], "changed": bool(r["changed"]), "profile": json.loads(r["profile_json"])} for r in rows]

    def all_profiles(self):
        for row in self.conn.execute("SELECT profile_json FROM profiles ORDER BY org_number"):
            yield json.loads(row["profile_json"])

    def close(self):
        self.conn.close()
