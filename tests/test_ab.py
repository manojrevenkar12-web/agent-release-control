import numpy as np
import pandas as pd

from arc.experiment import ab


def test_power_analysis_matches_the_textbook_formula():
    # two-sided alpha 5%, power 80%, p = 0.5, mde 0.05: about 1,570 per arm
    assert 1560 <= ab.per_arm_n(0.5, 0.05, 0.05, 0.8) <= 1580
    p = ab.plan(0.68, 1500, 0.5, {"primary": "resolved_obs", "mde": 0.02, "alpha": 0.01, "power": 0.8})
    assert p.days % 7 == 0 and p.per_arm > 10000


def test_assignment_is_deterministic_and_has_the_right_share():
    acc = np.arange(50000)
    a, b = ab.assign(acc, 1, 0.3), ab.assign(acc, 1, 0.3)
    assert (a == b).all() and abs(a.mean() - 0.3) < 0.01
    assert (ab.assign(acc, 2, 0.3) != a).any()


def _clustered(rng, n_acc, effect, arm):
    rows = []
    for acc in range(n_acc):
        base = rng.uniform(0.3, 0.9)  # accounts differ a lot
        for _ in range(int(rng.integers(1, 8))):
            rows.append({"arm": arm, "account": f"{arm}{acc}", "y": float(rng.random() < min(base + effect, 1))})
    return rows


def test_delta_method_is_wider_than_a_naive_interval_when_accounts_cluster():
    rng = np.random.default_rng(3)
    df = pd.DataFrame(_clustered(rng, 1500, 0.0, "control") + _clustered(rng, 1500, 0.0, "treatment"))
    e = ab.ratio_by_account(df, "y")
    g = df.groupby("arm").y
    naive_se = np.sqrt((g.var() / g.count()).sum())
    assert (e.hi - e.lo) / 3.92 > naive_se * 1.1


def test_aa_false_positive_rate_is_about_alpha():
    rng = np.random.default_rng(4)
    fp = 0
    for _ in range(200):
        df = pd.DataFrame(_clustered(rng, 300, 0.0, "control") + _clustered(rng, 300, 0.0, "treatment"))
        fp += ab.ratio_by_account(df, "y").p < 0.05
    assert fp / 200 < 0.09
