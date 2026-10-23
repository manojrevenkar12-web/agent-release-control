"""Trains what the platform needs from history: the understanding tiers (from labelled messages)
and the learned judge (from specialist-reviewed conversations of the production release)."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from arc.agent.nlu import NLU
from arc.agent.release import load as load_release
from arc.config import MODELS
from arc.evals.judges import LearnedJudge
from arc.runner import Env, simulate
from arc.sim import review
from arc.sim.history import labelled_messages
from arc.sim.world import load as load_world
from arc.sim.world import make_specs


def train(history_conversations: int = 6000, reviewed: int = 1500) -> dict[str, Any]:
    t0 = time.time()
    w = load_world()
    X, y = labelled_messages(w)
    nlu = NLU.fit(X, y)
    nlu.save()
    e = Env(w, nlu)
    hist = simulate(load_release("r1-prod"), make_specs(w, history_conversations, 11, day0=0, prefix="h"), e)
    sample = hist[:reviewed]
    labels = review.labels(sample, 3)
    plans = [str(w.systems.plan[o.account]) for o in sample]
    judge = LearnedJudge.fit(sample, plans, labels, {"release": "r1-prod", "conversations": reviewed})
    judge.save()
    # does the judge still work on conversations it was not trained on, and on a different release?
    validation = {}
    for rid, seed in (("r1-prod", 12), ("r2-personalised", 13)):
        outs = simulate(load_release(rid), make_specs(w, 800, seed, day0=30, prefix=f"jv{rid}"), e, seed)
        lab = review.labels(outs, seed)
        sc = judge.score(outs, [str(w.systems.plan[o.account]) for o in outs])
        validation[rid] = {
            m: {
                "auc": round(float(roc_auc_score(lab[m], getattr(sc, m))), 3),
                "judged_rate": round(float(np.mean(getattr(sc, m))), 4),
                "labelled_rate": round(float(lab[m].mean()), 4),
            }
            for m in ("resolved", "hallucinated")
        }
    card = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "nlu": {"labelled_messages": len(X), "tiers": nlu.trained_on},
        "judge": {
            "trained_on_release": "r1-prod",
            "reviewed_conversations": reviewed,
            "label_resolved_rate": round(float(labels.resolved.mean()), 4),
            "label_hallucinated_rate": round(float(labels.hallucinated.mean()), 4),
            "validation": validation,
        },
        "history_conversations": history_conversations,
        "seconds": round(time.time() - t0, 1),
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    (MODELS / "model_card.json").write_text(json.dumps(card, indent=2))

    return card
