from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from typing import Dict, Any, List, Tuple
import re

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_NS   = "http://www.w3.org/2001/XMLSchema#"

def _is_literal(value: str) -> bool:
    return not (isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")))

def _parse_xsd(value: str, xsd: str) -> bool:
    if not isinstance(value, str):
        return False
    t = xsd.replace(XSD_NS, "")
    try:
        if t in ("string",):
            return True
        if t in ("integer", "int", "long", "short", "byte", "nonNegativeInteger", "positiveInteger"):
            int(value); return True
        if t in ("decimal", "float", "double"):
            float(value); return True
        if t in ("boolean",):
            return value.lower() in ("true", "false", "1", "0")
        if t in ("date",):
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
        if t in ("dateTime",):
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}(\.\d+)?z?", value, flags=re.IGNORECASE))
    except Exception:
        return False
    return True

def _normalize_triple(t: Any) -> Tuple[str, str, str] | None:
    if not isinstance(t, (list, tuple)) or len(t) != 3:
        return None
    s, p, o = (str(t[0]).strip(), str(t[1]).strip(), str(t[2]).strip())
    if not s or not p or (o == ""):
        return None
    if s.startswith("<") and s.endswith(">"): s = s[1:-1].strip()
    if p.startswith("<") and p.endswith(">"): p = p[1:-1].strip()
    if o.startswith("<") and o.endswith(">"): o = o[1:-1].strip()
    return (s, p, o)

def _extract_types(triples: List[Tuple[str,str,str]]) -> Dict[str, set]:
    types: Dict[str, set] = {}
    for s,p,o in triples:
        if p == RDF_TYPE:
            types.setdefault(s, set()).add(o)
    return types

def _load_properties(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    prop_map: Dict[str, Dict[str, Any]] = {}
    props = schema.get("properties")
    if not props:
        return prop_map

    # normalized list
    if isinstance(props, list) and props and isinstance(props[0], dict) and "iri" in props[0]:
        for p in props:
            iri   = p.get("iri")
            ptype = p.get("type")
            dom   = p.get("domain")
            rng   = p.get("range")
            if iri:
                prop_map[iri] = {"type": ptype, "domain": dom, "range": rng}
        return prop_map

    # raw SPARQL JSON
    if isinstance(props, dict) and "results" in props:
        for b in props.get("results", {}).get("bindings", []):
            iri   = b.get("p", {}).get("value")
            ptype = b.get("type", {}).get("value")
            dom   = b.get("domain", {}).get("value") if "domain" in b else None
            rng   = b.get("range", {}).get("value")  if "range"  in b else None
            if iri:
                prop_map[iri] = {"type": ptype, "domain": dom, "range": rng}
        return prop_map

    return prop_map

@tool(
    name="check_schema",
    description="Validate triple patterns against domain/range from schema. Returns ok plus issues list.",
    permission=ToolPermission.ADMIN
)
def check_schema(ontology_schema: Dict[str, Any], triples: List[List[str]]) -> Dict[str, Any]:
    """
    :param ontology_schema: output of get_schema (normalized or raw SPARQL JSON)
    :param triples: list of triples [[s,p,o], ...] to validate
    :return: {"ok": bool, "issues": [ {level, code, message, triple} , ... ]}
    """
    issues: List[Dict[str, Any]] = []

    # normalize triples
    tlist: List[Tuple[str,str,str]] = []
    if isinstance(triples, (list, tuple)):
        for t in triples:
            nt = _normalize_triple(t)
            if nt: tlist.append(nt)
            else:
                issues.append({"level":"warn","code":"bad_triple","message":"Malformed triple skipped", "triple": str(t)})

    # properties map
    props = _load_properties(ontology_schema)

    # rdf:type facts from provided triples
    types = _extract_types(tlist)

    # validate
    for s,p,o in tlist:
        meta = props.get(p)
        if not meta:
            issues.append({"level":"error","code":"unknown_predicate","message":"Predicate not found in schema", "triple":[s,p,o]})
            continue

        dom = meta.get("domain")
        rng = meta.get("range")

        if dom and s in types and dom not in types[s]:
            issues.append({"level":"warn","code":"domain_mismatch_possible","message":f"Subject types {list(types[s])} do not include domain {dom}", "triple":[s,p,o]})

        if rng:
            if rng.startswith(XSD_NS):
                if not _is_literal(o) or not _parse_xsd(o, rng):
                    issues.append({"level":"warn","code":"datatype_mismatch","message":f"Object literal not matching {rng}", "triple":[s,p,o]})
            else:
                if o in types and rng not in types[o]:
                    issues.append({"level":"warn","code":"range_mismatch_possible","message":f"Object types {list(types[o])} do not include range {rng}", "triple":[s,p,o]})

    ok = not any(i for i in issues if i["level"] == "error")
    return {"ok": ok, "issues": issues}
