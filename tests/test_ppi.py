import numpy as np

from arc.evals import ppi


def test_ppi_removes_judge_bias_and_covers_the_truth():
    rng = np.random.default_rng(0)
    covered_ppi, covered_naive = 0, 0
    for _ in range(200):
        y = (rng.random(4000) < 0.6).astype(float)
        f = np.clip(y * 0.7 + 0.1 + rng.normal(0, 0.1, y.size), 0, 1)  # a judge that under-scores
        lab = rng.choice(y.size, 150, replace=False)
        e = ppi.mean(f, f[lab], y[lab])
        lo, hi = e.ci()
        covered_ppi += lo <= y.mean() <= hi
        lo, hi = ppi.naive(f).ci()
        covered_naive += lo <= y.mean() <= hi
    assert covered_ppi / 200 > 0.9
    assert covered_naive / 200 < 0.1


def test_paired_difference_recovers_a_change_the_judge_understates():
    rng = np.random.default_rng(1)
    n = 3000
    ya = (rng.random(n) < 0.6).astype(float)
    yb = np.maximum(ya, (rng.random(n) < 0.12).astype(float))  # b resolves ~5pp more
    noise = rng.normal(0, 0.1, (2, n))
    fa, fb = 0.2 + 0.5 * ya + noise[0], 0.2 + 0.5 * yb + noise[1]  # judge sees half of every change
    lab = rng.choice(n, 400, replace=False)
    e = ppi.paired_diff(fa, fb, lab, ya[lab], yb[lab])
    lo, hi = e.ci()
    true = yb.mean() - ya.mean()
    assert lo <= true <= hi
    assert abs(ppi.paired_naive(fa, fb).est - true / 2) < 0.01


def test_labelling_only_changed_conversations_is_unbiased_and_much_tighter():
    rng = np.random.default_rng(2)
    n, cover_changed, widths = 1000, 0, ([], [])
    for _ in range(200):
        ya = (rng.random(n) < 0.7).astype(float)
        changed = np.flatnonzero(rng.random(n) < 0.05)  # the candidate changes 5% of conversations
        yb = ya.copy()
        yb[changed] = (rng.random(len(changed)) < 0.9).astype(float)  # ... and resolves more of them
        fa = np.clip(0.2 + 0.5 * ya + rng.normal(0, 0.1, n), 0, 1)
        fb = fa.copy()
        fb[changed] = np.clip(0.2 + 0.5 * yb[changed] + rng.normal(0, 0.1, len(changed)), 0, 1)
        true = yb.mean() - ya.mean()
        lab = rng.choice(changed, min(150, len(changed)), replace=False)
        e = ppi.paired_diff_changed(fa, fb, changed, lab, ya[lab], yb[lab])
        lo, hi = e.ci()
        cover_changed += lo <= true <= hi
        lab_any = rng.choice(n, 150, replace=False)
        lo2, hi2 = ppi.paired_diff(fa, fb, lab_any, ya[lab_any], yb[lab_any]).ci()
        widths[0].append(hi - lo)
        widths[1].append(hi2 - lo2)
    assert cover_changed / 200 > 0.9
    assert np.mean(widths[0]) < 0.6 * np.mean(widths[1])  # without reviewer noise; with it, far tighter
