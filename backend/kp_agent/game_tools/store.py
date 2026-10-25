"""Checksummed, atomic JSON saves. Never silently restore a backup."""
import json
import os
import re
import threading
import uuid
from pathlib import Path
from .content import GameError, digest

class JsonStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.mutex = threading.RLock()
        self.process_file = (self.root / '.web-runtime.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.process_file.write(b'0'); self.process_file.flush(); self.process_file.seek(0)
                msvcrt.locking(self.process_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.process_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.process_file.close()
            raise GameError('worker_conflict', '网页 JSON 游戏只支持一个进程/worker。', 503) from None

    def close(self):
        self.process_file.close()

    def path(self, game_id):
        if not re.fullmatch(r'[0-9a-f]{32}', game_id):
            raise GameError('game_not_found', '找不到这场调查。', 404)
        path = self.root / game_id / 'game.json'
        if path.parent.is_symlink() or path.is_symlink():
            raise GameError('save_invalid', '游戏文件路径无效。', 503)
        return path

    def load(self, game_id):
        path = self.path(game_id)
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            checksum = value.pop('_checksum')
            if digest(value) != checksum or value['gameId'] != game_id:
                raise ValueError()
            return value
        except FileNotFoundError:
            raise GameError('game_not_found', '找不到这场调查。', 404) from None
        except (ValueError, KeyError, TypeError, OSError):
            raise GameError('save_invalid', '游戏文件损坏或无法读取；原文件和备份已保留。', 503) from None

    def _replace(self, path, data):
        temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
        try:
            with temp.open('xb') as file:
                file.write(data); file.flush(); os.fsync(file.fileno())
            os.replace(temp, path)
            if os.name != 'nt':
                fd = os.open(path.parent, os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
        finally:
            temp.unlink(missing_ok=True)

    def save(self, game):
        with self.mutex:
            path = self.path(game['gameId'])
            path.parent.mkdir(exist_ok=True)
            if path.exists():
                self.load(game['gameId'])  # A damaged original must never be overwritten.
                self._replace(path.with_suffix('.json.bak'), path.read_bytes())
            value = {**game, '_checksum': digest(game)}
            self._replace(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
