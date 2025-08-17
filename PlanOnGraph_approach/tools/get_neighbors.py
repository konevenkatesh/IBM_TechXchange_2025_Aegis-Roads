from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import os
import requests
from typing import Dict, Any, List

OUT_TPL = "SELECT DISTINCT ?n WHERE { <{e}> <{p}> ?n } LIMIT {limit}"
IN_TPL  = "SELECT DISTINCT ?n WHERE { ?n <{p}> <{e}> } LIMIT {limit}"

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
    s = (iri or "").strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1].strip()
    return s

@tool(
    name="get_neighbors",
    description="Fetch neighbor entities for (entity, relation) with direction 'out' or 'in'. Returns candidates and triples.",
    permission=ToolPermission.ADMIN
)
def get_neighbors(endpoint_url: str, entity_iri: str, relation_iri: str, direction: str = "out", limit: int = 100) -> dict:
    """
    :param endpoint_url: Fuseki endpoint (uses FUSEKI_ENDPOINT if empty)
    :param entity_iri: subject/object IRI (with or without angle brackets)
    :param relation_iri: predicate IRI (with or without angle brackets)
    :param direction: "out" for <e> <p> ?n ; "in" for ?n <p> <e>
    :param limit: max neighbors to return (default 100)
    :return: {"candidates": [iri_or_literal, ...], "triples": [[s,p,o], ...]} or {"error": "..."}
    """
    e = _sanitize_iri(entity_iri)
    p = _sanitize_iri(relation_iri)
    if not e or not p:
        return {"error": "Empty entity_iri or relation_iri"}
    if direction not in ("out", "in"):
        return {"error": "direction must be 'out' or 'in'"}

    sparql = (OUT_TPL if direction == "out" else IN_TPL).format(e=e, p=p, limit=int(limit))
    data = _post(endpoint_url, sparql)
    if "error" in data:
        return {"error": data["error"]}

    triples: List[List[str]] = []
    bindings = data.get("results", {}).get("bindings", []) if isinstance(data, dict) else []
    for b in bindings:
        n = b.get("n", {}).get("value")
        if not n:
            continue
        if direction == "out":
            triples.append([e, p, n])
        else:
            triples.append([n, p, e])

    # dedupe while preserving order
    seen = set()
    triples_unique = []
    for t in triples:
        tt = tuple(t)
        if tt not in seen:
            triples_unique.append(t)
            seen.add(tt)

    return {"candidates": [t[-1] for t in triples_unique], "triples": triples_unique}
