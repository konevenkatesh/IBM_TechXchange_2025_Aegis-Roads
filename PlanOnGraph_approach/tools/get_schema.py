from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import os
import requests

SCHEMA_CLASS_QUERY = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?cls (SAMPLE(?lbl) AS ?label)
WHERE {
  ?cls a owl:Class .
  OPTIONAL { ?cls rdfs:label ?lbl }
}
GROUP BY ?cls
"""

SCHEMA_PROP_QUERY = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?p ?type ?domain ?range (SAMPLE(?lbl) AS ?label)
WHERE {
  VALUES ?type { owl:ObjectProperty owl:DatatypeProperty }
  ?p a ?type .
  OPTIONAL { ?p rdfs:domain ?domain }
  OPTIONAL { ?p rdfs:range  ?range }
  OPTIONAL { ?p rdfs:label  ?lbl }
}
GROUP BY ?p ?type ?domain ?range
"""

def _post(endpoint: str, query: str):
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

@tool(
    name="get_schema",
    description="Return ontology schema (classes, properties, domain/range, labels).",
    permission=ToolPermission.ADMIN
)
def get_schema(endpoint_url: str) -> dict:
    classes = _post(endpoint_url, SCHEMA_CLASS_QUERY)
    if "error" in classes:
        return {"error": classes["error"]}
    props = _post(endpoint_url, SCHEMA_PROP_QUERY)
    if "error" in props:
        return {"error": props["error"]}
    # keep same contract your orchestrator expects
    return {"classes": classes, "properties": props}
