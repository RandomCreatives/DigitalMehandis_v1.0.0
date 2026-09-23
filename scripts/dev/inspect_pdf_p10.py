import pdfplumber
import os

path = "data/rates/Page 10.pdf"
if os.path.exists(path):
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
        print(text[:1000])
else:
    print(f"File {path} not found")
