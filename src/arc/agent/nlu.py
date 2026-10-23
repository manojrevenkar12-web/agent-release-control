"""Understanding a customer message: which request it is, and how sure we are.

Two tiers stand in for a small and a large model: the small one is cheap and fast and learned from
a few thousand labelled messages; the large one sees word pairs and character patterns and learned
from all of them. The release decides when the large one is asked (router). Both are trained on
messages from past conversations that support specialists labelled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer

from arc.config import CONFIG, MODELS

_LEXICON = [(re.compile(k, re.I), v) for k, v in yaml.safe_load((CONFIG / "lexicon.yaml").read_text()).items()]


def expand(texts: list[str]) -> list[str]:
    """The large tier's wider vocabulary (config/lexicon.yaml)."""
    out = []
    for t in texts:
        extra = [v for rx, v in _LEXICON if rx.search(t)]
        out.append(t + (" " + " ".join(extra) if extra else ""))
    return out


def small_pipeline() -> Pipeline:
    return Pipeline([("tf", TfidfVectorizer(sublinear_tf=True, min_df=2)), ("lr", LogisticRegression(C=4.0, max_iter=2000))])


def large_pipeline() -> Pipeline:
    feats = FeatureUnion(
        [
            ("w", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2)),
        ]
    )
    return Pipeline([("x", FunctionTransformer(expand)), ("f", feats), ("lr", LogisticRegression(C=8.0, max_iter=3000))])


@dataclass
class NLU:
    small: Pipeline
    large: Pipeline
    trained_on: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._cache: dict[tuple[str, str], tuple[str, float]] = {}

    def predict(self, text: str, tier: str) -> tuple[str, float]:
        key = (tier, text)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        m = self.small if tier == "small" else self.large
        p = m.predict_proba([text])[0]
        j = int(np.argmax(p))
        out = (str(m.classes_[j]), float(p[j]))
        if len(self._cache) < 500_000:
            self._cache[key] = out
        return out

    def predict_many(self, texts: list[str], tier: str) -> list[tuple[str, float]]:
        m = self.small if tier == "small" else self.large
        P = m.predict_proba(texts)
        j = P.argmax(axis=1)
        out = [(str(m.classes_[k]), float(P[i, k])) for i, k in enumerate(j)]
        for t, o in zip(texts, out, strict=True):
            self._cache[(tier, t)] = o
        return out

    @classmethod
    def fit(cls, texts: list[str], labels: list[str], small_rows: int = 2000) -> NLU:
        small = small_pipeline().fit(texts[:small_rows], labels[:small_rows])
        large = large_pipeline().fit(texts, labels)
        return cls(small, large, {"small": min(small_rows, len(texts)), "large": len(texts)})

    def save(self, path: Path = MODELS / "nlu.joblib") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump((self.small, self.large, self.trained_on), path, compress=3)

    @classmethod
    def load(cls, path: Path = MODELS / "nlu.joblib") -> NLU:
        s, lg, t = joblib.load(path)
        return cls(s, lg, t)
