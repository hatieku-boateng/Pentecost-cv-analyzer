# Modern Interactive App

This repository now includes a React + Vite frontend and a FastAPI backend that work beside the original Streamlit app.

## Run the API

```powershell
cd api
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Run the Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://127.0.0.1:5173`.

## What It Adds

- React single-page interface with live vacancy search, faculty filters, role-aware navigation, upload panels, dashboard metrics, and charts.
- FastAPI endpoints for login, signup, jobs, applications, uploads, scheduling, HR recommendation, and VC approval.
- Existing CSV data and uploaded files remain in `Proje/data`.
- The original Streamlit app in `Proje/app.py` is unchanged.
