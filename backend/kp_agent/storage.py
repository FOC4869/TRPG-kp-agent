"""SQLite snapshots and an append-only audit trail for one active game.

Random results are written before narration. Action commits atomically update
character + scene + event; request and action identifiers make retries safe.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator
from uuid import uuid4


class StorageError(RuntimeError):
    pass


class VersionConflict(StorageError):
    pass


class StaleGameError(StorageError):
    pass


class MessageConflict(StorageError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=15)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=15000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                character TEXT NOT NULL,
                initial_character TEXT NOT NULL,
                scene_state TEXT NOT NULL,
                initial_scene_state TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                game_id TEXT NOT NULL REFERENCES games(game_id),
                message_id TEXT NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL,
                draft TEXT,
                reply TEXT,
                error TEXT,
                action_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(game_id,message_id)
            );
            CREATE TABLE IF NOT EXISTS rolls (
                game_id TEXT NOT NULL REFERENCES games(game_id),
                request_id TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(game_id,request_id)
            );
            CREATE TABLE IF NOT EXISTS actions (
                game_id TEXT NOT NULL REFERENCES games(game_id),
                action_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                event TEXT NOT NULL,
                roll_ids TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(game_id,action_id),
                UNIQUE(game_id,message_id),
                FOREIGN KEY(game_id,message_id) REFERENCES messages(game_id,message_id)
            );
        """)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def _active_id(self, conn: sqlite3.Connection) -> str | None:
        row = conn.execute("SELECT value FROM settings WHERE key='active_game'").fetchone()
        return row["value"] if row else None

    def _require_active(self, conn: sqlite3.Connection, game_id: str) -> None:
        if game_id != self._active_id(conn):
            raise StaleGameError("游戏已重新开始，旧请求不能修改新游戏。")

    @staticmethod
    def _game(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "game_id": row["game_id"], "version": row["version"],
            "character": json.loads(row["character"]),
            "scene_state": json.loads(row["scene_state"]), "status": row["status"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    @staticmethod
    def _message(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for field in ("draft", "reply"):
            result[field] = json.loads(row[field]) if row[field] else None
        return result

    def get_game(self, game_id: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            game_id = game_id or self._active_id(self._conn)
            row = self._conn.execute("SELECT * FROM games WHERE game_id=?", (game_id,)).fetchone()
            return self._game(row)

    def start_game(
        self, character: dict[str, Any], scene_state: dict[str, Any], force: bool = False
    ) -> dict[str, Any]:
        with self._transaction() as conn:
            active_id = self._active_id(conn)
            if active_id and not force:
                return self._game(conn.execute("SELECT * FROM games WHERE game_id=?", (active_id,)).fetchone())  # type: ignore[return-value]
            game_id, timestamp = uuid4().hex, _now()
            conn.execute(
                "INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?)",
                (game_id, 0, _json(character), _json(character), _json(scene_state),
                 _json(scene_state), scene_state.get("status", "playing"), timestamp, timestamp),
            )
            conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('active_game',?)", (game_id,))
            return self._game(conn.execute("SELECT * FROM games WHERE game_id=?", (game_id,)).fetchone())  # type: ignore[return-value]

    def restart_game(
        self, character: dict[str, Any] | None = None, scene_state: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Holding the lock through start prevents an in-process restart race.
        with self._lock:
            if character is None or scene_state is None:
                active = self._active_id(self._conn)
                row = self._conn.execute("SELECT * FROM games WHERE game_id=?", (active,)).fetchone()
                if row is None:
                    raise StorageError("尚未开始游戏。")
                if character is None:
                    character = json.loads(row["initial_character"])
                if scene_state is None:
                    scene_state = json.loads(row["initial_scene_state"])
            return self.start_game(character, scene_state, force=True)

    def load_character(self, game_id: str | None = None) -> dict[str, Any]:
        game = self.get_game(game_id)
        if game is None:
            raise StorageError("尚未开始游戏。")
        return game["character"]

    def begin_message(self, game_id: str, message_id: str, text: str) -> dict[str, Any]:
        if not message_id or not text.strip():
            raise MessageConflict("消息编号和内容不能为空。")
        with self._transaction() as conn:
            self._require_active(conn, game_id)
            row = conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone()
            if row:
                if row["text"] != text:
                    raise MessageConflict("同一消息编号不能对应不同内容。")
                if row["status"] == "failed":
                    busy = conn.execute("SELECT message_id FROM messages WHERE game_id=? AND status IN ('processing','failed') AND message_id<>?", (game_id, message_id)).fetchone()
                    if busy:
                        raise MessageConflict(f"请先恢复尚未完成的消息：{busy['message_id']}。")
                    conn.execute("UPDATE messages SET status='processing',error=NULL,updated_at=? WHERE game_id=? AND message_id=?", (_now(), game_id, message_id))
                    row = conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone()
                return self._message(row)  # type: ignore[return-value]
            busy = conn.execute("SELECT message_id FROM messages WHERE game_id=? AND status IN ('processing','failed')", (game_id,)).fetchone()
            if busy:
                raise MessageConflict(f"上一条消息尚未完成，请等待或恢复原消息：{busy['message_id']}。")
            timestamp = _now()
            conn.execute(
                "INSERT INTO messages(game_id,message_id,text,status,created_at,updated_at) VALUES(?,?,?,'processing',?,?)",
                (game_id, message_id, text, timestamp, timestamp),
            )
            return self._message(conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone())  # type: ignore[return-value]

    def get_message(self, game_id: str, message_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._message(self._conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone())

    def save_message_draft(self, game_id: str, message_id: str, draft: dict[str, Any]) -> dict[str, Any]:
        with self._transaction() as conn:
            self._require_active(conn, game_id)
            row = conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone()
            if row is None:
                raise MessageConflict("请先登记消息。")
            # The first persisted plan is immutable, so retries cannot choose a new action.
            if row["draft"] is None:
                conn.execute("UPDATE messages SET draft=?,updated_at=? WHERE game_id=? AND message_id=?", (_json(draft), _now(), game_id, message_id))
            return self._message(conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone())  # type: ignore[return-value]

    def get_roll(self, game_id: str, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT result FROM rolls WHERE game_id=? AND request_id=?", (game_id, request_id)).fetchone()
            return json.loads(row["result"]) if row else None

    def record_roll(self, game_id: str, request_id: str, roll: dict[str, Any]) -> dict[str, Any]:
        with self._transaction() as conn:
            self._require_active(conn, game_id)
            row = conn.execute("SELECT result FROM rolls WHERE game_id=? AND request_id=?", (game_id, request_id)).fetchone()
            if row:
                return json.loads(row["result"])
            conn.execute("INSERT INTO rolls VALUES(?,?,?,?)", (game_id, request_id, _json(roll), _now()))
            return json.loads(_json(roll))

    def get_action(self, game_id: str, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM actions WHERE game_id=? AND action_id=?", (game_id, action_id)).fetchone()
            if row is None:
                return None
            return {
                "game_id": game_id, "action_id": action_id, "message_id": row["message_id"],
                "event": json.loads(row["event"]), "roll_ids": json.loads(row["roll_ids"]),
                "game": json.loads(row["result"]), "created_at": row["created_at"],
            }

    def commit_action(
        self, game_id: str, message_id: str, action_id: str, expected_version: int,
        character: dict[str, Any], scene_state: dict[str, Any], event: dict[str, Any],
        roll_ids: tuple[str, ...] | list[str] = (),
    ) -> dict[str, Any]:
        with self._transaction() as conn:
            self._require_active(conn, game_id)
            prior = conn.execute("SELECT * FROM actions WHERE game_id=? AND action_id=?", (game_id, action_id)).fetchone()
            if prior:
                if prior["message_id"] != message_id:
                    raise MessageConflict("行动编号已被另一条消息使用。")
                return json.loads(prior["result"])
            message = conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone()
            if message is None or message["status"] == "completed":
                raise MessageConflict("消息不存在或已经完成。")
            if message["action_id"]:
                raise MessageConflict("此消息已提交其他行动，不能重复修改状态。")
            current = conn.execute("SELECT * FROM games WHERE game_id=?", (game_id,)).fetchone()
            if current["version"] != expected_version:
                raise VersionConflict("游戏状态已经变化，请重新读取；未提交任何变化。")
            for request_id in roll_ids:
                if not conn.execute("SELECT 1 FROM rolls WHERE game_id=? AND request_id=?", (game_id, request_id)).fetchone():
                    raise StorageError(f"骰子结果尚未保存：{request_id}")
            timestamp = _now()
            conn.execute(
                "UPDATE games SET version=version+1,character=?,scene_state=?,status=?,updated_at=? WHERE game_id=?",
                (_json(character), _json(scene_state), scene_state.get("status", "playing"), timestamp, game_id),
            )
            result = self._game(conn.execute("SELECT * FROM games WHERE game_id=?", (game_id,)).fetchone())
            conn.execute("INSERT INTO actions VALUES(?,?,?,?,?,?,?)", (game_id, action_id, message_id, _json(event), _json(list(roll_ids)), _json(result), timestamp))
            conn.execute("UPDATE messages SET action_id=?,updated_at=? WHERE game_id=? AND message_id=?", (action_id, timestamp, game_id, message_id))
            return result  # type: ignore[return-value]

    def save_reply(self, game_id: str, message_id: str, reply: dict[str, Any]) -> dict[str, Any]:
        with self._transaction() as conn:
            self._require_active(conn, game_id)
            row = conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone()
            if row is None:
                raise MessageConflict("请先登记消息。")
            if row["status"] != "completed":
                conn.execute("UPDATE messages SET status='completed',reply=?,error=NULL,updated_at=? WHERE game_id=? AND message_id=?", (_json(reply), _now(), game_id, message_id))
            return self._message(conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone())  # type: ignore[return-value]

    def fail_message(self, game_id: str, message_id: str, error: str) -> dict[str, Any]:
        with self._transaction() as conn:
            self._require_active(conn, game_id)
            row = conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone()
            if row is None:
                raise MessageConflict("消息不存在。")
            if row["status"] != "completed":
                conn.execute("UPDATE messages SET status='failed',error=?,updated_at=? WHERE game_id=? AND message_id=?", (error, _now(), game_id, message_id))
            return self._message(conn.execute("SELECT * FROM messages WHERE game_id=? AND message_id=?", (game_id, message_id)).fetchone())  # type: ignore[return-value]

    def list_messages(self, game_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            game_id = game_id or self._active_id(self._conn)
            rows = self._conn.execute("SELECT * FROM messages WHERE game_id=? ORDER BY created_at,rowid", (game_id,)).fetchall()
            return [self._message(row) for row in rows]  # type: ignore[misc]

    def list_events(self, game_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            game_id = game_id or self._active_id(self._conn)
            rows = self._conn.execute("SELECT action_id,event,created_at FROM actions WHERE game_id=? ORDER BY created_at,rowid", (game_id,)).fetchall()
            return [{"action_id": row["action_id"], "event": json.loads(row["event"]), "created_at": row["created_at"]} for row in rows]

    def get_recent_events(self, game_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        return self.list_events(game_id)[-max(0, limit):] if limit > 0 else []
