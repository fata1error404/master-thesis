import json
import re
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from schemas.resume_schema import Resume

# [TODO] annotation

class BulletValidityScores(BaseModel):
    scores: List[int] = Field(
        description="One score per bullet: 1 if it is a valid atomic XYZ-style resume claim, otherwise 0."
    )


def _resume_bullets(resume_data: Dict[str, Any]) -> List[str]:
    resume = Resume(**resume_data)
    bullets: List[str] = []

    for experience in resume.work_experience_section:
        bullets.extend(experience.description)

    for project in resume.projects_section:
        bullets.extend(project.description)

    return [bullet for bullet in bullets if bullet.strip()]


def _heuristic_structural_validity(bullets: List[str]) -> Dict[str, Any]:
    scores: List[int] = []

    action_pattern = re.compile(
        r"^\s*(built|created|developed|designed|implemented|engineered|led|improved|optimized|automated|"
        r"managed|analyzed|delivered|launched|integrated|reduced|increased|enhanced|streamlined|"
        r"collaborated|initiated|architected|trained|deployed|maintained|migrated|refactored)\b",
        re.IGNORECASE,
    )
    method_pattern = re.compile(r"\b(by|using|with|through|via|leveraging|utilizing)\b", re.IGNORECASE)
    outcome_pattern = re.compile(
        r"(\d+%|\d+x|\$\d+|\b(reduced|increased|improved|achieved|resulting|saved|accelerated|boosted|cut|grew)\b)",
        re.IGNORECASE,
    )

    for bullet in bullets:
        has_action = bool(action_pattern.search(bullet))
        has_method = bool(method_pattern.search(bullet))
        has_outcome = bool(outcome_pattern.search(bullet))
        scores.append(1 if has_action and has_method and has_outcome else 0)

    valid_count = sum(scores)
    structural_validity = valid_count / len(scores) if scores else 1.0

    return {
        "structural_validity": structural_validity,
        "valid_count": valid_count,
        "bullet_count": len(scores),
        "bullet_scores": scores,
        "used_fallback": True,
    }


def compute_structural_validity(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    bullets = _resume_bullets(resume_data)

    if not bullets:
        return {
            "structural_validity": 1.0,
            "valid_count": 0,
            "bullet_count": 0,
            "bullet_scores": [],
            "used_fallback": False,
        }

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You evaluate resume bullet structure. Return one binary score per bullet.",
            ),
            (
                "human",
                (
                    "A valid bullet is an atomic resume claim that follows the XYZ idea: "
                    "one clear action, a method/tool/context, and an outcome or impact. "
                    "It should not combine unrelated claims.\n\n"
                    "Resume bullets:\n{bullets}\n\n"
                    "Return 1 for each valid atomic XYZ-style claim, otherwise 0."
                ),
            ),
        ]
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm.with_structured_output(BulletValidityScores)

    try:
        response = chain.invoke({"bullets": json.dumps(bullets, ensure_ascii=False)})
        scores = [1 if int(score) == 1 else 0 for score in response.scores[: len(bullets)]]

        if len(scores) != len(bullets):
            return _heuristic_structural_validity(bullets)

        valid_count = sum(scores)
        return {
            "structural_validity": valid_count / len(scores),
            "valid_count": valid_count,
            "bullet_count": len(scores),
            "bullet_scores": scores,
            "used_fallback": False,
        }
    except Exception:
        return _heuristic_structural_validity(bullets)
