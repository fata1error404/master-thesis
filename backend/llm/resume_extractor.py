import re
import json
import fitz
from pathlib import Path
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from prompts.prompt_3_resume_extraction import RESUME_DETAILS_EXTRACTOR
from schemas.resume_schema import Resume

llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You extract structured resume details from resume text."),
    ("human", RESUME_DETAILS_EXTRACTOR),
])

structured_llm = llm.with_structured_output(
    Resume,
    method="function_calling"
)


def extract_resume(
    resume_file_id: str, 
    output_dir: str
) -> Dict[str, Any]:
    
    resume_path = Path(output_dir) / f"{resume_file_id}.pdf"

    if not resume_path.exists():
        raise FileNotFoundError(f"Resume PDF file not found: {resume_path}")
    
    doc = fitz.open(resume_path)
    pages_text = []

    for page in doc:
        text = page.get_text()
        pages_text.append(text)

    resume_text = "\n\n".join(pages_text).strip()
    resume_text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", resume_text)
    resume_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]+", " ", resume_text)
    # resume_text = re.sub(r"[^\x00-\x7F]+", " ", resume_text)

    lines = resume_text.split("\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]

    resume_text = "\n".join(lines)

    # print(resume_text)
    # Path("outputs/resume.txt").write_text(resume_text, encoding="utf-8")

    chain = prompt | structured_llm

    result = chain.invoke({"resume_text": resume_text})

    # print(result.model_dump_json(indent=2))

    data = json.loads(result.model_dump_json())

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "resume.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data