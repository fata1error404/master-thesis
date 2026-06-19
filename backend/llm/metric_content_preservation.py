import math
from typing import Any, Dict, Iterable, List, Set

from langchain_openai import OpenAIEmbeddings

from llm.knowledge_graph_builder import build_knowledge_graph
from schemas.job_details_schema import JobDetails
from schemas.knowledge_graph import KnowledgeGraph
from schemas.resume_schema import Resume

# [TODO] annotation

ALPHA = 0.3
BETA = 0.7


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


def _resume_to_text(resume: Dict[str, Any]) -> str:
    return "\n".join(_text_parts(resume.values()))


def _canonical_resume_skills(graph: KnowledgeGraph) -> Set[str]:
    skills: Set[str] = set()

    for node in graph.nodes:
        if node.type != "canonical_skill":
            continue

        meta = node.meta or {}
        resume_mentions = int(meta.get("resume_mentions", 0) or 0)
        evidence_mentions = int(meta.get("evidence_mentions", 0) or 0)

        if resume_mentions <= 0 and evidence_mentions <= 0:
            continue

        normalized_label = meta.get("normalized_label")
        if isinstance(normalized_label, str) and normalized_label.strip():
            skills.add(normalized_label.strip())
        else:
            skills.add(node.label.strip().lower())

    return skills


def _skill_overlap(k_out: Set[str], k_in: Set[str]) -> float:
    if not k_out and not k_in:
        return 1.0
    if not k_out or not k_in:
        return 0.0

    return len(k_out & k_in) / min(len(k_out), len(k_in))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def compute_content_preservation(
    job_details: Dict[str, Any],
    original_resume_data: Dict[str, Any],
    tailored_resume_data: Dict[str, Any],
    original_knowledge_graph_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    job = JobDetails(**job_details)
    original_resume = Resume(**original_resume_data)
    tailored_resume = Resume(**tailored_resume_data)

    if original_knowledge_graph_data:
        original_graph = KnowledgeGraph(**original_knowledge_graph_data)
    else:
        original_graph = build_knowledge_graph(job, original_resume)

    tailored_graph = build_knowledge_graph(job, tailored_resume)

    k_in = _canonical_resume_skills(original_graph)
    k_out = _canonical_resume_skills(tailored_graph)
    skill_overlap = _skill_overlap(k_out, k_in)

    embeddings = OpenAIEmbeddings()
    original_embedding = embeddings.embed_query(_resume_to_text(original_resume_data))
    tailored_embedding = embeddings.embed_query(_resume_to_text(tailored_resume_data))
    semantic_similarity = _cosine_similarity(tailored_embedding, original_embedding)

    content_preservation = ALPHA * skill_overlap + BETA * semantic_similarity

    return {
        "content_preservation": content_preservation,
        "skill_overlap": skill_overlap,
        "semantic_similarity": semantic_similarity,
        "alpha": ALPHA,
        "beta": BETA,
        "k_in_count": len(k_in),
        "k_out_count": len(k_out),
        "k_intersection_count": len(k_out & k_in),
        "tailored_knowledge_graph": tailored_graph.model_dump(mode="json"),
    }
