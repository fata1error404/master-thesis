import math
import re
from typing import Any, Dict, Iterable, List, Set

from langchain_openai import OpenAIEmbeddings

# [TODO] annotation

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


def _to_text(data: Dict[str, Any]) -> str:
    return "\n".join(_text_parts(data.values()))


def _tokens(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _overlap_coefficient(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    return len(a & b) / min(len(a), len(b))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def compute_resume_flow_metrics(
    job_details: Dict[str, Any],
    original_resume_data: Dict[str, Any],
    tailored_resume_data: Dict[str, Any],
) -> Dict[str, Any]:
    job_text = _to_text(job_details)
    original_resume_text = _to_text(original_resume_data)
    tailored_resume_text = _to_text(tailored_resume_data)

    embeddings = OpenAIEmbeddings()
    job_embedding = embeddings.embed_query(job_text)
    original_resume_embedding = embeddings.embed_query(original_resume_text)
    tailored_resume_embedding = embeddings.embed_query(tailored_resume_text)

    job_alignment_orig = _cosine_similarity(original_resume_embedding, job_embedding)
    job_alignment_new = _cosine_similarity(tailored_resume_embedding, job_embedding)
    content_preservation = _cosine_similarity(tailored_resume_embedding, original_resume_embedding)

    job_tokens = _tokens(job_text)
    original_resume_tokens = _tokens(original_resume_text)
    tailored_resume_tokens = _tokens(tailored_resume_text)

    return {
        "job_alignment_orig": job_alignment_orig,
        "job_alignment_new": job_alignment_new,
        "content_preservation": content_preservation,
        "job_alignment_orig_token": _overlap_coefficient(original_resume_tokens, job_tokens),
        "job_alignment_new_token": _overlap_coefficient(tailored_resume_tokens, job_tokens),
        "content_preservation_token": _overlap_coefficient(tailored_resume_tokens, original_resume_tokens),
    }
