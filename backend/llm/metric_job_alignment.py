import json
import math
import re
from typing import Any, Dict, Iterable, List, Set, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field

from llm.knowledge_graph_builder import build_knowledge_graph
from schemas.job_details_schema import JobDetails
from schemas.knowledge_graph import KnowledgeGraph
from schemas.resume_schema import Resume


ALPHA = 0.45
BETA = 0.35
GAMMA = 0.20
LAMBDA = 0.10

SECTION_WEIGHTS = {
    "skills": 0.50,
    "work_experience": 0.25,
    "projects": 0.25,
}

JOB_SKILL_WEIGHTS = {
    "required_qualification": 0.6,
    "duty": 0.6,
    "keyword": 0.3,
    "preferred_qualification": 0.3,
    "domain": 0.1,
}

SENIORITY_LEVELS = {
    "intern": 0.20,
    "trainee": 0.25,
    "junior": 0.35,
    "entry": 0.35,
    "associate": 0.45,
    "mid": 0.55,
    "intermediate": 0.55,
    "senior": 0.75,
    "lead": 0.85,
    "staff": 0.90,
    "principal": 0.95,
    "manager": 0.85,
    "director": 1.00,
}


class BulletNoiseScores(BaseModel):
    scores: List[float] = Field(
        description="Noise probability for each bullet, where 0 means highly relevant and 1 means off-topic or padding."
    )


def _text_parts(values: Iterable[Any]) -> List[str]:
    parts: List[str] = []

    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                parts.append(text)
        elif isinstance(value, list):
            parts.extend(_text_parts(value))
        elif isinstance(value, dict):
            parts.extend(_text_parts(value.values()))
        else:
            text = str(value).strip()
            if text:
                parts.append(text)

    return parts


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def _node_label(node: Any) -> str:
    meta = node.meta or {}
    normalized_label = meta.get("normalized_label")
    if isinstance(normalized_label, str) and normalized_label.strip():
        return normalized_label.strip()
    return node.label.strip().lower()


def _canonical_resume_skills(graph: KnowledgeGraph) -> Set[str]:
    skills: Set[str] = set()

    for node in graph.nodes:
        if node.type != "canonical_skill":
            continue

        meta = node.meta or {}
        resume_mentions = int(meta.get("resume_mentions", 0) or 0)
        evidence_mentions = int(meta.get("evidence_mentions", 0) or 0)

        if resume_mentions > 0 or evidence_mentions > 0:
            skills.add(_node_label(node))

    return skills


def _job_skill_categories(graph: KnowledgeGraph) -> Dict[str, Set[str]]:
    node_by_id = {node.id: node for node in graph.nodes}
    categories: Dict[str, Set[str]] = {}

    for edge in graph.edges:
        if edge.relation != "canonicalizes_to":
            continue

        source = node_by_id.get(edge.source)
        target = node_by_id.get(edge.target)
        if not source or not target or target.type != "canonical_skill":
            continue

        source_meta = source.meta or {}
        if source_meta.get("kind") != "job_requirement":
            continue

        category = source_meta.get("category")
        skill_label = _node_label(target)

        if isinstance(category, str):
            categories.setdefault(skill_label, set()).add(category)

    return categories


def _job_skill_weight(categories: Set[str]) -> float:
    if not categories:
        return JOB_SKILL_WEIGHTS["domain"]

    return max(JOB_SKILL_WEIGHTS.get(category, JOB_SKILL_WEIGHTS["domain"]) for category in categories)


def _embedding_map(embeddings: OpenAIEmbeddings, labels: Iterable[str]) -> Dict[str, List[float]]:
    unique_labels = list(dict.fromkeys(label for label in labels if label))
    if not unique_labels:
        return {}

    vectors = embeddings.embed_documents(unique_labels)
    return dict(zip(unique_labels, vectors))


def _skill_alignment_score(
    graph: KnowledgeGraph,
    embeddings: OpenAIEmbeddings,
) -> Tuple[float, int, int]:
    job_categories = _job_skill_categories(graph)
    resume_skills = _canonical_resume_skills(graph)

    if not job_categories and not resume_skills:
        return 1.0, 0, 0
    if not job_categories or not resume_skills:
        return 0.0, len(job_categories), len(resume_skills)

    labels = set(job_categories.keys()) | resume_skills
    label_embeddings = _embedding_map(embeddings, labels)

    weighted_total = 0.0
    weight_sum = 0.0

    for job_skill, categories in job_categories.items():
        job_embedding = label_embeddings.get(job_skill)
        if not job_embedding:
            continue

        max_similarity = max(
            _cosine_similarity(job_embedding, label_embeddings[resume_skill])
            for resume_skill in resume_skills
            if resume_skill in label_embeddings
        )

        weight = _job_skill_weight(categories)
        weighted_total += weight * max_similarity
        weight_sum += weight

    if weight_sum == 0.0:
        return 0.0, len(job_categories), len(resume_skills)

    return weighted_total / weight_sum, len(job_categories), len(resume_skills)


def _job_text(job_details: Dict[str, Any]) -> str:
    return "\n".join(_text_parts(job_details.values()))


def _section_text(tailored_resume_data: Dict[str, Any], section_key: str) -> str:
    return "\n".join(_text_parts(tailored_resume_data.get(section_key, [])))


def _section_similarity_score(
    job_details: Dict[str, Any],
    tailored_resume_data: Dict[str, Any],
    embeddings: OpenAIEmbeddings,
) -> Dict[str, float]:
    job_embedding = embeddings.embed_query(_job_text(job_details))

    section_values = {
        "skills": _section_text(tailored_resume_data, "skills_section"),
        "work_experience": _section_text(tailored_resume_data, "work_experience_section"),
        "projects": _section_text(tailored_resume_data, "projects_section"),
    }

    similarities: Dict[str, float] = {}
    for name, text in section_values.items():
        if not text.strip():
            similarities[name] = 0.0
            continue
        similarities[name] = _cosine_similarity(embeddings.embed_query(text), job_embedding)

    similarities["weighted"] = sum(
        SECTION_WEIGHTS[name] * similarities[name]
        for name in SECTION_WEIGHTS
    )

    return similarities


def _infer_seniority(text: str) -> float:
    normalized = text.lower()

    for label, value in sorted(SENIORITY_LEVELS.items(), key=lambda item: item[1], reverse=True):
        if re.search(rf"\b{re.escape(label)}\b", normalized):
            return value

    year_matches = [int(value) for value in re.findall(r"(\d+)\+?\s*(?:years|yrs)", normalized)]
    if year_matches:
        years = max(year_matches)
        if years >= 10:
            return 0.90
        if years >= 6:
            return 0.75
        if years >= 3:
            return 0.55
        if years >= 1:
            return 0.35

    return 0.55


def _experience_fit_score(
    job_details: Dict[str, Any],
    tailored_resume_data: Dict[str, Any],
) -> Dict[str, float]:
    job_level = _infer_seniority(_job_text(job_details))
    resume_level = _infer_seniority(
        "\n".join(
            [
                _section_text(tailored_resume_data, "summary"),
                _section_text(tailored_resume_data, "work_experience_section"),
                _section_text(tailored_resume_data, "projects_section"),
            ]
        )
    )

    score = 1 - max(0.0, job_level - resume_level)
    return {
        "experience_fit": score,
        "job_seniority": job_level,
        "resume_seniority": resume_level,
    }


def _resume_bullets(tailored_resume_data: Dict[str, Any]) -> List[str]:
    bullets: List[str] = []

    for section_key in ("work_experience_section", "projects_section"):
        for item in tailored_resume_data.get(section_key, []) or []:
            descriptions = item.get("description", []) if isinstance(item, dict) else []
            if isinstance(descriptions, list):
                bullets.extend(str(description) for description in descriptions if str(description).strip())

    return bullets


def _heuristic_noise_penalty(job_details: Dict[str, Any], bullets: List[str]) -> float:
    job_terms = set(re.findall(r"[a-z0-9]+", _job_text(job_details).lower()))
    if not bullets or not job_terms:
        return 0.0

    penalties: List[float] = []
    for bullet in bullets:
        bullet_terms = set(re.findall(r"[a-z0-9]+", bullet.lower()))
        if not bullet_terms:
            penalties.append(1.0)
            continue

        overlap = len(job_terms & bullet_terms) / max(len(bullet_terms), 1)
        penalties.append(max(0.0, min(1.0, 1.0 - overlap * 3.0)))

    return sum(penalties) / len(penalties)


def _noise_penalty(job_details: Dict[str, Any], tailored_resume_data: Dict[str, Any]) -> float:
    bullets = _resume_bullets(tailored_resume_data)
    if not bullets:
        return 0.0

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You evaluate resume bullet relevance for a target job. Return one noise probability per bullet.",
            ),
            (
                "human",
                (
                    "Target job details:\n{job_details}\n\n"
                    "Resume bullets:\n{bullets}\n\n"
                    "For each bullet, assign a score from 0 to 1 where 0 means highly relevant and useful for the job, "
                    "and 1 means off-topic, padding, or not useful for job alignment."
                ),
            ),
        ]
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm.with_structured_output(BulletNoiseScores)

    try:
        response = chain.invoke(
            {
                "job_details": json.dumps(job_details, ensure_ascii=False),
                "bullets": json.dumps(bullets, ensure_ascii=False),
            }
        )
        scores = [max(0.0, min(1.0, float(score))) for score in response.scores[: len(bullets)]]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
    except Exception:
        return _heuristic_noise_penalty(job_details, bullets)


def compute_job_alignment(
    job_details: Dict[str, Any],
    tailored_resume_data: Dict[str, Any],
) -> Dict[str, Any]:
    job = JobDetails(**job_details)
    tailored_resume = Resume(**tailored_resume_data)
    graph = build_knowledge_graph(job, tailored_resume)

    embeddings = OpenAIEmbeddings()

    skill_overlap, k_job_count, k_out_count = _skill_alignment_score(graph, embeddings)
    section_similarity = _section_similarity_score(job_details, tailored_resume_data, embeddings)
    experience_fit = _experience_fit_score(job_details, tailored_resume_data)
    noise_penalty = _noise_penalty(job_details, tailored_resume_data)

    job_alignment = (
        ALPHA * skill_overlap
        + BETA * section_similarity["weighted"]
        + GAMMA * experience_fit["experience_fit"]
        - LAMBDA * noise_penalty
    )

    job_alignment = max(0.0, min(1.0, job_alignment))

    return {
        "job_alignment": job_alignment,
        "skill_overlap": skill_overlap,
        "section_similarity": section_similarity["weighted"],
        "section_similarities": section_similarity,
        "experience_fit": experience_fit["experience_fit"],
        "job_seniority": experience_fit["job_seniority"],
        "resume_seniority": experience_fit["resume_seniority"],
        "noise_penalty": noise_penalty,
        "alpha": ALPHA,
        "beta": BETA,
        "gamma": GAMMA,
        "lambda": LAMBDA,
        "k_job_count": k_job_count,
        "k_out_count": k_out_count,
        "tailored_knowledge_graph": graph.model_dump(mode="json"),
    }
