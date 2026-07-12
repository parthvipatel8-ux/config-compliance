from fastapi import FastAPI
from pydantic import BaseModel, Field
from rag_pipeline import answer, ApiResponse


app = FastAPI(
    title="Compliance Intelligence API",
    description="Query CIS benchmark controls and get structured, actionable remediation guidance.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

class RemediateRequest(BaseModel):
    question: str = Field(
        min_length=5,
        max_length=500,
        description="A question about a CIS benchmark control, e.g. 'How do I secure world-writable directories?'",
    )

@app.post("/api/v1/remediate", response_model=ApiResponse)
def remediate(request: RemediateRequest) -> ApiResponse:
    return answer(request.question)