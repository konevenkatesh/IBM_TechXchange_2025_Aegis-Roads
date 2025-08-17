from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from typing import List, Dict, Any
import re

def _tokens(s: str) -> List[str]:
    """Lowercase alphanumeric tokens."""
    return re.findall(r"[A-Za-z0-9]+", (s or "").lower())

def _localname(iri: str) -> str:
    """Heuristic label from IRI (after '#'/last '/')."""
    if not iri:
        return ""
    pos = max(iri.rfind('#'), iri.rfind('/'))
    return iri[pos + 1:] if pos != -1 else iri

@tool(
    name="rank_candidates",
    description="Rank candidate entities against a question using a simple lexical score.",
    permission=ToolPermission.ADMIN
)
def rank_candidates(
    question: str,
    candidates: List[str],
    top_k: int = 5,
    candidate_labels: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """
    :param question: user question text
    :param candidates: list of candidate IRIs or literals
    :param top_k: maximum items to return
    :param candidate_labels: optional mapping {candidate_iri: human_label}
    :return: {"topk": [candidate, ...]}
    """
    q = " ".join(_tokens(question))
    q_set = set(_tokens(question))

    # de-duplicate while preserving order
    seen = set()
    cand_list = []
    for c in candidates or []:
        if c and c not in seen:
            cand_list.append(c)
            seen.add(c)

    scored = []
    for c in cand_list:
        # prefer provided label; else derive from IRI
        label = (candidate_labels or {}).get(c) or _localname(c) or str(c)
        toks = set(_tokens(label))

        # simple overlap score + small bonus for substring match
        overlap = len(q_set & toks)
        bonus = 2 if label.lower() in q or any(w in label.lower() for w in q_set) else 0
        score = overlap * 2 + bonus

        # stable tie-break by label then IRI
        scored.append((score, label, c))

    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    k = max(1, int(top_k)) if top_k else 5
    top = [c for _, _, c in scored[:k]]
    return {"topk": top}
