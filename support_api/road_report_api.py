# road_report_api.py
import os, math, json, re, uuid, time
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import requests
import pandas as pd
from shapely import wkt as shapely_wkt
from shapely.geometry import shape as shapely_shape, LineString, MultiLineString, Polygon, MultiPolygon
from shapely.ops import transform as shp_transform
from pyproj import CRS, Transformer
import matplotlib
matplotlib.use("Agg")              # headless-safe
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ---------- Config (env) ----------
SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://localhost:8111/query")  # proxy JSON or direct /sparql
USE_PROXY_JSON  = SPARQL_ENDPOINT.endswith("/query")
DEFAULT_EPSG    = int(os.getenv("DEFAULT_EPSG", "32644"))  # India UTM 44N
API_KEY         = os.getenv("ROAD_API_KEY", "")            # set to a non-empty string for auth
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")         # e.g., https://abcd1234.ngrok-free.app

# Output dir exposed at /files
REPORT_DIR = Path(os.getenv("REPORT_DIR", "./reports")).absolute()
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- FastAPI ----------
app = FastAPI(title="RoadSegment Report API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.mount("/files", StaticFiles(directory=str(REPORT_DIR)), name="files")

PREFIXES = """
PREFIX adto: <http://www.projectsynapse.com/ontologies/adto#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo:  <http://www.opengis.net/ont/geosparql#>
"""

class ReportRequest(BaseModel):
    buffer_meters: float = 5.0

def _auth_or_403(x_api_key: Optional[str]):
    if API_KEY and (x_api_key or "") != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

# ---------- SPARQL ----------
def sparql_select(query: str) -> pd.DataFrame:
    if USE_PROXY_JSON:
        r = requests.post(
            SPARQL_ENDPOINT,
            headers={"Content-Type": "application/json"},
            json={"query": PREFIXES + query},
            timeout=120,
        )
    else:
        r = requests.post(
            SPARQL_ENDPOINT,
            headers={"Accept":"application/sparql-results+json",
                     "Content-Type":"application/sparql-query"},
            data=(PREFIXES + query).encode("utf-8"),
            timeout=120,
        )
    r.raise_for_status()
    data = r.json()
    rows = [{k:v.get("value") for k,v in b.items()} for b in data.get("results",{}).get("bindings",[])]
    return pd.DataFrame(rows)

def fetch_roadsegments() -> pd.DataFrame:
    q = """
    SELECT ?s ?name ?status
           (COALESCE(?wkt_geo, ?wkt_adto)    AS ?wkt)
           (COALESCE(?gj_geom, ?gj_subject)  AS ?geojson)
    WHERE {
      ?s a adto:RoadSegment .
      OPTIONAL { ?s adto:hasName ?name }
      OPTIONAL { ?s adto:hasStatus ?status }

      OPTIONAL {
        ?s (geo:hasGeometry|adto:hasGeometry) ?g .
        OPTIONAL { ?g geo:asWKT  ?wkt_geo }
        OPTIONAL { ?g adto:asWKT ?wkt_adto }
      }
      OPTIONAL {
        ?s (geo:hasGeometry|adto:hasGeometry) ?g2 .
        OPTIONAL { ?g2 adto:asGeoJSON ?gj_geom }   # change if your predicate name differs
      }
      OPTIONAL { ?s adto:asGeoJSON ?gj_subject }
    }
    ORDER BY ?s
    """
    df = sparql_select(q)
    if not df.empty:
        df = df.rename(columns={"s":"iri"})
    for col in ("iri","name","status","wkt","geojson"):
        if col not in df.columns:
            df[col] = pd.NA
    return df

# ---------- Geometry ----------
def _clean_wkt(s: str) -> str:
    if not s: return s
    s2 = str(s).strip()
    if s2.upper().startswith("SRID=") and ";" in s2:
        s2 = s2.split(";",1)[1].strip()
    m = re.match(r"^<[^>]+>\s*(.*)$", s2)  # drop leading <...CRS...>
    if m: s2 = m.group(1).strip()
    return s2

def _geom_from_literals(wkt_str: Optional[str], geojson_str: Optional[str]):
    # WKT first
    if wkt_str:
        try:
            return shapely_wkt.loads(_clean_wkt(wkt_str))
        except Exception:
            pass
    # GeoJSON fallback
    if geojson_str:
        try:
            gj = json.loads(geojson_str)
            if isinstance(gj, dict) and gj.get("type") == "Feature":
                gj = gj.get("geometry")
            return shapely_shape(gj) if gj else None
        except Exception:
            pass
    return None

def _utm_epsg_for_lonlat(lon: float, lat: float) -> int:
    zone = int(math.floor((lon + 180) / 6) + 1)
    return 32600 + zone if lat >= 0 else 32700 + zone

def project_to_meters(df: pd.DataFrame, default_epsg: Optional[int] = DEFAULT_EPSG):
    df = df.copy()
    for col in ("wkt","geojson"):
        if col not in df.columns:
            df[col] = pd.Series([None]*len(df), dtype="object")
    df["geom"] = [ _geom_from_literals(w,g) for w,g in zip(df["wkt"], df["geojson"]) ]
    df["geom_m"] = pd.Series([None]*len(df), dtype="object")

    valid = df["geom"].dropna()
    if valid.empty:
        return df, CRS.from_epsg(default_epsg or 4326)

    lons = [g.centroid.x for g in valid]
    lats = [g.centroid.y for g in valid]
    mean_lon = sum(lons)/len(lons)
    mean_lat = sum(lats)/len(lats)

    epsg = default_epsg or _utm_epsg_for_lonlat(mean_lon, mean_lat)
    crs_m = CRS.from_epsg(epsg)

    transformer = Transformer.from_crs("EPSG:4326", crs_m, always_xy=True)
    def _proj(g):
        return shp_transform(lambda x,y, z=None: transformer.transform(x,y), g)

    df.loc[valid.index, "geom_m"] = [ _proj(g) for g in valid ]
    return df, crs_m

def length_m(g):
    if g is None: return 0.0
    if isinstance(g, (LineString, MultiLineString)):
        return g.length
    if isinstance(g, (Polygon, MultiPolygon)):
        return g.length
    return 0.0

# ---------- Report ----------
def build_roadsegment_report(out_pdf: Path, buffer_meters: float = 5.0) -> Path:
    roads = fetch_roadsegments()
    roads_p, crs_m = project_to_meters(roads, DEFAULT_EPSG)
    roads_p["length_m"] = roads_p["geom_m"].map(length_m)

    with PdfPages(str(out_pdf)) as pdf:
        # Page 1 — summary
        fig = plt.figure(figsize=(8.5, 11)); ax = fig.add_subplot(111); ax.axis("off")
        ax.text(0.02, 0.95, "RoadSegment Length Report", fontsize=18, weight="bold")
        ax.text(0.02, 0.91, f"Projected CRS: {crs_m.to_string()}", fontsize=10)
        ax.text(0.02, 0.88, f"Segments: {len(roads_p)}", fontsize=10)
        ax.text(0.02, 0.85, f"Total length: {roads_p['length_m'].sum():,.0f} m", fontsize=10)
        pdf.savefig(fig); plt.close(fig)

        # Page 2 — histogram
        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_subplot(111)
        ax.set_title("Road segment lengths (m)")
        roads_p["length_m"].plot(kind="hist", bins=24, ax=ax)
        ax.set_xlabel("meters"); ax.set_ylabel("count")
        pdf.savefig(fig); plt.close(fig)

        # Page 3 — top table
        fig = plt.figure(figsize=(8.5, 11)); ax = fig.add_subplot(111); ax.axis("off")
        ax.set_title("Top segments by length (m)")
        top = roads_p[["iri","name","status","length_m"]]\
              .sort_values("length_m", ascending=False).head(20).copy()
        top["length_m"] = top["length_m"].map(lambda v: f"{v:,.0f}")
        table = ax.table(cellText=top.values, colLabels=list(top.columns),
                         loc="upper left", colLoc="left", cellLoc="left")
        table.auto_set_font_size(False); table.set_fontsize(8); table.scale(1, 1.2)
        pdf.savefig(fig); plt.close(fig)

        # Page 4 — quick map
        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_subplot(111)
        ax.set_title("Road segments (projected meters)")
        for g in roads_p["geom_m"].dropna().head(1000):
            try:
                if isinstance(g, LineString):
                    x, y = g.xy; ax.plot(x, y, linewidth=0.6)
                elif isinstance(g, MultiLineString):
                    for part in g.geoms:
                        x, y = part.xy; ax.plot(x, y, linewidth=0.6)
            except Exception:
                pass
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
        pdf.savefig(fig); plt.close(fig)

    if not out_pdf.exists():
        raise RuntimeError("PDF was not written")
    return out_pdf

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/reports/roadsegments")
def create_road_report(body: ReportRequest, request: Request, x_api_key: Optional[str] = Header(None)):
    _auth_or_403(x_api_key)

    # unique file
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = f"roadsegment_report_{ts}_{uuid.uuid4().hex[:6]}.pdf"
    fpath = REPORT_DIR / fname

    try:
        build_roadsegment_report(fpath, buffer_meters=body.buffer_meters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    # public link
    base = (PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else str(request.base_url).rstrip("/"))
    url = f"{base}/files/{fname}"

    size = fpath.stat().st_size if fpath.exists() else 0
    return {
        "status": "ok",
        "file_name": fname,
        "size_bytes": size,
        "url": url
    }
