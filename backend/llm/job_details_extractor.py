import json
from pathlib import Path
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from prompts.prompt_2_job_details_extraction import JOB_DETAILS_EXTRACTOR
from schemas.job_details_schema import JobDetails

# initialize OpenAI LLM (temperature = 0 ensures deterministic output, which is important for structured extraction)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# prompt definition: system message defines the role of the model (instruction about identity + behavior), while human message provides the task itself – <task> pre-defined prompt + input placeholder <job_description>
prompt = ChatPromptTemplate.from_messages([
    ("system", "You extract structured job details from job description text."),
    ("human", JOB_DETAILS_EXTRACTOR),
])

# enforce the model to use structured output (pydantic schema job_details_schema.py) instead of free-form text
structured_llm = llm.with_structured_output(JobDetails)


def extract_job_details(
    job_description: str, 
    output_dir: str
) -> Dict[str, Any]:
    
    # combine prompt + structured output model into a single pipeline
    chain = prompt | structured_llm

    # run LLM inference with runtime input injected into the prompt
    result = chain.invoke({"job_description_text": job_description})

    # convert Pydantic model → Python dictionary
    data = result.model_dump()

    # save to JSON
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "job_details.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data