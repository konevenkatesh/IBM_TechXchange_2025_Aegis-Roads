from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import os
import requests
from typing import Dict, Any, List

RELATIONS_TPL = """
SELECT ?p (COUNT(*) AS ?count) WHERE {
  { <{entity}> ?p ?o } UNION { ?s ?p <{entity}> }
}
GROUP BY ?p
ORDER BY DESC(?count)
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

def _sanitize_iri(iri: str) -> str:
    """Remove surrounding angle brackets/spaces; return the bare IRI string."""
    s = (iri or "").strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1].strip()
    return s

@tool(
    name="get_relations",
    description="List adjacent predicates for an entity (incoming + outgoing), with counts.",
    permission=ToolPermission.ADMIN
)
def get_relations(endpoint_url: str, entity_iri: str) -> dict:
    """
    :param endpoint_url: Fuseki endpoint (fallback to FUSEKI_ENDPOINT)
    :param entity_iri: Full IRI of the entity (with or without angle brackets)
    :return: {"relations": [{"iri": "...", "count": 12}, ...]} or {"error": "..."}
    """
    e = _sanitize_iri(entity_iri)
    if not e:
        return {"error": "Empty entity_iri"}

    sparql = RELATIONS_TPL.format(entity=e)
    data = _post(endpoint_url, sparql)
    if "error" in data:
        return {"error": data["error"]}

    bindings = data.get("results", {}).get("bindings", []) if isinstance(data, dict) else []
    rels: List[Dict[str, Any]] = []
    for b in bindings:
        p = b.get("p", {}).get("value")
        c = b.get("count", {}).get("value")
        if p:
            try:
                cnt = int(float(c)) if c is not None else 0
            except Exception:
                cnt = 0
            rels.append({"iri": p, "count": cnt})

    return {"relations": rels}
