"""Signal processing: validation, ECG filtering, R-peak detection and signal quality."""
from typing import Annotated

import numpy as np
from pydantic import Field, TypeAdapter, ValidationError
from scipy.signal import butter, find_peaks, sosfiltfilt

from .simulator import FS
from .stats import ARTIFACT_SQI, BASELINE

ECG_WINDOW = 15 * FS
PPG_WINDOW = 5 * FS
SOS = butter(4, [0.5, 40], btype="band", fs=FS, output="sos")
SPIKE_JUMP = 0.15  # a normal pulse never rises this much in one sample
SPIKES_FOR_ZERO_SQI = 6

# Physically possible ranges; anything outside is a sensor fault, not a patient
LIMITS = {"hr": (20, 250), "hrv_rmssd": (0, 300), "spo2": (50, 100),
          "temp": (30, 43), "resp_rate": (3, 60), "bp_sys": (50, 260)}
_CHECKS = {k: TypeAdapter(Annotated[float, Field(ge=lo, le=hi)]) for k, (lo, hi) in LIMITS.items()}
NOISE = {"spo2": 0.3, "temp": 0.05, "resp_rate": 0.5, "bp_sys": 2.0}
TRUTH_KEY = {"spo2": "spo2", "temp": "temp", "resp_rate": "resp", "bp_sys": "bp_sys"}
ECG_VITALS = ("hr", "hrv_rmssd")
PPG_VITALS = ("spo2", "bp_sys")


def is_valid(name, value):
    try:
        _CHECKS[name].validate_python(float(value))
        return True
    except ValidationError:
        return False


def ecg_metrics(ecg):
    """Return (hr, rmssd, sqi) from a raw ECG window; hr and rmssd are None if not measurable."""
    sig = sosfiltfilt(SOS, ecg)
    threshold = max(0.5 * np.percentile(sig, 99.5), 1e-6)
    peaks, _ = find_peaks(sig, height=threshold, distance=int(0.3 * FS))
    if len(peaks) < 4:
        return None, None, 0.0
    rr = np.diff(peaks) / FS
    # Real beats are evenly spaced and tower over the background; noise is neither
    regular = np.mean(np.abs(rr - np.median(rr)) < 0.25 * np.median(rr))
    prominence = np.clip((np.median(sig[peaks]) / np.std(sig) - 2.0) / 2.0, 0, 1)
    sqi = float(regular * prominence)
    rr = rr[(rr > 0.3) & (rr < 2.0)]
    if len(rr) < 3:
        return None, None, sqi
    return 60 / rr.mean(), float(np.sqrt(np.mean(np.diff(rr) ** 2)) * 1000), sqi


def ppg_sqi(ppg):
    spikes = np.sum(np.diff(ppg) > SPIKE_JUMP)
    return float(np.clip(1 - spikes / SPIKES_FOR_ZERO_SQI, 0, 1))


class Pipeline:
    def __init__(self, rng):
        self.rng = rng
        self.ecg = np.zeros(0)
        self.ppg = np.zeros(0)
        self.trusted = dict(BASELINE)  # last valid reading from a trustworthy sensor

    @property
    def ready(self):
        return len(self.ecg) >= ECG_WINDOW

    def push(self, chunk):
        self.ecg = np.concatenate([self.ecg, chunk.ecg])[-ECG_WINDOW:]
        self.ppg = np.concatenate([self.ppg, chunk.ppg])[-PPG_WINDOW:]

    def measure(self, truth):
        """Return (values, sqi) for the six vitals."""
        hr, rmssd, ecg_q = ecg_metrics(self.ecg)
        ppg_q = ppg_sqi(self.ppg)
        raw = {"hr": hr, "hrv_rmssd": rmssd}
        for name, key in TRUTH_KEY.items():
            raw[name] = truth[key] + self.rng.normal(0, NOISE[name])
        sqi = {name: 1.0 for name in raw}
        sqi.update({n: ecg_q for n in ECG_VITALS} | {n: ppg_q for n in PPG_VITALS})
        values = {}
        for name, v in raw.items():
            # A sensor under suspicion keeps its last good reading instead of feeding garbage downstream
            if v is not None and sqi[name] >= ARTIFACT_SQI and is_valid(name, v):
                self.trusted[name] = float(v)
            values[name] = self.trusted[name]
        return values, sqi
