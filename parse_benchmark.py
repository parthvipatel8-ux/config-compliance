import re
import json 
from pypdf import PdfReader
from pathlib import Path

reader = PdfReader("data/raw/CIS_Amazon_Linux_2_Benchmark_v4.0.0.pdf")

full_text = "\n".join(page.extract_text() for page in reader.pages)

full_text = re.sub(r"^Page \d+ *$", "", full_text, flags=re.MULTILINE)

# Match any dotted-number heading, not just "Ensure ..." titles
heading_pattern = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$", flags=re.MULTILINE)

# Slice at EVERY candidate heading, then validate each slice by its own
# contents — a real control's chunk contains its Profile Applicability
candidates = list(heading_pattern.finditer(full_text))

controls = []
chunks = []
for i, match in enumerate(candidates):
    start = match.start()
    end = candidates[i + 1].start() if i + 1 < len(candidates) else len(full_text)
    chunk = full_text[start:end]
    if "Profile Applicability" in chunk:
        # Title = everything between the ID and "Profile Applicability",
        # with wrapped-line whitespace collapsed to single spaces
        title_text = chunk[len(match.group(1)):chunk.index("Profile Applicability")]
        controls.append({"id": match.group(1), "title": " ".join(title_text.split())})
        chunks.append(chunk)
    elif chunks:
        # Impostor heading (mapping-table row) — this text is the tail of
        # the previous control's chunk, so glue it back on
        chunks[-1] += chunk


# Split each chunk into its named sections
SECTION_NAMES = [
    "Profile Applicability", "Description", "Rationale", "Impact",
    "Audit", "Remediation", "Default Value", "References",
    "Additional Information", "CIS Controls",
]
section_pattern = re.compile(
    r"^(" + "|".join(SECTION_NAMES) + r"): *$", flags=re.MULTILINE
)

records = []
for control, chunk in zip(controls, chunks):
    parts = section_pattern.split(chunk)
    # parts alternates: [text-before-first-section, name, body, name, body, ...]
    sections = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        sections[name] = body.strip()
    records.append({
        "benchmark": "CIS Amazon Linux 2 v4.0.0",
        "control_id": control["id"],
        "title": control["title"],
        "sections": sections,
    })

Path("data/processed").mkdir(parents=True, exist_ok=True)
with open("data/processed/controls.json", "w") as f:
    json.dump(records, f, indent=2)

print(f"Wrote {len(records)} controls to data/processed/controls.json")

# Quality report: which sections are missing where?
for name in SECTION_NAMES:
    missing = sum(1 for r in records if name not in r["sections"])
    print(f"  {name}: missing in {missing} controls")

# for record, chunk in zip(records, chunks):
#     if "Remediation" not in record["sections"]:
#         print(record["control_id"], record["title"])
#         print(repr(chunk[:800]))
#         break
