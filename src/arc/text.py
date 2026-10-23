"""Text utilities: tokenising and BM25 retrieval over the help centre."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("a an the to of and or in on for with my me i we our you your is are be can do does how what when where why it this that there at from by as please pls hi hello hey thanks thank".split())


def tokens(text: str) -> list[str]:
    out = []
    for t in TOKEN.findall(text.lower()):
        if t in STOP:
            continue
        # light stemming
        for suf in ("ing", "ed", "es", "s"):
            if len(t) > 4 and t.endswith(suf):
                t = t[: -len(suf)]
                break
        out.append(t)
    return out


@dataclass
class Hit:
    doc: str
    score: float


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.4, b: float = 0.75):
        self.ids = list(docs)
        self.tf = [Counter(tokens(docs[i])) for i in self.ids]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        df: Counter[str] = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(self.ids)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self.k1, self.b = k1, b
        self._cache: dict[str, list[Hit]] = {}

    def search(self, query: str, k: int = 5) -> list[Hit]:
        key = f"{k}|{query}"
        if key in self._cache:
            return self._cache[key]
        q = set(tokens(query))
        scores = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for t in q:
                f = c.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores.append(s)
        order = sorted(range(len(scores)), key=lambda j: -scores[j])[:k]
        out = [Hit(self.ids[j], scores[j]) for j in order]
        if len(self._cache) < 200_000:
            self._cache[key] = out
        return out
