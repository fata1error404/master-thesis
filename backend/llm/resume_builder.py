import json
from pathlib import Path
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from prompts.prompt_4_resume_tailoring import WORK_EXPERIENCE, EDUCATION, SKILLS, PROJECTS, CERTIFICATIONS, ACHIEVEMENTS
from schemas.resume_schema import Resume, Experience, Education, SkillSection, Project, Certification, Achievement


SECTION_SPECS = {
    "work_experience_section": (WORK_EXPERIENCE, Experience),
    "projects_section": (PROJECTS, Project),
    "skills_section": (SKILLS, SkillSection),
    "education_section": (EDUCATION, Education),
    "certifications_section": (CERTIFICATIONS, Certification),
    "achievements_section": (ACHIEVEMENTS, Achievement)
}

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def build_resume(
    job_details: Dict[str, Any],
    resume_data: Dict[str, Any],
    resume_file_id: str,
    output_dir: str
) -> Dict[str, Any]:

    # append static fields from input resume
    tailored_resume = {
        "name": resume_data["name"],
        "summary": resume_data.get("summary"),  # optional field in schema
        "phone": resume_data["phone"],
        "email": resume_data["email"],
        "media": {
            "linkedin": resume_data["media"].get("linkedin"),
            "github": resume_data["media"].get("github"),
            "medium": resume_data["media"].get("medium"),
            "devpost": resume_data["media"].get("devpost"),
        },
        "work_experience_section": [],
        "education_section": [],
        "skills_section": [],
        "projects_section": [],
        "certifications_section": [],
        "achievements_section": []
    }

    # iterate over each section from input resume and generate its tailored version 
    for section_key, (section_prompt, section_model) in SECTION_SPECS.items():

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You tailor resume sections for a job application."),
            ("human", section_prompt),
        ])

        structured_llm = llm.with_structured_output(
            section_model, 
            method="function_calling"
        )

        chain = prompt | structured_llm

        try:
            response = chain.invoke({
                "section_data": json.dumps(resume_data[section_key], ensure_ascii=False),
                "job_description": json.dumps(job_details, ensure_ascii=False),
            })

        except Exception as e:
            print(f"Error generating {section_key}: {e}")
            response = None

        if response is None:
            tailored_resume[section_key] = []
            continue

        data = response.model_dump(mode="json")
        tailored_resume[section_key] = [data]

    # validate the result (force convert to Resume object and back to JSON dictionary)
    validated_resume = Resume(**tailored_resume).model_dump(mode="json")

    # save to JSON
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "resume_tailored.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(validated_resume, f, indent=2, ensure_ascii=False)

    return validated_resume