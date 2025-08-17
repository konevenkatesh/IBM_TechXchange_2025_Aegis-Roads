# file: fuseki_proxy.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from requests.auth import HTTPBasicAuth
import requests, os

# ---- Configure these (or use env vars) ----
FUSEKI     = os.getenv("FUSEKI_BASE", "https://40af5a14eaa8.ngrok-free.app/amaravati")
FUSEKI_USER = os.getenv("FUSEKI_USER", "admin")
FUSEKI_PASS = os.getenv("FUSEKI_PASS", "StrongPass123")
AUTH = HTTPBasicAuth(FUSEKI_USER, FUSEKI_PASS)  # used for UPDATE; add to SELECT if needed
# -------------------------------------------

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # set specific origins if you need credentials/cookies
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SPARQLQuery(BaseModel):
    query: str

def _is_graph_query(q: str) -> bool:
    q0 = q.lstrip().upper()
    return q0.startswith("CONSTRUCT") or q0.startswith("DESCRIBE")

@app.get("/health")
def health():
    return {"ok": True, "fuseki": FUSEKI}

@app.post("/query")
def query(body: SPARQLQuery):
    # SELECT/ASK -> JSON; CONSTRUCT/DESCRIBE -> JSON-LD (so still JSON)
    accept = "application/sparql-results+json"
    if _is_graph_query(body.query):
        accept = "application/ld+json"

    try:
        r = requests.post(
            f"{FUSEKI}/sparql",
            data=body.query.encode("utf-8"),
            headers={"Accept": accept, "Content-Type": "application/sparql-query"},
            timeout=60,
            # auth=AUTH,  # uncomment if your /sparql requires auth
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    if accept == "application/sparql-results+json":
        return JSONResponse(r.json())
    else:
        return Response(content=r.text, media_type=accept)

@app.post("/update")
def update(body: SPARQLQuery):
    try:
        r = requests.post(
            f"{FUSEKI}/update",
            data=body.query.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            auth=AUTH,     # updates usually require admin
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return {"ok": True}
