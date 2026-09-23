import pdfplumber
import os

path = "data/rates/Page 1.pdf"
if os.path.exists(path):
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
        print("--- Text Content ---")
        print(text[:1000])
        print("\n--- Tables Found ---")
        tables = page.extract_tables()
        for i, table in enumerate(tables):
            print(f"Table {i}:")
            for row in table[:5]:
                print(row)
else:
    print(f"File {path} not found")
