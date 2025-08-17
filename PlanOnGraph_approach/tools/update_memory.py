from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from typing import Dict, List, Any, Tuple
from datetime import datetime

def _sanitize_iri(x: str) -> str:
    if not isinstance(x, str):
        return ""
    s = x.strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1].strip()
    return s

def _normalize_triple(t: List[str]) -> Tuple[str, str, str] | None:
    if not isinstance(t, (list, tuple)) or len(t) != 3:
        return None
    s, p, o = map(_sanitize_iri, t)
    # literals (o) may be non-IRI; keep as-is if not empty
    if not s or not p or (not o and o != ""):
        return None
    return (s, p, o)

@tool(
    name="update_memory",
    description="Update PoG memory with new triples and entities (dedupe, sanitize, cap sizes).",
    permission=ToolPermission.ADMIN
)
def update_memory(
    memory: Dict[str, Any],
    new_triples: List[List[str]],
    selected_entities: List[str],
    max_subgraph: int = 5000,
    max_frontier: int = 1000,
) -> Dict[str, Any]:
    """
    Returns the updated memory dict with:
      - subgraph: deduped list of [s,p,o]
      - frontier_entities: deduped list of IRIs/literals
      - reasoning_paths: preserved (not modified here)
      - sub_objectives/sub_objective_status: preserved (not modified here)
      - stats.last_update: ISO timestamp
    """
    mem = dict(memory or {})
    mem.setdefault("subgraph", [])
    mem.setdefault("reasoning_paths", [])
    mem.setdefault("frontier_entities", [])
    mem.setdefault("sub_objectives", [])
    mem.setdefault("sub_objective_status", {})
    mem.setdefault("stats", {})

    # --- merge triples (dedupe + sanitize) ---
    existing = {tuple(t) for t in mem["subgraph"] if isinstance(t, (list, tuple)) and len(t) == 3}
    for raw in new_triples or []:
        nt = _normalize_triple(raw)
        if not nt:
            continue
        if nt not in existing:
            mem["subgraph"].append(list(nt))
            existing.add(nt)

    # cap subgraph size (keep newest)
    if len(mem["subgraph"]) > max_subgraph:
        mem["subgraph"] = mem["subgraph"][-max_subgraph:]

    # --- merge frontier entities (dedupe + sanitize) ---
    fe_seen = set(mem["frontier_entities"])
    for e in selected_entities or []:
        e_norm = _sanitize_iri(e) or str(e).strip()
        if not e_norm:
            continue
        if e_norm not in fe_seen:
            mem["frontier_entities"].append(e_norm)
            fe_seen.add(e_norm)

    # cap frontier size (keep newest)
    if len(mem["frontier_entities"]) > max_frontier:
        mem["frontier_entities"] = mem["frontier_entities"][-max_frontier:]

    # simple stats
    mem["stats"]["triple_count"] = len(mem["subgraph"])
    mem["stats"]["frontier_count"] = len(mem["frontier_entities"])
    mem["stats"]["last_update"] = datetime.utcnow().isoformat() + "Z"

    return mem

