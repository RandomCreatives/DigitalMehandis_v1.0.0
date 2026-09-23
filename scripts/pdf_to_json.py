import asyncio
import json
import sys
import os
from pathlib import Path
from uuid import uuid4

# Add backend to sys.path to allow imports
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.modules.cad.extraction import ExtractionService

async def convert(pdf_path: str, output_path: str):
    print(f"Converting {pdf_path}...")
    project_id = uuid4()
    drawing_id = uuid4()

    # ExtractionService.extract_from_drawing is async
    # is_dxf=False for PDF
    result = await ExtractionService.extract_from_drawing(
        project_id=project_id,
        drawing_id=drawing_id,
        file_path=pdf_path,
        discipline="ARCHITECTURAL", # Default
        is_dxf=False
    )

    # Format the results into a clean JSON
    output_data = {
        "project_id": str(project_id),
        "drawing_id": str(drawing_id),
        "source_file": pdf_path,
        "suggestions": [
            {
                "discipline": s.discipline,
                "category": s.element_category,
                "description": s.description,
                "value": s.value,
                "unit": s.unit,
                "moudc_code": s.moudc_code,
                "confidence": s.confidence
            } for s in result["suggestions"]
        ],
        "canvas_json": result["canvas_json"]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    print(f"Done! Result saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/pdf_to_json.py <input_pdf> [output_json]")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 else input_pdf.replace(".pdf", ".json")

    asyncio.run(convert(input_pdf, output_json))
