"""Plain-language alerts: decision support for a non-doctor, never a diagnosis."""

LABEL = {"hr": "Heart rate", "hrv_rmssd": "Heart rate variability", "spo2": "Oxygen saturation",
         "temp": "Body temperature", "resp_rate": "Breathing rate", "bp_sys": "Blood pressure"}

# (metric, direction) -> (title, explanation, guidance)
PHYSIOLOGICAL = {
    ("hr", "up"): ("Heart rate above your baseline",
                   "Your heart is beating faster than usual. Exertion, stress, heat or low oxygen can all do this.",
                   ["Stop what you are doing and sit or float calmly for a few minutes.",
                    "Take slow, deep breaths and drink some water.",
                    "Check the cabin temperature and air quality.",
                    "If it stays high at rest, report it to the flight surgeon."]),
    ("hr", "down"): ("Heart rate below your baseline",
                     "Your heart is beating slower than usual. This can be normal at rest but should be checked if you feel unwell.",
                     ["Note whether you feel dizzy, faint or unusually tired.",
                      "Move slowly and avoid sudden changes of position.",
                      "Report it to the flight surgeon if you feel unwell."]),
    ("hrv_rmssd", "down"): ("Heart rate variability is low",
                            "Low variability means your body is under strain, often from stress, poor sleep or fatigue.",
                            ["Plan a rest period and aim for a full sleep cycle.",
                             "Postpone demanding tasks if you can.",
                             "Log how you feel in the daily check-in.",
                             "If it stays low for a day or more, tell the flight surgeon."]),
    ("spo2", "down"): ("Oxygen saturation below your baseline",
                       "The oxygen level in your blood is lower than usual. This can come from poor cabin air or a breathing problem.",
                       ["Check the cabin oxygen and carbon dioxide levels.",
                        "Sit upright and take slow, deep breaths.",
                        "Stop strenuous activity until it recovers.",
                        "Report it to the flight surgeon if it does not improve."]),
    ("temp", "up"): ("Body temperature above your baseline",
                     "Your temperature is higher than usual. Heat, exercise, fatigue or an infection can cause this.",
                     ["Rest and cool down, and check the cabin temperature.",
                      "Drink water.",
                      "Re-measure in 15 minutes.",
                      "Report it to the flight surgeon if it keeps rising."]),
    ("temp", "down"): ("Body temperature below your baseline",
                       "Your temperature is lower than usual, which can happen when you are cold or exhausted.",
                       ["Put on warmer clothing and check the cabin temperature.",
                        "Have a warm drink or meal.",
                        "Re-measure in 15 minutes."]),
    ("resp_rate", "up"): ("Breathing faster than usual",
                          "You are breathing more quickly than your baseline. Exertion, stress or low oxygen can cause this.",
                          ["Pause and breathe slowly: in for 4 seconds, out for 6.",
                           "Check the cabin air quality.",
                           "Report it to the flight surgeon if it continues at rest."]),
    ("resp_rate", "down"): ("Breathing slower than usual",
                            "You are breathing more slowly than your baseline.",
                            ["Take a few deliberate deep breaths.",
                             "Note whether you feel drowsy or lightheaded.",
                             "Report it to the flight surgeon if it continues."]),
    ("bp_sys", "up"): ("Blood pressure above your baseline",
                       "Your estimated blood pressure is higher than usual. Stress, fluid shifts or exertion can cause this.",
                       ["Rest quietly and breathe slowly for a few minutes.",
                        "Drink water and avoid caffeine.",
                        "Re-measure in 15 minutes.",
                        "Report it to the flight surgeon if it stays high."]),
    ("bp_sys", "down"): ("Blood pressure below your baseline",
                         "Your estimated blood pressure is lower than usual. Fluid shifts in microgravity can cause this.",
                         ["Move slowly and avoid sudden changes of position.",
                          "Drink water.",
                          "Report it to the flight surgeon if you feel dizzy or faint."]),
}

# sensor -> (metric the alert is filed under, title, explanation, guidance)
ARTIFACT = {
    "ecg": ("hr", "ECG signal lost",
            "The ECG signal is noisy or flat, so heart rate and variability readings are ignored. This looks like a sensor problem, not a heart problem.",
            ["Check that the ECG electrodes are firmly attached to your skin.",
             "Press each electrode and check the cable connection.",
             "Wait about 30 seconds for the signal to return.",
             "If it does not, replace the electrodes."]),
    "ppg": ("spo2", "Radiation hit on the pulse sensor",
            "Sharp spikes on the pulse sensor match radiation striking it. Oxygen and blood pressure readings are ignored until the signal is clean.",
            ["No action is needed for your body based on these readings.",
             "Check the radiation dose rate on this screen.",
             "If radiation is high, move to the shielded area."]),
}
SENSOR = {"hr": "ecg", "hrv_rmssd": "ecg", "spo2": "ppg", "bp_sys": "ppg"}

RADIATION = {
    "amber": ("Radiation dose rate is elevated",
              "The radiation level is above normal. This may be the start of a solar particle event.",
              ["Check the space weather forecast on this screen.",
               "Limit time in lightly shielded areas.",
               "Be ready to move to the shielded area."]),
    "red": ("Radiation dose rate is high",
            "The radiation level is dangerously high, as in a strong solar particle event.",
            ["Move to the shielded area now.",
             "Stay there until the dose rate drops.",
             "Contact ground control and report your exposure.",
             "Log how you feel in the daily check-in."]),
}


def _generic(metric):
    return (f"{LABEL[metric]} changed from your baseline",
            "This reading moved away from your normal range.",
            ["Rest for a few minutes and re-check.", "Report it to the flight surgeon if it persists."])


class AlertTracker:
    """Keeps an alert alive, with a stable id, for as long as its condition holds."""

    MAX_ALERTS = 5

    def __init__(self):
        self.active = {}

    def update(self, t, results, radiation):
        wanted = {}
        for name, r in results.items():
            if r.artifact:
                sensor = SENSOR.get(name)
                if sensor is None:
                    continue
                metric, title, why, steps = ARTIFACT[sensor]
                wanted[(metric, "artifact", "amber")] = (title, why, steps)
            elif r.status != "green":
                direction = "up" if r.delta > 0 else "down"
                title, why, steps = PHYSIOLOGICAL.get((name, direction)) or _generic(name)
                if r.status == "red":
                    steps = steps[:3] + ["Contact the flight surgeon on the ground now."]
                wanted[(name, "physiological", r.status)] = (title, why, steps)
        if radiation != "green":
            wanted[("radiation", "physiological", radiation)] = RADIATION[radiation]

        self.active = {k: a for k, a in self.active.items() if k in wanted}
        for key, (title, why, steps) in wanted.items():
            if key not in self.active:
                metric, origin, level = key
                self.active[key] = {"id": f"{metric}-{int(t)}", "t": round(t, 1), "metric": metric, "level": level,
                                    "origin": origin, "title": title, "explanation": why, "guidance": steps}
        newest_first = sorted(self.active.values(), key=lambda a: a["t"], reverse=True)
        return newest_first[:self.MAX_ALERTS]
