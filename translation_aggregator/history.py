from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import json
import time

from .config import config


@dataclass
class HistoryEntry:
    ts: float
    src_lang: str
    dst_lang: str
    original: str
    results: List[dict]  # [{"translator": , "text": , "error": }]


class HistoryStore:
    def __init__(self, max_entries: int = 200):
        self.max = max_entries
        self.entries: List[HistoryEntry] = []
        self.path = Path("history.json")
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.entries = [
                    HistoryEntry(
                        ts=e.get("ts", time.time()),
                        src_lang=e.get("src", "ja"),
                        dst_lang=e.get("dst", "en"),
                        original=e.get("orig", ""),
                        results=e.get("results", []),
                    )
                    for e in data
                ]
            except Exception:
                self.entries = []

    def save(self):
        try:
            data = [
                {
                    "ts": e.ts,
                    "src": e.src_lang,
                    "dst": e.dst_lang,
                    "orig": e.original,
                    "results": e.results,
                }
                for e in self.entries[-self.max :]
            ]
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add(self, src: str, dst: str, original: str, results: List[dict]):
        self.entries.append(
            HistoryEntry(
                ts=time.time(),
                src_lang=src,
                dst_lang=dst,
                original=original,
                results=results,
            )
        )
        if len(self.entries) > self.max:
            self.entries = self.entries[-self.max :]
        self.save()

    def recent(self, n: int = 50) -> List[HistoryEntry]:
        return list(reversed(self.entries[-n:]))
