from pypdf import PdfReader

reader = PdfReader("data/raw/CIS_Amazon_Linux_2_Benchmark_v4.0.0.pdf")

print(f"Total pages: {len(reader.pages)}")

page_number = 14
text = reader.pages[page_number].extract_text()
print(f"--- Page {page_number}")
print(text)
