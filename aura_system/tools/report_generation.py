from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import requests

ROAD_REPORT_API = "https://2e5b79924ef6.ngrok-free.app"  # <-- string in quotes

@tool(
    name="get_roadsegment_report_link",
    description="Generate the RoadSegment length PDF and return a public URL.",
    permission=ToolPermission.READ_ONLY  # READ_ONLY is sufficient
)
def get_roadsegment_report_link() -> dict:
    """Calls POST /report on the road report API and returns the link."""
    try:
        r = requests.post(f"{ROAD_REPORT_API}/report", timeout=180)
        if r.status_code >= 400:
            return {"status": "error", "detail": r.text}
        data = r.json()
        return {"status": "ok", "url": data.get("url")}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
