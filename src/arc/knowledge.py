"""The help centre: articles with optional plan-specific sections. The agent answers only from these."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from arc.config import KNOWLEDGE
from arc.text import BM25

PLANS = ("free", "pro", "business")


@dataclass
class Article:
    id: str
    title: str
    body: str
    sections: dict[str, str] = field(default_factory=dict)  # plan -> text
    keywords: str = ""

    @property
    def plan_specific(self) -> bool:
        return bool(self.sections)

    def text_for(self, plan: str | None) -> str:
        """The answer text: the body plus the section for `plan`; without a plan, the Pro section
        (what a non-personalised answer says)."""
        if not self.sections:
            return self.body
        sec = self.sections.get(plan or "pro", self.sections["pro"])
        return f"{sec} {self.body}".strip()

    def search_text(self) -> str:
        return " ".join([self.title, self.title, self.keywords, self.body, *self.sections.values()])


def parse(path: Path) -> Article:
    raw = path.read_text()
    _, fm, rest = raw.split("---", 2)
    meta = yaml.safe_load(fm)
    body, sections, cur = [], {}, None
    for line in rest.strip().splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            cur = line[3:].strip().lower()
            sections[cur] = ""
            continue
        if line.strip():
            if cur:
                sections[cur] = (sections[cur] + " " + line.strip()).strip()
            else:
                body.append(line.strip())
    return Article(meta["id"], meta["title"], " ".join(body), sections, str(meta.get("keywords", "")))


@lru_cache
def load(directory: Path = KNOWLEDGE) -> dict[str, Article]:
    return {a.id: a for a in (parse(p) for p in sorted(directory.glob("*.md")))}


@lru_cache
def index(directory: Path = KNOWLEDGE) -> BM25:
    return BM25({a.id: a.search_text() for a in load(directory).values()})
