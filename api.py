import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from rag_pipeline import ApiResponse, answer, search

load_dotenv()


app = FastAPI(
    title="Compliance Intelligence API",
    description="Query CIS benchmark controls and get structured, actionable remediation guidance.",
    version="0.1.0",
)


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


API_KEYS = set(filter(None, os.environ.get("API_KEYS", "").split(",")))

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def require_api_key(key: str | None = Security(api_key_header)) -> str:
    if key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key

class RemediateRequest(BaseModel):
    question: str = Field(
        min_length=5,
        max_length=500,
        description="A question about a CIS benchmark control, e.g. 'How do I secure world-writable directories?'",
    )

@app.post("/api/v1/remediate", response_model=ApiResponse)
@limiter.limit("10/minute")
def remediate(request: Request, payload: RemediateRequest, api_key: str = Depends(require_api_key)) -> ApiResponse:
    return answer(payload.question)



class SearchResult(BaseModel):
    control_id: str
    benchmark: str
    title: str
    profile_applicability: str | None
    distance: float = Field(description="Semantic distance — lower means more similar")


@app.get("/api/v1/search", response_model=list[SearchResult])
@limiter.limit("30/minute")
def search_controls(
    request: Request,
    q: str = Query(min_length=2, max_length=200, description="What to search for"),
    k: int = Query(default=5, ge=1, le=20, description="How many results (1-20)"),
    api_key: str = Depends(require_api_key),
) -> list[SearchResult]:
    return search(q, k)