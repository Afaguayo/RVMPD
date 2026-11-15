import numpy as np

from app.stats import BASELINE, VitalStats

rng = np.random.default_rng(0)
SPREAD = {"hr": 1.5, "hrv_rmssd": 4.0, "spo2": 0.3, "temp": 0.05, "resp_rate": 0.5, "bp_sys": 2.0}
FULL_SQI = {name: 1.0 for name in BASELINE}


def run(stats, seconds, shift=None, sqi=None):
    """Feed noisy one-second values; `shift` moves chosen vitals away from baseline."""
    shift = shift or {}
    for _ in range(seconds):
        values = {n: BASELINE[n] + shift.get(n, 0) + rng.normal(0, SPREAD[n]) for n in BASELINE}
        results = stats.update(values, sqi or FULL_SQI)
    return results


def test_nominal_stays_green():
    stats = VitalStats()
    for _ in range(10):
        results = run(stats, 5)
        assert all(r.status == "green" for r in results.values())


def test_small_significant_drift_stays_green():
    # Clearly different from baseline statistically, but below the caution delta
    results = run(VitalStats(), 15, shift={"hr": 4.0})
    assert results["hr"].p_adj < 0.05
    assert results["hr"].status == "green"


def test_big_sustained_drop_goes_red():
    results = run(VitalStats(), 15, shift={"spo2": -10.0})
    assert results["spo2"].status == "red"
    assert results["spo2"].p_adj < 0.05


def test_low_sqi_is_capped_at_amber():
    results = run(VitalStats(), 15, shift={"spo2": -10.0}, sqi={**FULL_SQI, "spo2": 0.2})
    assert results["spo2"].artifact
    assert results["spo2"].status == "amber"
