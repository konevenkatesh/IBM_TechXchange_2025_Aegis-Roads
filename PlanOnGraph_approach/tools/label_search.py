from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import os, requests
from typing import List, Dict, Any

ADTO_NS = os.getenv("ADTO_NS", "http://www.projectsynapse.com/ontologies/adto#")

LABEL_OR_NAME_SEARCH = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX adto: <%(ADTO)s>
SELECT DISTINCT ?e ?name
WHERE {
  {
    ?e rdfs:label ?name .
    FILTER(LANGMATCHES(LANG(?name),'en') || LANG(?name) = '')
    FILTER(CONTAINS(LCASE(STR(?name)), LCASE(%(q)s)))
  }
  UNION
  {
    ?e adto:hasName ?name .
    FILTER(CONTAINS(LCASE(STR(?name)), LCASE(%(q)s)))
  }
}
LIMIT 50
"""

# Fallback: find instances by matching the CLASS label (e.g., "Road Segment")
CLASS_INSTANCE_FALLBACK = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX adto: <%(ADTO)s>
SELECT DISTINCT ?e (COALESCE(?n1, ?n2, ?clsLabel, STR(?e)) AS ?name)
WHERE {
  ?e a ?cls .
  OPTIONAL { ?e adto:hasName ?n1 }
  OPTIONAL { ?e rdfs:label   ?n2 }
  ?cls rdfs:label ?clsLabel .
  FILTER(LANGMATCHES(LANG(?clsLabel),'en') || LANG(?clsLabel) = '')
  FILTER(CONTAINS(LCASE(STR(?clsLabel)), LCASE(%(q)s)))
}
LIMIT 100
"""

def _post(endpoint: str, query: str) -> Dict[str, Any]:
    endpoint = (endpoint or os.getenv("FUSEKI_ENDPOINT", "")).strip()
    if not endpoint:
        return {"error": "Missing endpoint_url (and FUSEKI_ENDPOINT not set)"}
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/sparql-query",
    }
    resp = requests.post(endpoint, data=query.encode("utf-8"), headers=headers, timeout=60)
    if resp.status_code >= 400:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
    try:
        return resp.json()
    except ValueError:
        return {"error": f"Non-JSON response: {resp.text[:500]}"}

def _escape_for_sparql(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')

def _to_candidates(data: Dict[str, Any]) -> List[Dict[str,str]]:
    bindings = data.get("results", {}).get("bindings", []) if isinstance(data, dict) else []
    out = []
    for b in bindings:
        iri = b.get("e", {}).get("value")
        name = b.get("name", {}).get("value")
        if iri and name:
            out.append({"iri": iri, "label": name})
    return out

@tool(
    name="label_search",
    description="Find entities by fuzzy match on rdfs:label or adto:hasName. Falls back to class-matched instances.",
    permission=ToolPermission.ADMIN
)
def label_search(endpoint_url: str, question: str, hints: List[str] = None) -> dict:
    """
    :param endpoint_url: Fuseki endpoint
    :param question: free-text query
    :param hints: optional tokens to append (bias search)
    :return: {"candidates": [{"iri": "...", "label": "..."}]} or {"error": "..."}
    """
    q = (question or "").strip()
    if hints:
        q = (q + " " + " ".join(hints)).strip()
    if not q:
        return {"candidates": []}

    q_lit = f"\"{_escape_for_sparql(q)}\""

    # Strategy 1: label/name
    sparql1 = LABEL_OR_NAME_SEARCH % {"q": q_lit, "ADTO": ADTO_NS}
    data1 = _post(endpoint_url, sparql1)
    if "error" in data1:
        return {"error": data1["error"]}
    cand1 = _to_candidates(data1)
    if cand1:
        return {"candidates": cand1}

    # Strategy 2: class-instance fallback
    sparql2 = CLASS_INSTANCE_FALLBACK % {"q": q_lit, "ADTO": ADTO_NS}
    data2 = _post(endpoint_url, sparql2)
    if "error" in data2:
        return {"error": data2["error"]}
    cand2 = _to_candidates(data2)
    return {"candidates": cand2}
