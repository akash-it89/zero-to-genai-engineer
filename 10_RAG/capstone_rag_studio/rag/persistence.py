"""SQLite persistence: strategy_variants, access_policies, audit_log (Req 2, 11.13, 23.3, 23.5).

CRUD for named strategy variants (name conflicts rejected, deleting one retains the
rest), Access_Policy read/update, an append-only audit log, and conversation/message
storage for conversational chat. Filesystem storage holds uploaded document bytes
alongside the database. Every operation wraps a disk/permission/corruption failure in
a descriptive :class:`PersistenceError` rather than letting a raw driver exception
escape (Req 23.5).

Only imports :mod:`rag.interfaces` (module isolation, Req 12.6) — the audit-log
``append`` method is duck-typed to accept anything with ``request_id``,
``acting_principal``, ``authorized_doc_ids``, ``denied_doc_ids`` attributes (matching
``rag.governance.AuditEntry`` structurally) so this module never imports governance.
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3

from rag.interfaces import AccessPolicy


class PersistenceError(Exception):
    """A descriptive wrapper around disk/permission/corruption failures (Req 23.5)."""

    def __init__(self, operation: str, message: str):
        self.operation = operation
        super().__init__(f"Persistence operation '{operation}' failed: {message}")


class DuplicateVariantNameError(Exception):
    """Raised when saving a variant whose name already exists; the store is left
    unchanged (Req 2.3, P23)."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"A strategy variant named '{name}' already exists.")


class VariantNotFoundError(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"No strategy variant named '{name}' exists.")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_variants (
    name TEXT PRIMARY KEY,
    config_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS access_policies (
    doc_id TEXT PRIMARY KEY,
    access_level TEXT NOT NULL,
    owner TEXT NOT NULL,
    acl_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    acting_principal TEXT NOT NULL,
    authorized_doc_ids_json TEXT NOT NULL,
    denied_doc_ids_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    variant_name TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    trace_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id
    ON conversation_messages (conversation_id, id);
"""


class SqlitePersistence:
    """The SQLite-backed store for variants, access policies, and the audit log (Req 11.1)."""

    def __init__(self, db_path: str = "./rag_studio.sqlite", upload_dir: str = "./uploads"):
        self.db_path = db_path
        self.upload_dir = upload_dir
        try:
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            os.makedirs(upload_dir, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        except (OSError, sqlite3.Error) as exc:
            raise PersistenceError("open", str(exc)) from exc

    # --- strategy_variants (Req 2.1-2.4) ---

    def save_variant(self, name: str, config_dict: dict) -> None:
        try:
            existing = self._conn.execute(
                "SELECT 1 FROM strategy_variants WHERE name = ?", (name,)
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError("save_variant", str(exc)) from exc
        if existing:
            raise DuplicateVariantNameError(name)
        try:
            self._conn.execute(
                "INSERT INTO strategy_variants (name, config_json) VALUES (?, ?)",
                (name, json.dumps(config_dict, sort_keys=True)),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError("save_variant", str(exc)) from exc

    def list_variants(self) -> dict[str, dict]:
        try:
            rows = self._conn.execute("SELECT name, config_json FROM strategy_variants").fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("list_variants", str(exc)) from exc
        return {name: json.loads(cfg) for name, cfg in rows}

    def get_variant(self, name: str) -> dict:
        variants = self.list_variants()
        if name not in variants:
            raise VariantNotFoundError(name)
        return variants[name]

    def delete_variant(self, name: str) -> None:
        try:
            cur = self._conn.execute("DELETE FROM strategy_variants WHERE name = ?", (name,))
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError("delete_variant", str(exc)) from exc
        if cur.rowcount == 0:
            raise VariantNotFoundError(name)

    # --- access_policies (Req 11.16) ---

    def get_access_policy(self, doc_id: str) -> AccessPolicy:
        try:
            row = self._conn.execute(
                "SELECT access_level, owner, acl_json FROM access_policies WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError("get_access_policy", str(exc)) from exc
        if row is None:
            return AccessPolicy(access_level="PRIVATE", owner="\x00unknown", acl=[])
        level, owner, acl_json = row
        return AccessPolicy(access_level=level, owner=owner, acl=json.loads(acl_json))

    def set_access_policy(self, doc_id: str, policy: AccessPolicy) -> None:
        try:
            self._conn.execute(
                "INSERT INTO access_policies (doc_id, access_level, owner, acl_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(doc_id) DO UPDATE SET access_level=excluded.access_level, "
                "owner=excluded.owner, acl_json=excluded.acl_json",
                (doc_id, policy.access_level, policy.owner, json.dumps(policy.acl)),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError("set_access_policy", str(exc)) from exc

    # --- audit_log (Req 11.13) — append-only ---

    def append(self, entry) -> None:
        """Duck-typed AuditSink.append: accepts anything with the four AuditEntry fields."""
        try:
            self._conn.execute(
                "INSERT INTO audit_log (request_id, acting_principal, authorized_doc_ids_json, denied_doc_ids_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    entry.request_id,
                    entry.acting_principal,
                    json.dumps(entry.authorized_doc_ids),
                    json.dumps(entry.denied_doc_ids),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError("append_audit", str(exc)) from exc

    def list_audit_entries(self) -> list[dict]:
        try:
            rows = self._conn.execute(
                "SELECT request_id, acting_principal, authorized_doc_ids_json, denied_doc_ids_json "
                "FROM audit_log ORDER BY id"
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("list_audit_entries", str(exc)) from exc
        return [
            {
                "request_id": r,
                "acting_principal": p,
                "authorized_doc_ids": json.loads(a),
                "denied_doc_ids": json.loads(d),
            }
            for r, p, a, d in rows
        ]

    # --- conversations + messages (conversational chat memory) ---

    def create_conversation(self, conversation_id: str, variant_name: str, principal_id: str) -> None:
        try:
            self._conn.execute(
                "INSERT INTO conversations (id, variant_name, principal_id, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, variant_name, principal_id, datetime.datetime.utcnow().isoformat()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError("create_conversation", str(exc)) from exc

    def append_conversation_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        trace_id: str | None = None,
    ) -> None:
        try:
            self._conn.execute(
                "INSERT INTO conversation_messages "
                "(conversation_id, role, content, citations_json, trace_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(citations or []),
                    trace_id,
                    datetime.datetime.utcnow().isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError("append_conversation_message", str(exc)) from exc

    def list_conversation_messages(self, conversation_id: str) -> list[dict]:
        try:
            rows = self._conn.execute(
                "SELECT role, content, citations_json, trace_id, created_at FROM conversation_messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("list_conversation_messages", str(exc)) from exc
        return [
            {"role": role, "content": content, "citations": json.loads(citations_json), "trace_id": trace_id, "created_at": created_at}
            for role, content, citations_json, trace_id, created_at in rows
        ]

    def list_conversations(self, principal_id: str) -> list[dict]:
        try:
            rows = self._conn.execute(
                "SELECT id, variant_name, created_at FROM conversations WHERE principal_id = ? ORDER BY created_at DESC",
                (principal_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("list_conversations", str(exc)) from exc
        return [{"id": cid, "variant_name": variant_name, "created_at": created_at} for cid, variant_name, created_at in rows]

    def get_conversation(self, conversation_id: str) -> dict | None:
        try:
            row = self._conn.execute(
                "SELECT id, variant_name, principal_id, created_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError("get_conversation", str(exc)) from exc
        if row is None:
            return None
        cid, variant_name, principal_id, created_at = row
        return {"id": cid, "variant_name": variant_name, "principal_id": principal_id, "created_at": created_at}

    # --- filesystem uploads (Req 2.1) ---

    def save_upload(self, filename: str, content: bytes) -> str:
        path = os.path.join(self.upload_dir, filename)
        try:
            with open(path, "wb") as fh:
                fh.write(content)
        except OSError as exc:
            raise PersistenceError("save_upload", str(exc)) from exc
        return path

    def close(self) -> None:
        self._conn.close()
