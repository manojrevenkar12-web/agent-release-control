"""Prediction-powered inference: unbiased estimates from many judge scores plus a few human labels.

A judge scores every conversation (cheap, biased); people label a random sample (expensive,
unbiased). The estimate is the judges' mean corrected by the average judge error on the sample:

    theta = mean(f over all) + mean(y - f over the labelled sample)

with variance var(f)/N + var(y - f)/n. For a paired comparison of two releases on the same
conversations, the same is done on differences. (Angelopoulos et al., 2023.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class Estimate:
    est: float
    se: float

    def ci(self, alpha: float = 0.05) -> tuple[float, float]:
        z = stats.norm.ppf(1 - alpha / 2)
        return self.est - z * self.se, self.est + z * self.se


def naive(f: np.ndarray) -> Estimate:
    f = np.asarray(f, float)
    return Estimate(float(f.mean()), float(f.std(ddof=1) / np.sqrt(len(f))))


def mean(f_all: np.ndarray, f_lab: np.ndarray, y_lab: np.ndarray) -> Estimate:
    f_all, f_lab, y_lab = (np.asarray(x, float) for x in (f_all, f_lab, y_lab))
    rect = y_lab - f_lab
    return Estimate(float(f_all.mean() + rect.mean()), float(np.sqrt(f_all.var(ddof=1) / len(f_all) + rect.var(ddof=1) / len(rect))))


def paired_diff(fa: np.ndarray, fb: np.ndarray, lab: np.ndarray, ya: np.ndarray, yb: np.ndarray) -> Estimate:
    """Candidate (b) minus baseline (a) on the same conversations; `lab` indexes the labelled ones."""
    fa, fb, ya, yb = (np.asarray(x, float) for x in (fa, fb, ya, yb))
    d = fb - fa
    rect = (yb - fb[lab]) - (ya - fa[lab])
    return Estimate(float(d.mean() + rect.mean()), float(np.sqrt(d.var(ddof=1) / len(d) + rect.var(ddof=1) / max(len(rect), 2))))


def paired_diff_changed(fa: np.ndarray, fb: np.ndarray, changed: np.ndarray, lab: np.ndarray, ya: np.ndarray, yb: np.ndarray) -> Estimate:
    """Like `paired_diff`, when only some conversations went differently under the candidate.

    Where both releases produced the same conversation, the difference is zero for the judges and for
    any reviewer, so labels are spent only on conversations that changed (`changed`: their indices;
    `lab`: the labelled ones among them). The estimate is the changed share times the PPI estimate
    on the changed conversations, which is far tighter when a release changes few conversations.
    """
    fa, fb, ya, yb = (np.asarray(x, float) for x in (fa, fb, ya, yb))
    n, k = len(fa), len(changed)
    if k == 0:
        return Estimate(0.0, 0.0)
    share = k / n
    d = fb - fa  # zero wherever the conversation did not change
    rect = (yb - fb[lab]) - (ya - fa[lab])
    # sampling of conversations (which ones changed, and by how much) plus the judges' error on the
    # changed ones, measured on the labelled sample (reviewer disagreement included)
    var_r = rect.var(ddof=1) / len(rect) if len(rect) > 1 else 0.0
    return Estimate(
        float(d.mean() + share * rect.mean()) if len(rect) else float(d.mean()), float(np.sqrt(d.var(ddof=1) / n + share**2 * var_r))
    )


def paired_naive(fa: np.ndarray, fb: np.ndarray) -> Estimate:
    d = np.asarray(fb, float) - np.asarray(fa, float)
    return Estimate(float(d.mean()), float(d.std(ddof=1) / np.sqrt(len(d))))
