"""Statistical status of each vital against the astronaut's personal baseline."""
from collections import deque
from dataclasses import dataclass

import numpy as np
from scipy.stats import ttest_1samp
from statsmodels.stats.multitest import multipletests

BASELINE = {"hr": 68.0, "hrv_rmssd": 45.0, "spo2": 98.0, "temp": 36.6, "resp_rate": 14.0, "bp_sys": 117.0}
UNIT = {"hr": "bpm", "hrv_rmssd": "ms", "spo2": "%", "temp": "°C", "resp_rate": "rpm", "bp_sys": "mmHg"}

# (caution, action): the smallest change that matters clinically, and the change that needs action.
# A drift smaller than the caution delta stays green even when it is statistically significant.
DELTAS = {
    "hr": (10.0, 25.0), "hrv_rmssd": (15.0, 30.0), "spo2": (3.0, 6.0),
    "temp": (0.5, 1.2), "resp_rate": (4.0, 9.0), "bp_sys": (15.0, 30.0),
}

WINDOW = 10  # last one-second values kept per vital
MIN_SAMPLES = 5
ALPHA = 0.05
ARTIFACT_SQI = 0.5
RADIATION_AMBER, RADIATION_RED = 100.0, 300.0  # uSv/h
RANK = {"green": 0, "amber": 1, "red": 2}


@dataclass
class VitalResult:
    name: str
    value: float
    sqi: float
    delta: float
    status: str
    p_adj: float

    @property
    def artifact(self):
        return self.sqi < ARTIFACT_SQI

    def as_dict(self):
        return {"value": round(self.value, 1), "unit": UNIT[self.name], "baseline": BASELINE[self.name],
                "delta": round(self.delta, 1), "status": self.status,
                "p_adj": round(self.p_adj, 3), "sqi": round(self.sqi, 2)}


def classify(name, delta, rejected, sqi):
    caution, action = DELTAS[name]
    if not rejected or abs(delta) < caution:
        status = "green"
    elif abs(delta) >= action:
        status = "red"
    else:
        status = "amber"
    # A sensor we do not trust can warn but never trigger the red alarm
    if sqi < ARTIFACT_SQI and status == "red":
        status = "amber"
    return status


def _p_value(samples, baseline):
    if len(samples) < MIN_SAMPLES:
        return 1.0
    if np.ptp(samples) == 0:  # the t-test is undefined without any spread
        return 1.0 if samples[0] == baseline else 0.0
    return float(ttest_1samp(samples, baseline).pvalue)


def radiation_status(dose_rate):
    if dose_rate >= RADIATION_RED:
        return "red"
    return "amber" if dose_rate >= RADIATION_AMBER else "green"


def global_status(results, radiation):
    return max([r.status for r in results.values()] + [radiation], key=RANK.get)


class VitalStats:
    def __init__(self):
        self.history = {name: deque(maxlen=WINDOW) for name in BASELINE}

    def update(self, values, sqi):
        """Add one second of values and return a VitalResult per vital."""
        for name, v in values.items():
            self.history[name].append(v)
        names = list(BASELINE)
        p = [_p_value(list(self.history[n]), BASELINE[n]) for n in names]
        # Six tests at once: the Holm correction keeps the false-alarm rate at ALPHA
        rejected, p_adj, _, _ = multipletests(p, alpha=ALPHA, method="holm")
        results = {}
        for n, rej, pa in zip(names, rejected, p_adj):
            delta = values[n] - BASELINE[n]
            results[n] = VitalResult(n, values[n], sqi[n], delta, classify(n, delta, bool(rej), sqi[n]), float(pa))
        return results
