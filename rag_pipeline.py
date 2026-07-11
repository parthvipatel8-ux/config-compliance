import json
import os
from dotenv import load_dotenv
import anthropic
import chromadb

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
- Remediation steps must be copy-paste ready where possible."""


def retrieve(query: str, k: int = 3) -> list[dict]:
    results = collection.query(query_texts=[query], n_results=k)
    return [records[chroma_id] for chroma_id in results["ids"][0]]


def format_control(r: dict) -> str:
    s = r["sections"]
    return f"""<control id="{r['control_id']}" benchmark="{r['benchmark']}">
Title: {r['title']}
Description: {s.get('Description', 'N/A')}
Rationale: {s.get('Rationale', 'N/A')}
Audit: {s.get('Audit', 'N/A')}
Remediation: {s.get('Remediation', 'N/A')}
</control>"""


def answer(question: str) -> str:
    controls = retrieve(question)
    context = "\n\n".join(format_control(r) for r in controls)

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"<controls>\n{context}\n</controls>\n\nQuestion: {question}",
        }],
    )
    usage = response.usage
    print(f"[retrieved: {', '.join(r['control_id'] for r in controls)}] "
          f"[tokens in: {usage.input_tokens}, out: {usage.output_tokens}]\n")
    return response.content[0].text


if __name__ == "__main__":
    question = "How do I enforce password complexity on Windows Server 2019?"
    print(answer(question))