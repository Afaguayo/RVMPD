# VITALIS

Health monitoring for astronauts on long missions. Built by team RVMPD for the NASA Space Apps Challenge 2026, challenge "Create Health Monitoring Software for Astronauts on Space Missions".

VITALIS reads the astronaut's vital signs and the radiation dose, compares each one with that person's own baseline, and tells them in plain words what changed and what to do about it. It is decision support, not a medical diagnosis.

## What it does

- Shows live ECG, pulse and breathing waveforms on a phone-sized screen.
- Tracks heart rate, heart rate variability, oxygen saturation, temperature, breathing rate and blood pressure against a personal baseline.
- Tracks radiation dose rate and accumulated dose, and shows live proton flux from NOAA's GOES satellites.
- Raises green, amber or red status with a statistical guarantee: testing six vitals at once still keeps the false alarm rate at 5% or less (Holm-Bonferroni correction).
- Tells a sensor fault or a radiation hit on the sensor apart from a real change in the body, so a loose electrode does not abort a spacewalk.
- Gives step-by-step guidance for every alert, written for someone who is not a doctor.
- Daily check-in for mood and sleep, and a short task list.

## Run it

You need Python 3.11 or newer and Node 20 or newer.

Backend:

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Frontend, in a second terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Use the scenario picker to trigger a solar particle event, hypoxia, a loose electrode or fatigue.

## How it works

```
simulated wearable -> validation -> filtering -> vitals -> statistics -> alerts -> WebSocket -> phone screen
```

The data has no real sensor behind it yet. A simulator produces the signals, behind the same interface a Bluetooth or serial reader would use.

More detail: [docs/PLAN.md](docs/PLAN.md) and [docs/CONTRACT.md](docs/CONTRACT.md).
