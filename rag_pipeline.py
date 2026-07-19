import json
import os
from dotenv import load_dotenv
import anthropic
import chromadb
from pydantic import BaseModel, Field

load_dotenv()

client = anthropic.Anthropic()
chroma = chromadb.PersistentClient(path="data/chroma")
collection = chroma.get_collection("cis_controls")

# Source of truth: full records keyed the same way as the Chroma IDs
with open("data/processed/controls.json") as f:
    records = {f"{r['benchmark']}::{r['control_id']}": r for r in json.load(f)}

SYSTEM_PROMPT = """You are a compliance remediation assistant for security engineers.
You answer questions about CIS benchmark controls.

Rules:
- Answer ONLY from the CIS control text provided in <controls>. Do not use outside knowledge.
- Always cite the control ID and benchmark you are answering from.
- If none of the provided controls are relevant to the question, say exactly that
  and do not attempt an answer.
- You only see a few retrieved controls, never the whole benchmark. If the question
  requires counting, listing, or ranking across ALL controls (e.g. "how many...",
  "list all..."), state that this service answers questions about specific controls
  and cannot enumerate the full benchmark.
- Remediation steps must be copy-paste ready where possible."""

class RemediationResponse(BaseModel):
    relevant_control_found: bool = Field(
        description="False if none of the provided controls answer the question")
    control_id: str | None
    benchmark: str | None
    control_title: str | None
    rationale: str | None = Field(description="Why this control matters, in plain language")
    remediation_steps: list[str] = Field(
        description="Ordered, copy-paste-ready steps. Empty if no relevant control.")
    verification: str | None = Field(description="How to verify the fix, from the Audit section")
    estimated_effort_minutes: int | None

class ApiResponse(RemediationResponse):
    profile_applicability: str | None = None

def retrieve(query: str, k: int = 3) -> list[dict]:
    results = collection.query(query_texts=[query], n_results=k)
    return [records[chroma_id] for chroma_id in results["ids"][0]]

def search(query: str, k: int = 5) -> list[dict]:
    results = collection.query(query_texts=[query], n_results=k)
    return [
        {
            "control_id": records[chroma_id]["control_id"],
            "benchmark": records[chroma_id]["benchmark"],
            "title": records[chroma_id]["title"],
            "profile_applicability": records[chroma_id]["sections"].get("Profile Applicability"),
            "distance": round(distance, 4),
        }
        for chroma_id, distance in zip(results["ids"][0], results["distances"][0], strict=True)
    ]


def format_control(r: dict) -> str:
    s = r["sections"]
    return f"""<control id="{r['control_id']}" benchmark="{r['benchmark']}">
Title: {r['title']}
Description: {s.get('Description', 'N/A')}
Rationale: {s.get('Rationale', 'N/A')}
Audit: {s.get('Audit', 'N/A')}
Remediation: {s.get('Remediation', 'N/A')}
</control>"""


def answer(question: str) -> "ApiResponse":
    controls = retrieve(question)
    context = "\n\n".join(format_control(r) for r in controls)

    response = client.messages.parse(
        model="claude-sonnet-5",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"<controls>\n{context}\n</controls>\n\nQuestion: {question}",
        }],
        output_format=RemediationResponse,
    )
    usage = response.usage
    print(f"[retrieved: {', '.join(r['control_id'] for r in controls)}] "
          f"[tokens in: {usage.input_tokens}, out: {usage.output_tokens}]\n")
    result = ApiResponse(**response.parsed_output.model_dump())
    by_id = {r["control_id"]: r for r in controls}
    if result.control_id in by_id:
        result.profile_applicability = by_id[result.control_id]["sections"].get("Profile Applicability")
    return result


if __name__ == "__main__":
    import sys
    question = " ".join(sys.argv[1:]) or "How many controls are related to nosuid?"
    print(answer(question).model_dump_json(indent=2))