import numpy as np
import pandas as pd

from arc.ops import monitor


def _traffic(days=3, per_min=1.0, seed=0, err=0.0, err_window=None, slow_window=None, res=0.66, res_window=None, res_drop=0.0):
    rng = np.random.default_rng(seed)
    n = int(days * 1440 * per_min)
    t = np.sort(rng.integers(0, days * 1440, n))
    in_w = lambda w: (t >= w[0]) & (t < w[1]) if w else np.zeros(n, bool)  # noqa: E731
    e = rng.random(n) < np.where(in_w(err_window), 0.3, err)
    lat = rng.lognormal(1.0, 0.35, n) * np.where(in_w(slow_window), 3.0, 1.0)
    r = rng.random(n) < np.where(in_w(res_window), res - res_drop, res)
    return pd.DataFrame({"day": t // 1440, "minute": t % 1440, "error_conv": e, "latency_max_s": lat, "resolved_obs": r, "cost_eur": 0.004})


BASE = monitor.Baseline(0.66, 0.004)


def test_clean_traffic_raises_no_alert():
    assert monitor.alerts(_traffic(seed=1), BASE, 0, 3 * 1440 - 1) == []


def test_error_burst_pages_on_availability():
    al = monitor.alerts(_traffic(err_window=(2000, 2060)), BASE, 0, 3 * 1440 - 1)
    first = al[0]
    assert first.name == "availability burn rate" and first.severity == "page" and 2000 <= first.t <= 2060


def test_latency_spike_pages_on_latency():
    al = monitor.alerts(_traffic(slow_window=(1000, 1180)), BASE, 0, 3 * 1440 - 1)
    assert any(a.name == "latency burn rate" and 1000 <= a.t <= 1180 for a in al)


def test_resolution_drop_is_caught_by_cusum():
    al = monitor.alerts(_traffic(res_window=(1500, 1800), res_drop=0.3), BASE, 0, 3 * 1440 - 1)
    assert any(a.name == "resolution drop" and 1500 <= a.t <= 1800 for a in al)


def test_cost_spike_is_a_ticket():
    df = _traffic()
    df.loc[(df.day * 1440 + df.minute).between(600, 900), "cost_eur"] = 0.009
    al = monitor.alerts(df, BASE, 0, 3 * 1440 - 1)
    assert [a.severity for a in al if a.name == "AI cost per conversation"] == ["ticket"]
