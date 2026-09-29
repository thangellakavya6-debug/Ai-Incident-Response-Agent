# MemoryOps — AI Incident Response Agent

A hackathon MVP for the Hindsight "AI Agents That Learn Using Hindsight" challenge.

## Core workflow
Report Incident -> Analyze -> Recall Hindsight Memory -> Recommend -> Resolve -> Retain New Learning

## Stack
- Frontend: HTML/CSS/JavaScript
- Backend: Python + FastAPI
- Memory: Hindsight
- LLM: Groq

## Setup

1. Create a virtual environment:
   python -m venv .venv

2. Activate it on Windows:
   .venv\Scripts\activate

3. Install dependencies:
   pip install -r backend/requirements.txt

4. Copy `.env.example` to `.env` and add:
   HINDSIGHT_API_KEY=...
   GROQ_API_KEY=...
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   HINDSIGHT_BANK_ID=memoryops

5. Start:
   uvicorn backend.main:app --reload

6. Open:
   http://127.0.0.1:8000

The backend serves the frontend as well.

## Demo
The app includes realistic demo incidents. To make the Hindsight learning loop visible:
- submit the Payment API 503 incident
- inspect historical memory
- record the resolution
- submit a similar incident again

The real Hindsight integration is optional during UI development. If keys are missing, the app falls back to local demo memories so the interface can still be demonstrated.
