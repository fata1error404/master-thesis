import re
import json
import fitz
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

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


MISSING_STRINGS = {
    "",
    "unknown",
    "n/a",
    "na",
    "none",
    "not specified",
    "not provided",
    "unspecified",
}


def _is_missing_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in MISSING_STRINGS


def _clean_missing_strings(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: _clean_missing_strings(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_clean_missing_strings(value) for value in obj]
    if _is_missing_string(obj):
        return ""
    return obj


def _blank_suspicious_work_locations(data: Dict[str, Any]) -> None:
    experiences = data.get("work_experience_section") or []
    if not isinstance(experiences, list):
        return

    locations: List[str] = []
    for exp in experiences:
        if not isinstance(exp, dict):
            continue
        location = exp.get("location")
        if isinstance(location, str) and location.strip():
            locations.append(location.strip())

    location_counts = Counter(locations)
    repeated_locations = {
        location
        for location, count in location_counts.items()
        if count >= 2
    }

    education_text = " ".join(
        " ".join(str(value) for value in edu.values() if value)
        for edu in data.get("education_section", []) or []
        if isinstance(edu, dict)
    ).lower()

    for exp in experiences:
        if not isinstance(exp, dict):
            continue

        location = exp.get("location")
        if not isinstance(location, str) or not location.strip():
            exp["location"] = ""
            continue

        normalized = location.strip().lower()
        if location.strip() in repeated_locations or normalized in education_text:
            exp["location"] = ""


def _education_evidence_blocks(resume_text: str) -> Dict[str, Dict[str, Any]]:
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    evidence: Dict[str, Dict[str, Any]] = {}

    start = 0
    end = len(lines)
    for index, line in enumerate(lines):
        if line.upper() == "EDUCATION":
            start = index + 1
        elif start and line.upper() in {"WORK EXPERIENCE", "SELECTED PROJECTS", "PROJECTS", "TECHNICAL SKILLS"}:
            end = index
            break

    education_lines = lines[start:end]
    university_indices = [
        index
        for index, line in enumerate(education_lines)
        if "university" in line.lower() or "institute" in line.lower()
    ]

    for position, index in enumerate(university_indices):
        line = education_lines[index]
        next_index = university_indices[position + 1] if position + 1 < len(university_indices) else len(education_lines)
        block_lines = education_lines[index + 1 : next_index]
        if not block_lines:
            continue

        block = evidence.setdefault(
            line.lower(),
            {
                "university": line,
                "degree": None,
                "department": None,
                "grade": None,
                "highlights": [],
            },
        )

        for candidate in block_lines:
            lowered = candidate.lower()
            if lowered.startswith(("department of", "faculty of", "school of", "college of")):
                block["department"] = candidate
            if lowered.startswith(("diploma:", "degree:", "thesis:")):
                block["degree"] = candidate.rstrip(".")
            if "gpa" in lowered:
                grade = re.sub(r"^gpa\s*:\s*", "", candidate, flags=re.IGNORECASE).strip(" ;")
                if grade:
                    block["grade"] = grade
            if "ranked" in lowered:
                highlight = candidate.strip("()")
                if highlight and highlight not in block["highlights"]:
                    block["highlights"].append(highlight)

    return evidence


def _best_education_evidence(university: str, evidence: Dict[str, Dict[str, Any]]) -> Dict[str, Any] | None:
    normalized_university = university.strip().lower()
    if not normalized_university:
        return None

    for key, block in evidence.items():
        if normalized_university in key or key in normalized_university:
            return block

    return None


def _repair_education_from_evidence(data: Dict[str, Any], resume_text: str) -> None:
    evidence = _education_evidence_blocks(resume_text)
    educations = data.get("education_section") or []
    if not isinstance(educations, list):
        return

    for edu in educations:
        if not isinstance(edu, dict):
            continue

        university = str(edu.get("university") or "")
        block = _best_education_evidence(university, evidence)

        if block:
            if (
                _is_missing_string(edu.get("degree"))
                or str(edu.get("degree") or "").strip().lower() in {"diploma", "degree", "thesis"}
            ) and block.get("degree"):
                edu["degree"] = block["degree"]
            if _is_missing_string(edu.get("department")) and block.get("department"):
                edu["department"] = block["department"]
            if _is_missing_string(edu.get("grade")) and block.get("grade"):
                edu["grade"] = block["grade"]

            edu["highlights"] = list(block.get("highlights") or [])

        if "department" not in edu:
            edu["department"] = None
        if "grade" not in edu:
            edu["grade"] = None
        if "highlights" not in edu:
            edu["highlights"] = []


def _sanitize_education_highlights(data: Dict[str, Any]) -> None:
    educations = data.get("education_section") or []
    if not isinstance(educations, list):
        return

    for edu in educations:
        if not isinstance(edu, dict):
            continue

        university = str(edu.get("university") or "").lower()
        highlights = edu.get("highlights")
        if not isinstance(highlights, list):
            edu["highlights"] = []
            continue

        cleaned = []
        for highlight in highlights:
            text = str(highlight)
            lowered = text.lower()
            if "ranked" in lowered:
                if "china" in lowered and "tsinghua" not in university:
                    continue
                if "russia" in lowered and "moscow" not in university:
                    continue
            cleaned.append(text)

        edu["highlights"] = cleaned


def _sanitize_education_degrees(data: Dict[str, Any]) -> None:
    educations = data.get("education_section") or []
    if not isinstance(educations, list):
        return

    generic_degree_labels = {
        "master",
        "masters",
        "master's",
        "master’s",
        "master student",
        "masters student",
        "master's student",
        "master’s student",
        "student",
    }

    for edu in educations:
        if not isinstance(edu, dict):
            continue

        degree = edu.get("degree")
        department = edu.get("department")
        if not isinstance(degree, str) or not degree.strip():
            continue
        if not isinstance(department, str) or not department.strip():
            continue

        normalized = re.sub(r"\s+", " ", degree.strip().lower())
        if normalized in generic_degree_labels:
            edu["degree"] = ""


def _canonical_claim(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9+#./-]+", " ", text.lower())
    normalized = normalized.replace("$", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _claim_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#]+", text.lower())
        if len(token) >= 3
    }


def _claim_number_signatures(text: str) -> set[str]:
    signatures = set()
    for match in re.findall(r"(?:\$|%|x)?\d[\d,.$%x+]*", text):
        digits = re.sub(r"\D", "", match)
        if digits:
            signatures.add(digits)
    return signatures


def _achievement_exists_elsewhere(achievement: str, other_text: str, other_canonical: str) -> bool:
    canonical = _canonical_claim(achievement)
    if canonical and canonical in other_canonical:
        return True

    achievement_numbers = _claim_number_signatures(achievement)
    other_numbers = _claim_number_signatures(other_text)
    if achievement_numbers and achievement_numbers.issubset(other_numbers):
        achievement_tokens = _claim_tokens(achievement)
        other_tokens = _claim_tokens(other_text)
        if len(achievement_tokens & other_tokens) >= min(3, len(achievement_tokens)):
            return True

    achievement_lower = achievement.lower()
    if any(word in achievement_lower for word in ("hackathon", "prize", "winner", "competition", "foundation")):
        achievement_tokens = _claim_tokens(achievement)
        other_tokens = _claim_tokens(other_text)
        if len(achievement_tokens & other_tokens) >= 4:
            return True

    return False


def _dedupe_achievements(data: Dict[str, Any]) -> None:
    other_text = " ".join(
        str(part)
        for key in (
            "work_experience_section",
            "projects_section",
            "education_section",
            "certifications_section",
        )
        for part in _text_values(data.get(key))
    )
    other_canonical = _canonical_claim(other_text)

    filtered = []
    seen = set()
    for achievement in data.get("achievements_section", []) or []:
        if not isinstance(achievement, dict):
            continue

        name = str(achievement.get("name") or "").strip()
        canonical = _canonical_claim(name)
        if not canonical or canonical in seen:
            continue
        if _achievement_exists_elsewhere(name, other_text, other_canonical):
            continue

        filtered.append(achievement)
        seen.add(canonical)

    data["achievements_section"] = filtered


def _text_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(_text_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return [str(value)]


def postprocess_extracted_resume(data: Dict[str, Any], resume_text: str = "") -> Dict[str, Any]:
    data = _clean_missing_strings(data)
    _blank_suspicious_work_locations(data)
    _repair_education_from_evidence(data, resume_text)
    _sanitize_education_highlights(data)
    _sanitize_education_degrees(data)
    _dedupe_achievements(data)
    return data


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
    data = postprocess_extracted_resume(data, resume_text)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "resume.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data
