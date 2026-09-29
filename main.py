import os, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

try:
    from hindsight_client import Hindsight
except Exception:
    Hindsight = None

try:
    from groq import Groq
except Exception:
    Groq = None

BASE = Path(__file__).resolve().parent.parent
FRONTEND = BASE / "frontend"

app = FastAPI(title="MemoryOps", version="1.0.0")

HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "memoryops")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

hindsight = None
if Hindsight:
    try:
        hindsight = Hindsight(
            base_url=HINDSIGHT_BASE_URL,
            api_key=HINDSIGHT_API_KEY or None
        )
    except Exception:
        hindsight = None

groq_client = Groq(api_key=GROQ_API_KEY) if (Groq and GROQ_API_KEY) else None

DEMO_MEMORIES = [
    {
        "id": "INC-102",
        "service": "Payment API",
        "error": "HTTP 503",
        "severity": "Critical",
        "root_cause": "Database connection pool exhaustion",
        "resolution": "Increased connection pool from 50 to 100",
        "outcome": "Successfully resolved in 18 minutes",
    },
    {
        "id": "INC-147",
        "service": "Payment API",
        "error": "HTTP 503",
        "severity": "High",
        "root_cause": "Database connection pool exhaustion",
        "resolution": "Raised pool capacity and restarted affected workers",
        "outcome": "Successfully resolved in 14 minutes",
    },
    {
        "id": "INC-183",
        "service": "Payment API",
        "error": "Request timeout",
        "severity": "High",
        "root_cause": "Slow database query",
        "resolution": "Optimized query and added an index",
        "outcome": "Successfully resolved in 27 minutes",
    },
    {
        "id": "INC-211",
        "service": "Auth Service",
        "error": "HTTP 401",
        "severity": "Medium",
        "root_cause": "Expired signing key",
        "resolution": "Rotated signing key and refreshed service configuration",
        "outcome": "Successfully resolved in 11 minutes",
    },
    {
        "id": "INC-229",
        "service": "Order API",
        "error": "HTTP 500",
        "severity": "High",
        "root_cause": "Null response from inventory dependency",
        "resolution": "Added response validation and dependency timeout handling",
        "outcome": "Successfully resolved in 22 minutes",
    },
]

class Incident(BaseModel):
    title: str
    service: str
    error: str
    severity: str
    description: str

class Resolution(BaseModel):
    incident: Incident
    root_cause: str
    action: str
    outcome: str
    resolution_time: int
    helpful: bool
    notes: str = ""

def local_recall(incident: Incident):
    q = f"{incident.service} {incident.error} {incident.title} {incident.description}".lower()
    terms = set(q.replace(",", " ").replace(".", " ").split())
    scored = []
    for m in DEMO_MEMORIES:
        text = " ".join(str(v) for v in m.values()).lower()
        score = sum(1 for t in terms if len(t) > 3 and t in text)
        if incident.service.lower() in m["service"].lower():
            score += 5
        if incident.error.lower() in m["error"].lower():
            score += 5
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for score, m in scored[:3] if score > 0]

def hindsight_recall(incident: Incident):
    if not hindsight or not HINDSIGHT_API_KEY:
        return []
    try:
        result = hindsight.recall(
            bank_id=BANK_ID,
            query=f"Production incident: service={incident.service}; error={incident.error}; "
                  f"title={incident.title}; description={incident.description}",
            types=["experience", "observation"],
            max_tokens=4096,
            budget="mid",
        )
        return [{"id": f"MEM-{i+1}", "service": "Historical memory",
                 "error": "", "severity": "", "root_cause": "",
                 "resolution": r.text, "outcome": "Retrieved from Hindsight"}
                for i, r in enumerate(result.results[:5])]
    except Exception:
        return []

def build_recommendation(incident, memories):
    if not memories:
        return {
            "summary": "No matching historical memory was found. Start with standard incident investigation.",
            "steps": [
                "Check the service health and recent error logs.",
                "Review recent deployments or configuration changes.",
                "Inspect dependencies and resource utilization.",
                "Record the confirmed root cause and resolution after recovery."
            ],
            "why": ["No sufficiently similar incident was found in available memory."]
        }

    best = memories[0]
    return {
        "summary": f"Historical memory suggests investigating {best.get('root_cause') or 'the previously observed failure pattern'} first.",
        "steps": [
            f"Investigate the historical root cause: {best.get('root_cause') or 'review the retrieved incident details'}.",
            f"Compare the current symptoms with the previous resolution: {best.get('resolution') or 'review the retrieved memory'}.",
            "Validate the recommendation against current logs and system state before taking action.",
            "Record the final root cause and outcome so the agent can learn from this incident."
        ],
        "why": [
            f"Found {len(memories)} relevant historical memory item(s).",
            "The recommendation is based on previous incident experience.",
            "Historical solutions are treated as evidence, not guaranteed fixes."
        ]
    }

@app.get("/")
def home():
    return FileResponse(FRONTEND / "index.html")

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "hindsight_configured": bool(hindsight and HINDSIGHT_API_KEY),
        "groq_configured": bool(groq_client),
        "bank_id": BANK_ID
    }

@app.post("/api/analyze")
def analyze(incident: Incident):
    memories = hindsight_recall(incident)
    if not memories:
        memories = local_recall(incident)

    recommendation = build_recommendation(incident, memories)

    if groq_client:
        try:
            prompt = f"""You are MemoryOps, an incident-response assistant.
Current incident:
{incident.model_dump_json(indent=2)}

Historical memories:
{json.dumps(memories, indent=2)}

Return a concise, operationally useful response with:
1. incident summary
2. likely causes
3. recommended investigation steps
4. why historical memory matters
5. explicit warning that historical resolutions must be validated before execution.
Do not claim certainty without evidence."""
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a careful DevOps incident-response assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )
            recommendation["llm_analysis"] = response.choices[0].message.content
        except Exception as e:
            recommendation["llm_analysis"] = None

    return {
        "incident": incident,
        "memories": memories,
        "recommendation": recommendation
    }

@app.post("/api/resolve")
def resolve(payload: Resolution):
    content = f"""Incident resolution record:
Incident title: {payload.incident.title}
Service: {payload.incident.service}
Error: {payload.incident.error}
Severity: {payload.incident.severity}
Description: {payload.incident.description}
Confirmed root cause: {payload.root_cause}
Action taken: {payload.action}
Outcome: {payload.outcome}
Resolution time: {payload.resolution_time} minutes
Recommendation helpful: {payload.helpful}
Notes: {payload.notes}
Recorded at: {datetime.utcnow().isoformat()}Z
"""
    stored = False
    if hindsight and HINDSIGHT_API_KEY:
        try:
            hindsight.retain(
                bank_id=BANK_ID,
                content=content,
                context="MemoryOps incident resolution / post-mortem",
                metadata={
                    "service": payload.incident.service,
                    "severity": payload.incident.severity,
                    "source": "memoryops"
                }
            )
            stored = True
        except Exception:
            stored = False

    # Local fallback makes the demo visibly learn even without API credentials.
    DEMO_MEMORIES.insert(0, {
        "id": f"NEW-{datetime.now().strftime('%H%M%S')}",
        "service": payload.incident.service,
        "error": payload.incident.error,
        "severity": payload.incident.severity,
        "root_cause": payload.root_cause,
        "resolution": payload.action,
        "outcome": payload.outcome
    })

    return {
        "success": True,
        "stored_in_hindsight": stored,
        "message": "Resolution recorded. The new experience is available for future incident matching."
    }
