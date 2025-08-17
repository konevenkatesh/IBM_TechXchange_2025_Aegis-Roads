from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import os
import requests
from typing import Any, Dict

@tool(
    name="run_sparql_query",
    description="Execute a SPARQL query on a Fuseki endpoint and return JSON results.",
    permission=ToolPermission.ADMIN
)
def run_sparql_query(endpoint_url: str, query: str) -> Dict[str, Any]:
    """
    Execute a SPARQL query via HTTP POST.
    Returns:
      {"results": {...}} on success, or {"error": "..."} on failure.
    """
    # Fallback to env if endpoint_url not provided
    endpoint = (endpoint_url or os.getenv("FUSEKI_ENDPOINT", "")).strip()

    if not endpoint:
        return {"error": "Missing endpoint_url (and FUSEKI_ENDPOINT not set)"}

    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/sparql-query",
        "User-Agent": "pog-tools/1.0"
    }

    try:
        resp = requests.post(endpoint, data=query.encode("utf-8"), headers=headers, timeout=60)
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:500]}"}

        # Try JSON first
        try:
            return {"results": resp.json()}
        except ValueError:
            # Non-JSON body (e.g., text/html error page or unexpected format)
            return {
                "results": {
                    "content_type": resp.headers.get("Content-Type", ""),
                    "text": resp.text[:2000]
                }
            }

    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

