# Build plan

Challenge: [Create Health Monitoring Software for Astronauts on Space Missions](https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/) (NASA Space Apps 2026).

## What the challenge asks for

A visual tool that helps astronauts assess their own health and gives guidance on what to do. It must not assume the astronaut is a doctor, so every reading needs a plain explanation and simple steps. The challenge suggests color coding, charts that change over time, a clickable human figure, prompts for routine measurements and a gamified task list.

## What we build for the demo

A phone-sized web app fed by a Python backend. There is no flight hardware, so the backend simulates the wearable and lets the presenter trigger events live.

1. **Sensor simulator.** Produces ECG, pulse (PPG) and breathing waveforms at 250 Hz plus the radiation dose rate. Five scenarios can be switched on during the demo: nominal, solar particle event, hypoxia, loose electrode, fatigue.
2. **Signal pipeline.** Range validation rejects impossible readings, a zero-phase Butterworth filter cleans the ECG, and heart rate, HRV (RMSSD), SpO2, breathing rate and a signal quality index are computed each second.
3. **Statistics.** Each vital is tested against the astronaut's personal baseline. The p-values are corrected with Holm-Bonferroni, so watching six vitals at once keeps the overall false alarm rate at 5% or less.
4. **Artifact or body?** A reading with low signal quality, or a spike that matches a radiation hit on the sensor, is labelled as an artifact and cannot trigger a red alarm. This is the part that separates the project from a plain dashboard.
5. **Guidance.** Every alert carries a plain explanation and numbered steps, shown in a bottom sheet.
6. **App screen.** Three levels: a status bar with the traffic light, dose and confidence badge; a live oscilloscope with a channel switch; a grid of vital cards with the change from baseline and a sparkline. Also a HUD mode with large numbers, a clickable body figure, a daily check-in (mood, sleep, note) and a short task list.
7. **Real data.** The space weather card shows the live proton flux from NOAA's GOES satellites.

## Out of scope for the hackathon

Real BLE or serial sensors, CCSDS packet decoding, Kalman fusion, user accounts and a database. The architecture leaves room for them: the simulator sits behind the same interface a real sensor reader would use.

## Layout

```
backend/    Python, FastAPI. Simulator, pipeline, statistics, WebSocket and REST.
frontend/   React, TypeScript, Vite. The phone screen.
docs/       This plan and the contract between the two halves.
```

## Order of work

| Step | Work | Done when |
|---|---|---|
| 1 | Contract in `docs/CONTRACT.md` | Both halves agree on every field |
| 2 | Backend and frontend, built in parallel against the contract | Backend tests pass; frontend builds |
| 3 | Run both together | Switching a scenario changes the screen within a few seconds |
| 4 | Demo script and 30-second video | Recorded |
| 5 | Optional: host the frontend on AWS Amplify and the backend on EC2 | Public link works |

## Team split for the last day

| Person | Task |
|---|---|
| 1 | Run the demo, record the video |
| 2 | Slides: problem, the five hazards, how VITALIS answers them |
| 3 | Check the alert texts and guidance steps against NASA Human Research Program pages |
| 4 | Submission form text and the prize category wording |
| 5 | Test on a real phone, list what looks wrong |
| 6 | AWS hosting, if time allows |
