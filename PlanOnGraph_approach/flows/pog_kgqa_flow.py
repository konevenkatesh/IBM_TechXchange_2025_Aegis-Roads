from ibm_watsonx_orchestrate.flow_builder.flows import Flow, flow, START, END
from pydantic import BaseModel, Field

# ---- Flow I/O ----
class PoGFlowInput(BaseModel):
    q: str = Field(description="User question")
    endpoint_url: str = Field(
        default="https://a2cbd7dc615f.ngrok-free.app/amaravati/sparql",
        description="Fuseki SPARQL endpoint"
    )

class PoGFlowOutput(BaseModel):
    result: str = Field(description="Final answer")

# ---- Flow ----
@flow(
    name="pog_kgqa_flow",
    description="Run the PoG orchestrator over ADTO to answer a question via SPARQL.",
    input_schema=PoGFlowInput,
    output_schema=PoGFlowOutput,
    # Optional: enable scheduling feature mentioned by the importer
    schedulable=True
)
def build_pog_kgqa_flow(aflow: Flow) -> Flow:
    """
    Single-step flow that invokes the `pog_orchestrator` agent.
    Input: { q, endpoint_url } → Output: { result }
    """
    run_pog = aflow.agent(
        name="run_pog_orchestrator",
        agent="pog_orchestrator",
        description="Run the full PoG pipeline over the KG and return the final answer.",
        message="Answer the question using the KG with PoG.",
        input_schema=PoGFlowInput,
        output_schema=PoGFlowOutput,
    )
    aflow.sequence(START, run_pog, END)
    return aflow
