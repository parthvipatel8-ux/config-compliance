import json
import chromadb

with open("data/processed/controls.json") as f:
    records = json.load(f)

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_or_create_collection("cis_controls")

collection.add(
    # Prefix with benchmark so IDs stay unique when we add Ubuntu later
    ids=[f"{r['benchmark']}::{r['control_id']}" for r in records],
    documents=[
        f"{r['title']}\n{r['sections']['Description']}\n{r['sections']['Rationale']}"
        for r in records
    ],
    metadatas=[
        {"benchmark": r["benchmark"], "control_id": r["control_id"], "title": r["title"]}
        for r in records
    ],
)

print(f"Indexed {collection.count()} controls")

# The moment of truth: a semantic query with NO keyword overlap
results = collection.query(
    query_texts=["prevent users from running setuid programs in the audit log area"],
    n_results=3,
)
for control_id, distance in zip(results["ids"][0], results["distances"][0]):
    print(f"  {distance:.3f}  {control_id}")