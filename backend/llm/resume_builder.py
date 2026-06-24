import json
import re
import copy
from pathlib import Path
from typing import Any, Dict, List, Set

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from prompts.prompt_4_resume_tailoring import PERSON_DESCRIPTION, PROJECTS, WORK_EXPERIENCE
from schemas.resume_schema import Resume


class BulletRewrite(BaseModel):
    rewritten_bullet: str = Field(description="One factually supported rewritten resume bullet.")


class BulletRewriteList(BaseModel):
    bullets: List[str] = Field(description="Factually supported rewritten resume bullets.")


class SummaryRewrite(BaseModel):
    summary: str = Field(description="Factually supported person description / resume summary.")


bullet_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


ROLE_SIGNAL_GROUPS = {
    "frontend": {
        "frontend",
        "front end",
        "web developer",
        "web",
        "react",
        "next.js",
        "next js",
        "javascript",
        "typescript",
        "html",
        "css",
        "ui",
        "ux",
        "responsive",
        "component",
        "browser",
    },
    "backend": {
        "backend",
        "back end",
        "api",
        "rest",
        "database",
        "server",
        "node.js",
        "node js",
        "sql",
        "mongodb",
        "redis",
    },
    "ml": {
        "machine learning",
        "ml",
        "deep learning",
        "model",
        "ranking",
        "computer vision",
        "object detection",
        "pytorch",
        "yolo",
        "nlp",
        "llm",
    },
}

GENERIC_JOB_WORDS = {
    "application",
    "applications",
    "build",
    "clean",
    "collaborate",
    "code",
    "compatibility",
    "detail",
    "efficient",
    "engineer",
    "engineers",
    "enhance",
    "ensure",
    "experience",
    "familiarity",
    "high",
    "intuitive",
    "maintain",
    "maintainable",
    "modern",
    "optimize",
    "performance",
    "production",
    "ready",
    "required",
    "strong",
    "translate",
    "user",
    "using",
    "web",
    "work",
}

BUZZWORD_PHRASES = [
    "enhancing performance and user experience",
    "innovative problem-solving",
    "innovative web development solutions",
    "enhanced data management",
    "modern javascript frameworks",
    "advanced language models",
]

FRONTEND_EXPANSION_TERMS = {
    "component",
    "component-based",
    "frontend",
    "interface",
    "interfaces",
    "responsive",
    "ui",
    "ux",
    "web",
}

MAX_BULLET_CHARS = 165
MAX_SUMMARY_CHARS = 430
MAX_PROJECTS_ONE_PAGE = 3
MAX_COURSES_PER_SCHOOL = 6

STRONG_FACT_TECH_PATTERNS = [
    r"\bA/B tests?\b",
    r"\bAiogram\b",
    r"\bC\+\+\b",
    r"\bFaster R-CNN\b",
    r"\bGLSL\b",
    r"\bJavaScript\b",
    r"\bLLM\b",
    r"\bMongoDB\b",
    r"\bNext\.?js\b",
    r"\bNode\.?js\b",
    r"\bOpenGL\b",
    r"\bPyTorch\b",
    r"\bReact\.?js\b",
    r"\bRedis\b",
    r"\bSQL\b",
    r"\bTON Foundation\b",
    r"\bUnreal Engine\s*\d*\b",
    r"\bYOLO\b",
]


def _truncate(text: str, max_length: int = 700) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _section_hint(section_key: str) -> str:
    return {
        "work_experience_section": "work experience, internships, roles, responsibilities, measurable outcomes",
        "projects_section": "projects, repositories, demos, technical implementation, measurable outcomes",
        "skills_section": "skills, technologies, tools, frameworks, methods",
        "education_section": "education, coursework, degrees, academic background",
        "certifications_section": "certifications, credentials, licenses",
        "achievements_section": "achievements, awards, competitions, recognition",
    }.get(section_key, section_key)


def _format_rag_context(rag_context: Dict[str, Any] | None, section_key: str) -> List[str]:
    if not rag_context:
        return []

    chunks = rag_context.get("retrieved_chunks") or []
    if not isinstance(chunks, list):
        return []

    section_terms = _section_hint(section_key)
    lines = [
        "Retrieved resume evidence from the vector database.",
        f"Prefer chunks relevant to: {section_terms}.",
    ]

    for index, chunk in enumerate(chunks[:5], start=1):
        if not isinstance(chunk, dict):
            continue

        content = _truncate(str(chunk.get("content", "")), 650)
        if not content:
            continue

        metadata = chunk.get("metadata") or {}
        source = ""
        if isinstance(metadata, dict) and metadata:
            source_bits = [
                f"{key}={value}"
                for key, value in metadata.items()
                if value is not None
            ]
            source = f" ({', '.join(source_bits[:3])})" if source_bits else ""

        lines.append(f"{index}. {content}{source}")

    return lines if len(lines) > 2 else []


def _node_label_by_id(knowledge_graph: Dict[str, Any]) -> Dict[str, str]:
    labels = {}
    for node in knowledge_graph.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        label = node.get("label")
        if isinstance(node_id, str) and isinstance(label, str):
            labels[node_id] = label
    return labels


def _format_knowledge_graph_context(
    knowledge_graph: Dict[str, Any] | None,
    section_key: str,
) -> List[str]:
    if not knowledge_graph:
        return []

    nodes = knowledge_graph.get("nodes") or []
    if not isinstance(nodes, list):
        return []

    section_kinds = {
        "work_experience_section": {"experience", "experience_bullet"},
        "projects_section": {"project", "project_bullet"},
        "skills_section": {"resume_skill", "skill_group"},
        "education_section": {"education", "course"},
        "certifications_section": {"certification"},
        "achievements_section": {"achievement"},
    }.get(section_key, set())

    labels = _node_label_by_id(knowledge_graph)

    matched_requirements = []
    matched_evidence = []
    matched_skills = []

    for node in nodes:
        if not isinstance(node, dict):
            continue

        node_type = node.get("type")
        label = str(node.get("label", "")).strip()
        meta = node.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}

        if node_type == "keyword" and meta.get("kind") == "job_requirement":
            score = float(meta.get("best_match_score", 0.0) or 0.0)
            if score > 0:
                matched_requirements.append(
                    (
                        score,
                        meta.get("category", "requirement"),
                        meta.get("raw_text") or label,
                    )
                )

        if node_type == "canonical_skill":
            job_mentions = int(meta.get("job_mentions", 0) or 0)
            resume_mentions = int(meta.get("resume_mentions", 0) or 0)
            evidence_mentions = int(meta.get("evidence_mentions", 0) or 0)
            if job_mentions > 0 and (resume_mentions > 0 or evidence_mentions > 0):
                matched_skills.append(
                    (
                        float(meta.get("best_match_score", 0.0) or 0.0),
                        meta.get("normalized_label") or label,
                    )
                )

        kind = meta.get("kind")
        if section_kinds and kind not in section_kinds:
            continue

        requirement_ids = meta.get("matched_requirement_ids") or []
        skill_ids = meta.get("matched_canonical_skill_ids") or []
        score = float(meta.get("best_match_score", 0.0) or 0.0)

        if score <= 0 and not requirement_ids and not skill_ids:
            continue

        text = meta.get("full_text") or meta.get("raw_label") or label
        requirement_labels = [labels.get(req_id, req_id) for req_id in requirement_ids[:3]]
        skill_labels = [labels.get(skill_id, skill_id) for skill_id in skill_ids[:3]]

        matched_evidence.append(
            (
                score,
                _truncate(str(text), 360),
                requirement_labels,
                skill_labels,
            )
        )

    lines = ["Knowledge graph guidance: use these matches to prioritize and reorder truthful resume content."]

    matched_requirements.sort(key=lambda item: item[0], reverse=True)
    if matched_requirements:
        lines.append("Highest-signal job requirements already supported by the resume:")
        for score, category, text in matched_requirements[:6]:
            lines.append(f"- [{category}, score={score:.2f}] {_truncate(str(text), 220)}")

    matched_skills.sort(key=lambda item: item[0], reverse=True)
    if matched_skills:
        skill_text = ", ".join(str(skill) for _, skill in matched_skills[:15])
        lines.append(f"Canonical matched skills to emphasize when truthful: {skill_text}")

    matched_evidence.sort(key=lambda item: item[0], reverse=True)
    if matched_evidence:
        lines.append(f"Section-specific evidence for {_section_hint(section_key)}:")
        for score, text, requirement_labels, skill_labels in matched_evidence[:6]:
            requirement_text = "; ".join(_truncate(str(x), 120) for x in requirement_labels)
            skill_text = ", ".join(str(x) for x in skill_labels)
            suffix_parts = []
            if requirement_text:
                suffix_parts.append(f"requirements: {requirement_text}")
            if skill_text:
                suffix_parts.append(f"skills: {skill_text}")
            suffix = f" ({'; '.join(suffix_parts)})" if suffix_parts else ""
            lines.append(f"- [score={score:.2f}] {text}{suffix}")

    return lines if len(lines) > 1 else []


def build_tailoring_context(
    section_key: str,
    rag_context: Dict[str, Any] | None = None,
    knowledge_graph: Dict[str, Any] | None = None,
    agent_evidence: Dict[str, Any] | None = None,
) -> str:
    blocks = [
        "Use the following optional context only as guidance for relevance, ordering, and emphasis.",
        "Do not add skills, achievements, dates, employers, degrees, links, or metrics unless they are supported by the original section data or retrieved resume evidence.",
    ]

    rag_lines = _format_rag_context(rag_context, section_key)
    if rag_lines:
        blocks.append("\n<RAG_CONTEXT>\n" + "\n".join(rag_lines) + "\n</RAG_CONTEXT>")

    kg_lines = _format_knowledge_graph_context(knowledge_graph, section_key)
    if kg_lines:
        blocks.append("\n<KNOWLEDGE_GRAPH_CONTEXT>\n" + "\n".join(kg_lines) + "\n</KNOWLEDGE_GRAPH_CONTEXT>")

    agent_lines = _format_agent_evidence(agent_evidence, section_key)
    if agent_lines:
        blocks.append("\n<USER_AGENT_EVIDENCE>\n" + "\n".join(agent_lines) + "\n</USER_AGENT_EVIDENCE>")

    if len(blocks) == 2:
        blocks.append("No extra RAG or knowledge graph context is enabled for this generation.")

    return "\n".join(blocks)


def _format_agent_evidence(agent_evidence: Dict[str, Any] | None, section_key: str) -> List[str]:
    if not agent_evidence:
        return []

    answers = agent_evidence.get("answers") or []
    if not isinstance(answers, list):
        return []

    lines = [
        "User-provided answers collected by AI agent mode.",
        "Use each answer only for its referenced resume entry. Do not invent details for skipped or declined answers.",
    ]

    for answer in answers:
        if not isinstance(answer, dict):
            continue
        if answer.get("target_section") != section_key:
            continue
        if answer.get("status") != "answered":
            continue

        text = str(answer.get("answer") or "").strip()
        if not text:
            continue

        target = answer.get("target_item_key") or "unknown entry"
        field = answer.get("target_field") or "description"
        question = answer.get("question") or ""
        lines.append(f"- entry={target}; field={field}; question={question}; answer={text}")

    return lines if len(lines) > 2 else []


def _entry_key(entry: Dict[str, Any], preferred_fields: List[str]) -> str:
    for field in preferred_fields:
        value = entry.get(field)
        if value:
            return str(value).strip().lower()
    return json.dumps(entry, sort_keys=True, ensure_ascii=False).strip().lower()


def _agent_item_key(entry: Dict[str, Any], fields: List[str]) -> str:
    parts = []
    for field in fields:
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(_normalize_for_match(value))
    return "::".join(parts)


def _is_missing_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.strip().lower()
    return normalized in {
        "",
        "unknown",
        "n/a",
        "na",
        "none",
        "not specified",
        "not provided",
        "unspecified",
    }


def _clean_missing_values(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: _clean_missing_values(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_clean_missing_values(value) for value in obj]
    if _is_missing_value(obj):
        return ""
    return obj


def _copy_original_fields(
    section_key: str,
    original_item: Dict[str, Any],
    generated_item: Dict[str, Any],
) -> Dict[str, Any]:
    item = dict(generated_item)

    immutable_fields = {
        "work_experience_section": ["role", "company", "from_date", "to_date"],
        "projects_section": ["name", "type", "link", "resources", "from_date", "to_date"],
        "education_section": ["degree", "university", "department", "from_date", "to_date", "grade", "highlights"],
        "certifications_section": ["name", "by", "link"],
        "achievements_section": ["name"],
    }.get(section_key, [])

    for field in immutable_fields:
        if field in original_item:
            item[field] = original_item[field]

    if section_key == "work_experience_section":
        # The resume extractor often hallucinates or misplaces locations. Do not
        # surface them in generated resumes unless this field becomes reliable.
        item["location"] = ""

    if section_key in {"work_experience_section", "projects_section"}:
        original_description = original_item.get("description") or []
        generated_description = item.get("description") or []

        if original_description and not _meaningful_strings(generated_description):
            item["description"] = original_description

        if section_key == "projects_section" and not original_description:
            item["description"] = []

    return item


def _filter_supported_entries(
    section_key: str,
    original_items: List[Dict[str, Any]],
    generated_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not original_items:
        return []

    key_fields = {
        "work_experience_section": ["company", "role"],
        "projects_section": ["name"],
        "education_section": ["university", "degree"],
        "certifications_section": ["name"],
        "achievements_section": ["name"],
    }.get(section_key)

    if not key_fields:
        return generated_items or original_items

    original_by_key = {
        _entry_key(item, key_fields): item
        for item in original_items
        if isinstance(item, dict)
    }

    supported_items = []
    seen = set()

    for item in generated_items:
        if not isinstance(item, dict):
            continue

        key = _entry_key(item, key_fields)
        if key not in original_by_key or key in seen:
            continue

        supported_items.append(
            _copy_original_fields(section_key, original_by_key[key], item)
        )
        seen.add(key)

    for key, original_item in original_by_key.items():
        if key not in seen:
            supported_items.append(_copy_original_fields(section_key, original_item, original_item))

    return supported_items


def _text_parts(values: Any) -> List[str]:
    parts: List[str] = []

    if values is None:
        return parts
    if isinstance(values, str):
        text = values.strip()
        return [text] if text else []
    if isinstance(values, dict):
        for value in values.values():
            parts.extend(_text_parts(value))
        return parts
    if isinstance(values, list):
        for value in values:
            parts.extend(_text_parts(value))
        return parts

    text = str(values).strip()
    return [text] if text else []


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#./-]+", " ", text.lower())).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", text.lower()))


def _token_list(text: str) -> List[str]:
    return re.findall(r"[a-z0-9+#]+", text.lower())


def _meaningful_strings(values: Any) -> List[str]:
    return [text for text in _text_parts(values) if not _is_missing_value(text)]


def _agent_answer_is_negative(text: str) -> bool:
    normalized = _normalize_for_match(text)
    return normalized in {
        "no",
        "nope",
        "none",
        "not available",
        "dont know",
        "don't know",
        "i dont know",
        "i don't know",
        "i dont want to answer",
        "i don't want to answer",
        "skip",
    }


def _agent_answer_lines_for_item(
    agent_evidence: Dict[str, Any] | None,
    section_key: str,
    item: Dict[str, Any],
) -> List[str]:
    if not agent_evidence:
        return []

    key_fields = {
        "work_experience_section": ["company", "role"],
        "projects_section": ["name"],
        "education_section": ["university", "degree"],
        "certifications_section": ["name"],
    }.get(section_key, [])
    item_key = _agent_item_key(item, key_fields)

    lines = []
    for answer in agent_evidence.get("answers", []) or []:
        if not isinstance(answer, dict):
            continue
        if answer.get("status") != "answered":
            continue
        if answer.get("target_section") != section_key:
            continue
        if answer.get("target_item_key") != item_key:
            continue

        text = str(answer.get("answer") or "").strip()
        if not text or _agent_answer_is_negative(text):
            continue

        question = str(answer.get("question") or "").strip()
        field = str(answer.get("target_field") or "").strip()
        lines.append(f"{field}: {question} Answer: {text}")

    return lines


def _split_agent_date_answer(answer: str) -> tuple[str, str] | None:
    text = " ".join(answer.split())
    parts = re.split(r"\s+(?:-|–|—|to)\s+", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    start, end = parts[0].strip(), parts[1].strip()
    if not start or not end:
        return None
    return start, end


def _apply_agent_evidence_to_resume(
    resume_data: Dict[str, Any],
    agent_evidence: Dict[str, Any] | None,
) -> Dict[str, Any]:
    if not agent_evidence:
        return resume_data

    updated = copy.deepcopy(resume_data)
    key_fields_by_section = {
        "work_experience_section": ["company", "role"],
        "projects_section": ["name"],
        "education_section": ["university", "degree"],
        "certifications_section": ["name"],
    }

    for answer in agent_evidence.get("answers", []) or []:
        if not isinstance(answer, dict) or answer.get("status") != "answered":
            continue

        text = str(answer.get("answer") or "").strip()
        if not text or _agent_answer_is_negative(text):
            continue

        section_key = answer.get("target_section")
        target_key = answer.get("target_item_key")
        target_field = answer.get("target_field")
        if section_key not in key_fields_by_section:
            continue

        for item in updated.get(section_key, []) or []:
            if not isinstance(item, dict):
                continue
            if _agent_item_key(item, key_fields_by_section[section_key]) != target_key:
                continue

            if target_field == "degree" and section_key == "education_section" and _is_missing_value(str(item.get("degree") or "")):
                item["degree"] = text
            elif target_field == "link" and _is_missing_value(str(item.get("link") or "")):
                item["link"] = text
            elif target_field == "from_date/to_date":
                dates = _split_agent_date_answer(text)
                if dates:
                    if _is_missing_value(str(item.get("from_date") or "")):
                        item["from_date"] = dates[0]
                    if _is_missing_value(str(item.get("to_date") or "")):
                        item["to_date"] = dates[1]

    return updated


def _flat_resume_skills(resume_data: Dict[str, Any]) -> List[str]:
    skills: List[str] = []
    for section in resume_data.get("skills_section", []) or []:
        if not isinstance(section, dict):
            continue
        for skill in section.get("skills", []) or []:
            if isinstance(skill, str) and skill.strip():
                skills.append(skill.strip())
    return list(dict.fromkeys(skills))


def _job_phrases(job_details: Dict[str, Any]) -> List[str]:
    phrases: List[str] = []
    for field in (
        "job_title",
        "keywords",
        "job_duties_and_responsibilities",
        "required_qualifications",
        "preferred_qualifications",
    ):
        phrases.extend(_meaningful_strings(job_details.get(field)))
    return list(dict.fromkeys(phrases))


def _domain_weighted_matches(text: str, multiplier: float = 1.0) -> Dict[str, float]:
    normalized_text = _normalize_for_match(text)
    weights = {}

    for domain, signals in ROLE_SIGNAL_GROUPS.items():
        matches = sum(
            1
            for signal in signals
            if _normalize_for_match(signal) in normalized_text
        )
        if matches:
            weights[domain] = weights.get(domain, 0.0) + matches * multiplier

    return weights


def _merge_weights(*weight_maps: Dict[str, float]) -> Dict[str, float]:
    merged = {}
    for weights in weight_maps:
        for key, value in weights.items():
            merged[key] = merged.get(key, 0.0) + value
    return merged


def _job_domain_weights(job_details: Dict[str, Any]) -> Dict[str, float]:
    title_weights = _domain_weighted_matches(str(job_details.get("job_title", "")), 6.0)
    keyword_weights = _domain_weighted_matches("\n".join(_meaningful_strings(job_details.get("keywords"))), 2.0)
    body_weights = _domain_weighted_matches("\n".join(_job_phrases(job_details)), 0.6)
    weights = _merge_weights(title_weights, keyword_weights, body_weights)

    if title_weights:
        title_domains = set(title_weights)
        for domain in list(weights):
            if domain not in title_domains:
                weights[domain] *= 0.45

    return weights


def _extract_job_terms(job_details: Dict[str, Any]) -> Set[str]:
    terms = set()
    for phrase in _job_phrases(job_details):
        for token in _token_list(phrase):
            if len(token) < 3 or token in GENERIC_JOB_WORDS:
                continue
            terms.add(token)

    return terms


def _build_tailoring_plan(job_details: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
    job_phrases = _job_phrases(job_details)
    resume_skills = _flat_resume_skills(resume_data)
    supported_resume_text = "\n".join(_text_parts(resume_data))
    job_terms = _extract_job_terms(job_details)

    return {
        "job_phrases": job_phrases,
        "job_tokens": job_terms,
        "job_domain_weights": _job_domain_weights(job_details),
        "resume_skills": resume_skills,
        "supported_text": supported_resume_text,
        "supported_tokens": _tokens(supported_resume_text + "\n" + "\n".join(resume_skills)),
    }


def _resume_evidence_for_summary(resume_data: Dict[str, Any]) -> str:
    evidence = {
        "summary": resume_data.get("summary"),
        "skills_section": resume_data.get("skills_section", []),
        "work_experience_section": resume_data.get("work_experience_section", []),
        "projects_section": resume_data.get("projects_section", []),
        "education_section": resume_data.get("education_section", []),
        "certifications_section": resume_data.get("certifications_section", []),
        "achievements_section": resume_data.get("achievements_section", []),
    }
    return "\n".join(_text_parts(evidence))


def _summary_style_guidance(original_summary: str) -> str:
    if not original_summary:
        return "No original person description exists; write exactly two concise resume-summary sentences."

    pronoun_hint = "Preserve first-person voice." if re.search(r"\b(I|I'm|I am|my|me)\b", original_summary) else "Avoid first-person pronouns."
    sentence_count = len([part for part in re.split(r"[.!?]+", original_summary) if part.strip()])

    return (
        f"Original summary has about {sentence_count or 1} sentence(s). "
        f"{pronoun_hint} Use it only as style and tone reference; generate new target-job-aligned content."
    )


def _current_position_from_original_summary(original_summary: str) -> str:
    normalized = _normalize_for_match(original_summary)
    if not normalized:
        return ""

    if "master" in normalized and "student" in normalized:
        return "Master's student"
    if "phd" in normalized and "student" in normalized:
        return "PhD student"
    if "doctoral" in normalized and "student" in normalized:
        return "Doctoral student"
    if "undergraduate" in normalized and "student" in normalized:
        return "Undergraduate student"
    if "student" in normalized:
        return "Student"

    return ""


def _summary_alignment_score(summary: str, plan: Dict[str, Any]) -> float:
    return _relevance_score(summary, plan) + _domain_signal_score(summary, plan["job_domain_weights"])


def _looks_like_skill_inventory(summary: str, plan: Dict[str, Any]) -> bool:
    normalized = _normalize_for_match(summary)
    bad_phrases = (
        "experience across",
        "skilled in",
        "proficient in",
        "technical skills",
        "tech stack",
        "programming languages",
        "tools and technologies",
    )
    if any(phrase in normalized for phrase in bad_phrases):
        return True

    explicit_technology_terms = (
        "c++",
        "python",
        "javascript",
        "typescript",
        "react",
        "next.js",
        "next js",
        "node.js",
        "node js",
        "sql",
        "pytorch",
        "tensorflow",
        "mongodb",
        "redis",
        "aws",
        "azure",
        "gcp",
    )
    if any(term in normalized for term in explicit_technology_terms):
        return True

    mentioned_skills = [
        skill
        for skill in plan["resume_skills"]
        if _normalize_for_match(skill) and _normalize_for_match(skill) in normalized
    ]
    if len(mentioned_skills) >= 3:
        return True

    return bool(re.search(r"\b(?:C\+\+|Python|JavaScript|TypeScript|React|Next\.?js|Node\.?js|SQL|PyTorch)\b(?:,\s*\b(?:C\+\+|Python|JavaScript|TypeScript|React|Next\.?js|Node\.?js|SQL|PyTorch)\b){1,}", summary))


def _summary_supported(summary: str, original_summary: str, resume_evidence: str, plan: Dict[str, Any]) -> bool:
    if not summary.strip() or _is_missing_value(summary):
        return False

    if len(summary) > MAX_SUMMARY_CHARS:
        return False

    if _looks_like_skill_inventory(summary, plan):
        return False

    if "student" in _normalize_for_match(summary) and not _current_position_from_original_summary(original_summary):
        return False

    evidence = f"{original_summary}\n{resume_evidence}"
    if _generated_numbers_are_reasonable(original_summary, summary, evidence, plan) is False:
        return False

    if _missing_strong_facts(original_summary, summary):
        return False

    unsupported = _unsupported_terms(summary, evidence, plan)
    if unsupported:
        return False

    if original_summary:
        original_alignment = _summary_alignment_score(original_summary, plan)
        generated_alignment = _summary_alignment_score(summary, plan)
        if generated_alignment <= original_alignment:
            return False

    return True


def _fallback_generated_summary(job_details: Dict[str, Any], plan: Dict[str, Any]) -> str:
    return _fallback_generated_summary_from_context(job_details, plan, "")


def _fallback_generated_summary_from_context(
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
    original_summary: str,
) -> str:
    job_title = str(job_details.get("job_title") or "the target role").strip()
    current_position = _current_position_from_original_summary(original_summary)
    subject = f"{current_position} with" if current_position else "Candidate with"

    role_lower = job_title.lower()
    if "front" in role_lower or "ui" in role_lower or "web" in role_lower:
        interest = "a keen interest in building interactive, user-friendly interfaces"
        craft = "frontend experiences that are clear, responsive, and easy to use"
    elif "machine learning" in role_lower or "ai" in role_lower or "data" in role_lower:
        interest = "a keen interest in turning applied AI ideas into useful, reliable products"
        craft = "systems that connect model behavior with practical user needs"
    else:
        interest = f"a keen interest in the work of {job_title}"
        craft = "practical solutions that are clear, reliable, and useful"

    return (
        f"{subject} {interest}. "
        f"Brings careful problem-solving, clear communication, and a collaborative mindset to building {craft}."
    )


def _tailor_summary(
    resume_data: Dict[str, Any],
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
) -> str:
    original_summary = str(resume_data.get("summary") or "").strip()
    resume_evidence = _resume_evidence_for_summary(resume_data)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You tailor one resume person description for a target job. "
                    "Use the application prompt exactly. Return only the structured summary field. "
                    "Always generate a fresh summary. Do not invent facts; use the original summary only as style reference."
                ),
            ),
            (
                "human",
                (
                    "{summary_prompt}\n\n"
                    "Target job details:\n{job_details}\n\n"
                    "Supported resume skills:\n{resume_skills}\n\n"
                    "Style guidance:\n{style_guidance}\n\n"
                    "Return a new two-sentence summary that is more aligned with the target job than the original. "
                    "Do not list skills or technologies; write about role interest and working qualities."
                ),
            ),
        ]
    )

    try:
        chain = prompt | bullet_llm.with_structured_output(SummaryRewrite, method="function_calling")
        response = chain.invoke(
            {
                "summary_prompt": PERSON_DESCRIPTION.format(
                    original_summary=original_summary or "(none)",
                    resume_evidence=resume_evidence,
                    job_description=json.dumps(job_details, ensure_ascii=False),
                ),
                "job_details": json.dumps(job_details, ensure_ascii=False),
                "resume_skills": json.dumps(plan["resume_skills"], ensure_ascii=False),
                "style_guidance": _summary_style_guidance(original_summary),
            }
        )
        summary = " ".join(response.summary.split())
    except Exception as e:
        print(f"Error tailoring summary: {e}")
        return _fallback_generated_summary_from_context(job_details, plan, original_summary)

    if not _summary_supported(summary, original_summary, resume_evidence, plan):
        return _fallback_generated_summary_from_context(job_details, plan, original_summary)

    return summary


def _domain_signal_score(text: str, domain_weights: Dict[str, float]) -> float:
    normalized_text = _normalize_for_match(text)
    score = 0.0

    for domain, weight in domain_weights.items():
        signals = ROLE_SIGNAL_GROUPS.get(domain, set())
        for signal in signals:
            normalized_signal = _normalize_for_match(signal)
            if normalized_signal and normalized_signal in normalized_text:
                score += weight

    return score


def _field_text(item: Dict[str, Any], fields: List[str]) -> str:
    return " ".join(
        " ".join(_text_parts(item.get(field)))
        for field in fields
        if field in item
    )


def _strong_fact_score(text: str) -> float:
    facts = _strong_facts(text)
    return len(facts["numbers"]) * 2.0 + len(facts["money"]) * 3.0 + len(facts["scale"]) * 2.0 + len(facts["technologies"])


def _relevance_score(value: Any, plan: Dict[str, Any]) -> float:
    text = " ".join(_text_parts(value))
    if not text:
        return 0.0

    normalized_text = _normalize_for_match(text)
    tokens = _tokens(text)
    job_tokens = plan["job_tokens"]
    token_score = len(tokens & job_tokens)

    phrase_score = 0.0
    for phrase in plan["job_phrases"]:
        normalized_phrase = _normalize_for_match(phrase)
        if normalized_phrase and normalized_phrase in normalized_text:
            phrase_score += 3.0

    skill_score = 0.0
    for skill in plan["resume_skills"]:
        normalized_skill = _normalize_for_match(skill)
        if normalized_skill and normalized_skill in normalized_text:
            skill_score += 2.0

    return token_score + phrase_score + skill_score


def _entry_relevance_score(item: Dict[str, Any], plan: Dict[str, Any], section_key: str) -> float:
    full_text = " ".join(_text_parts(item))
    title_text = _field_text(item, ["role", "name", "type"])
    evidence_text = _field_text(item, ["description"])
    company_text = _field_text(item, ["company"])

    title_domain = _domain_signal_score(title_text, plan["job_domain_weights"])
    evidence_domain = _domain_signal_score(evidence_text, plan["job_domain_weights"])
    company_domain = _domain_signal_score(company_text, plan["job_domain_weights"])

    job_term_score = len(_tokens(full_text) & plan["job_tokens"])
    skill_score = 0.0
    normalized_full_text = _normalize_for_match(full_text)
    for skill in plan["resume_skills"]:
        normalized_skill = _normalize_for_match(skill)
        if normalized_skill and normalized_skill in normalized_full_text:
            skill_score += 1.0

    score = (
        title_domain * 12.0
        + evidence_domain * 4.0
        + company_domain * 2.0
        + job_term_score * 1.5
        + skill_score
        + _strong_fact_score(full_text) * 0.4
    )

    if section_key == "work_experience_section" and title_domain > 0:
        score += 8.0
    if section_key == "projects_section" and evidence_domain > 0:
        score += 4.0

    return score


def _sorted_by_relevance(items: List[Dict[str, Any]], plan: Dict[str, Any], section_key: str) -> List[Dict[str, Any]]:
    ranked = sorted(
        enumerate(items),
        key=lambda pair: (_entry_relevance_score(pair[1], plan, section_key), -pair[0]),
        reverse=True,
    )
    return [item for _, item in ranked]


def _number_signatures(text: str) -> set[str]:
    signatures = set()
    for match in re.findall(r"(?:\$|%|x)?\d[\d,.$%x+]*", text):
        digits = re.sub(r"\D", "", match)
        if digits:
            signatures.add(digits)
    return signatures


def _strong_facts(text: str) -> Dict[str, Set[str]]:
    money = {
        "$" + re.sub(r"\D", "", match)
        for match in re.findall(r"\$\s*\d[\d,]*(?:\.\d+)?", text)
        if re.sub(r"\D", "", match)
    }
    numbers = _number_signatures(text)
    scale = {
        " ".join(match.lower().split())
        for match in re.findall(
            r"\b(?:millions?|billions?|thousands?)\s+of\s+[a-z][a-z0-9-]*\b",
            text,
            flags=re.IGNORECASE,
        )
    }
    awards = {
        " ".join(match.lower().split())
        for match in re.findall(
            r"\b(?:\d+(?:st|nd|rd|th)\s+place|prize winner|hackathon|competition)\b",
            text,
            flags=re.IGNORECASE,
        )
    }
    technologies = set()
    for pattern in STRONG_FACT_TECH_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if isinstance(match, tuple):
                match = " ".join(part for part in match if part)
            technologies.add(_normalize_for_match(str(match)))

    return {
        "money": money,
        "numbers": numbers,
        "scale": scale,
        "awards": awards,
        "technologies": technologies,
    }


def _missing_strong_facts(original: str, rewritten: str) -> Dict[str, Set[str]]:
    original_facts = _strong_facts(original)
    rewritten_facts = _strong_facts(rewritten)
    missing = {}

    for key, values in original_facts.items():
        lost = values - rewritten_facts.get(key, set())
        if lost:
            missing[key] = lost

    return missing


def _is_award_or_funding_bullet(text: str) -> bool:
    normalized = _normalize_for_match(text)
    facts = _strong_facts(text)

    if facts["money"] and any(term in normalized for term in ("hackathon", "competition", "prize", "winner", "fund", "foundation")):
        return True

    return any(
        term in normalized
        for term in (
            "1st place",
            "first place",
            "prize winner",
            "hackathon",
            "university startup",
            "ton foundation",
            "innovation promotion fund",
        )
    )


def _compact_sentence(text: str, max_chars: int = MAX_BULLET_CHARS) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= max_chars:
        return text

    removable_phrases = [
        " to enhance user experience",
        " to improve user experience",
        " and improve user experience",
        " and ensure cross-browser compatibility",
        " ensuring seamless integration with frontend applications",
        " giving reviewers a production-facing view of frontend implementation quality",
        " strengthening practical experience with frontend-to-backend data flows",
        " to optimize training processes",
    ]
    compacted = text
    for phrase in removable_phrases:
        compacted = compacted.replace(phrase, "")
        if len(compacted) <= max_chars:
            return compacted.strip(" ,;.")

    clauses = re.split(r",\s+|\s+while\s+|\s+and\s+", compacted)
    if len(clauses) > 1:
        first = clauses[0].strip(" ,;.")
        if 60 <= len(first) <= max_chars:
            return first

    truncated = compacted[: max_chars - 1].rsplit(" ", 1)[0].strip(" ,;.")
    return truncated + "."


def _unsupported_terms(rewritten: str, evidence: str, plan: Dict[str, Any]) -> List[str]:
    evidence_norm = _normalize_for_match(evidence + "\n" + "\n".join(plan["resume_skills"]))
    rewritten_norm = _normalize_for_match(rewritten)

    risky_phrases = [
        "rest api",
        "rest apis",
        "state management",
        "typescript",
        "cross browser",
        "wireframe",
        "wireframes",
        "designer",
        "designers",
        "design team",
        "ui ux",
        "user engagement",
        "responsive",
        "high performance",
        "frontend tooling",
        "cross functional",
    ]

    buzzwords = [
        phrase
        for phrase in BUZZWORD_PHRASES
        if _normalize_for_match(phrase) in rewritten_norm
    ]

    return [
        phrase
        for phrase in risky_phrases
        if phrase in rewritten_norm
        and phrase not in evidence_norm
        and not _supported_contextual_term(phrase, evidence, plan)
    ] + buzzwords


def _supported_contextual_term(phrase: str, evidence: str, plan: Dict[str, Any]) -> bool:
    evidence_norm = _normalize_for_match(evidence + "\n" + "\n".join(plan["resume_skills"]))
    phrase_norm = _normalize_for_match(phrase)

    frontend_evidence = any(
        signal in evidence_norm
        for signal in ("frontend", "front end", "web developer", "website", "react", "next.js", "next js", "html", "css")
    )
    if frontend_evidence and any(term in phrase_norm for term in FRONTEND_EXPANSION_TERMS):
        return True

    api_evidence = any(signal in evidence_norm for signal in ("node.js", "node js", "mongodb", "redis", "sql", "bot developer"))
    if api_evidence and phrase_norm in {"rest api", "rest apis", "state management", "backend engineers"}:
        return True

    return False


def _relevant_enough_for_strong_rewrite(evidence: str, plan: Dict[str, Any]) -> bool:
    return _relevance_score(evidence, plan) >= 4.0 or _domain_signal_score(evidence, plan["job_domain_weights"]) >= 4.0


def _generated_numbers_are_reasonable(original: str, rewritten: str, evidence: str, plan: Dict[str, Any]) -> bool:
    original_numbers = _number_signatures(evidence)
    rewritten_numbers = _number_signatures(rewritten)
    new_numbers = rewritten_numbers - original_numbers
    return not new_numbers


def _valid_rewrite(original: str, rewritten: str, evidence: str, plan: Dict[str, Any]) -> bool:
    if not rewritten.strip() or _is_missing_value(rewritten):
        return False

    if not _generated_numbers_are_reasonable(original, rewritten, evidence, plan):
        return False

    if _missing_strong_facts(original, rewritten):
        return False

    if _unsupported_terms(rewritten, evidence, plan):
        return False

    if len(rewritten) > MAX_BULLET_CHARS and not _is_award_or_funding_bullet(rewritten):
        return False

    return True


def _rewrite_bullet(
    bullet: str,
    item: Dict[str, Any],
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
) -> str:
    bullet = bullet.strip()
    if not bullet:
        return bullet

    if _is_award_or_funding_bullet(bullet):
        return bullet

    item_context = "\n".join(_text_parts({key: value for key, value in item.items() if key != "description"}))
    evidence = f"{item_context}\n{bullet}"
    strong_facts = _strong_facts(bullet)
    strong_fact_values = [
        value
        for values in strong_facts.values()
        for value in sorted(values)
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You rewrite exactly one resume bullet for a target job. "
                    "Preserve factual truth. Make highly job-relevant bullets richer and closer to "
                    "the XYZ formula: did X by doing Y, achieved Z. Do not invent employers, dates, "
                    "tools, or exact metrics. If the source has no metric, express the result as "
                    "scope, readiness, maintainability, quality, or user-facing value."
                ),
            ),
            (
                "human",
                (
                    "Target job details:\n{job_details}\n\n"
                    "Supported resume skills:\n{resume_skills}\n\n"
                    "Entry context:\n{entry_context}\n\n"
                    "Strong facts that must be preserved exactly or with equivalent wording:\n{strong_facts}\n\n"
                    "Original bullet:\n{original_bullet}\n\n"
                    "Rewrite the bullet as one concise resume bullet. "
                    "For bullets strongly related to the job, expand short descriptions into a richer "
                    "specific accomplishment using supported role, project, and skill evidence. "
                    "Every claim must be supported by the original bullet, entry context, or supported skills."
                ),
            ),
        ]
    )

    try:
        chain = prompt | bullet_llm.with_structured_output(BulletRewrite, method="function_calling")
        response = chain.invoke(
            {
                "job_details": json.dumps(job_details, ensure_ascii=False),
                "resume_skills": json.dumps(plan["resume_skills"], ensure_ascii=False),
                "entry_context": item_context,
                "strong_facts": json.dumps(strong_fact_values, ensure_ascii=False),
                "original_bullet": bullet,
            }
        )
        rewritten = response.rewritten_bullet.strip()
    except Exception as e:
        print(f"Error rewriting bullet: {e}")
        return bullet

    if not _valid_rewrite(bullet, rewritten, evidence, plan):
        return bullet

    return _compact_sentence(rewritten)


def _rewrite_descriptions(
    item: Dict[str, Any],
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
    section_key: str,
    agent_evidence: Dict[str, Any] | None = None,
) -> List[str]:
    descriptions = _meaningful_strings(item.get("description") or [])
    if not descriptions:
        return []

    award_bullets = [bullet for bullet in descriptions if _is_award_or_funding_bullet(bullet)]
    rewrite_candidates = [bullet for bullet in descriptions if not _is_award_or_funding_bullet(bullet)]
    if not rewrite_candidates:
        return descriptions

    agent_lines = _agent_answer_lines_for_item(agent_evidence, section_key, item)
    item_context = "\n".join(
        _text_parts({key: value for key, value in item.items() if key != "description"})
        + (["User-provided agent evidence:"] + agent_lines if agent_lines else [])
    )
    evidence = f"{item_context}\n" + "\n".join(descriptions)
    relevant = _relevant_enough_for_strong_rewrite(evidence, plan)
    max_bullets = 2 if section_key == "work_experience_section" and relevant else len(rewrite_candidates)
    max_bullets = 1 if section_key == "projects_section" else max_bullets
    section_prompt = {
        "work_experience_section": WORK_EXPERIENCE,
        "projects_section": PROJECTS,
    }.get(section_key, "")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You rewrite resume bullets for a target job using only the supplied entry evidence. "
                    "Follow the section-specific tailoring prompt provided by the application. "
                    "Do not hardcode assumptions. Do not invent employers, dates, tools, exact metrics, awards, "
                    "links, team sizes, or business outcomes. Preserve concise award/funding facts outside this task. "
                    "If the entry is work experience and strongly matches the job, produce two concrete non-award "
                    "implementation bullets. If the entry is a personal or academic project, produce one enhanced "
                    "feature-focused description; do not force XYZ metrics for personal projects."
                ),
            ),
            (
                "human",
                (
                    "Target job details:\n{job_details}\n\n"
                    "Section-specific tailoring prompt:\n{section_prompt}\n\n"
                    "Supported resume skills:\n{resume_skills}\n\n"
                    "Entry context:\n{entry_context}\n\n"
                    "Original non-award bullets:\n{original_bullets}\n\n"
                    "Write {max_bullets} bullet(s). Requirements:\n"
                    "- Be specific to implemented features, architecture, UI flows, data/API integration, tooling, or project artifacts.\n"
                    "- If the original bullet is short, infer concrete feature categories from the entry itself "
                    "(for example pages, components, navigation, demos, dashboards, forms, bots, search, data flow), "
                    "but do not invent named features that are not implied by the entry.\n"
                    "- Use job-description language only when it is grounded in the entry context or supported skills.\n"
                    "- Avoid generic phrases like 'enhanced user experience', 'innovative solutions', or 'frontend structure'.\n"
                    "- For work experience, prefer XYZ style: built/implemented X using Y to improve Z, but do not invent exact numbers.\n"
                    "- For projects, describe concrete features/artifacts and relevant frontend concepts without fake impact metrics.\n"
                    "- Each bullet must be concise and must not exceed {max_chars} characters."
                ),
            ),
        ]
    )

    try:
        chain = prompt | bullet_llm.with_structured_output(BulletRewriteList, method="function_calling")
        response = chain.invoke(
            {
                "job_details": json.dumps(job_details, ensure_ascii=False),
                "section_prompt": section_prompt,
                "resume_skills": json.dumps(plan["resume_skills"], ensure_ascii=False),
                "entry_context": item_context,
                "original_bullets": json.dumps(rewrite_candidates, ensure_ascii=False),
                "max_bullets": max_bullets,
                "max_chars": MAX_BULLET_CHARS,
            }
        )
        rewritten = [_compact_sentence(str(bullet)) for bullet in response.bullets[:max_bullets]]
    except Exception as e:
        print(f"Error rewriting description list: {e}")
        rewritten = [
            _rewrite_bullet(description, item, job_details, plan)
            for description in rewrite_candidates
        ][:max_bullets]

    valid = [
        bullet
        for bullet in rewritten
        if _valid_rewrite("\n".join(rewrite_candidates), bullet, evidence, plan)
    ]
    if not valid:
        valid = [
            _rewrite_bullet(description, item, job_details, plan)
            for description in rewrite_candidates
        ][:max_bullets]

    return valid + award_bullets


def _tailor_bullets(
    item: Dict[str, Any],
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
    section_key: str,
    agent_evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    tailored = dict(item)
    tailored["description"] = _rewrite_descriptions(item, job_details, plan, section_key, agent_evidence)
    return tailored


def _limit_bullets_for_one_page(
    items: List[Dict[str, Any]],
    plan: Dict[str, Any],
    section_key: str,
) -> List[Dict[str, Any]]:
    if section_key == "work_experience_section":
        return items

    limited = []
    for index, item in enumerate(items):
        copy = dict(item)
        descriptions = _meaningful_strings(copy.get("description") or [])
        max_bullets = 1

        descriptions = sorted(
            descriptions,
            key=lambda bullet: (
                _is_award_or_funding_bullet(bullet),
                _relevance_score(bullet, plan),
                _strong_fact_score(bullet),
            ),
            reverse=True,
        )
        copy["description"] = descriptions[:max_bullets]
        limited.append(copy)
    return limited


def _tailor_work_experience(
    resume_data: Dict[str, Any],
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
    agent_evidence: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    items = []
    for original in resume_data.get("work_experience_section", []) or []:
        if not isinstance(original, dict):
            continue
        item = _copy_original_fields("work_experience_section", original, original)
        item = _tailor_bullets(item, job_details, plan, "work_experience_section", agent_evidence)
        items.append(item)
    items = _sorted_by_relevance(items, plan, "work_experience_section")
    return _limit_bullets_for_one_page(items, plan, "work_experience_section")


def _tailor_projects(
    resume_data: Dict[str, Any],
    job_details: Dict[str, Any],
    plan: Dict[str, Any],
    agent_evidence: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    items = []
    for original in resume_data.get("projects_section", []) or []:
        if not isinstance(original, dict):
            continue
        item = _copy_original_fields("projects_section", original, original)
        item = _tailor_bullets(item, job_details, plan, "projects_section", agent_evidence)
        items.append(item)
    items = _sorted_by_relevance(items, plan, "projects_section")
    items = items[:MAX_PROJECTS_ONE_PAGE]
    return _limit_bullets_for_one_page(items, plan, "projects_section")


def _tailor_skills(resume_data: Dict[str, Any], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections = []
    for section in resume_data.get("skills_section", []) or []:
        if not isinstance(section, dict):
            continue
        item = dict(section)
        skills = [skill for skill in item.get("skills", []) or [] if isinstance(skill, str) and skill.strip()]
        item["skills"] = sorted(skills, key=lambda skill: _relevance_score(skill, plan), reverse=True)
        sections.append(item)

    return sorted(sections, key=lambda section: _relevance_score(section, plan), reverse=True)


def _sanitize_education_section(resume_data: Dict[str, Any], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
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

    items = []
    for original in resume_data.get("education_section", []) or []:
        if not isinstance(original, dict):
            continue

        item = dict(original)
        degree = item.get("degree")
        department = item.get("department")
        if isinstance(degree, str) and isinstance(department, str) and department.strip():
            normalized = re.sub(r"\s+", " ", degree.strip().lower())
            if normalized in generic_degree_labels:
                item["degree"] = ""

        courses = item.get("courses")
        if isinstance(courses, list):
            item["courses"] = sorted(
                [course for course in courses if isinstance(course, str) and course.strip()],
                key=lambda course: _relevance_score(course, plan),
                reverse=True,
            )[:MAX_COURSES_PER_SCHOOL]

        items.append(item)

    return items


def _canonical_claim(text: str) -> str:
    normalized = _normalize_for_match(text)
    normalized = normalized.replace("$", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _claim_tokens(text: str) -> Set[str]:
    return {
        token
        for token in _tokens(text)
        if len(token) >= 3 and token not in GENERIC_JOB_WORDS
    }


def _claim_number_signatures(text: str) -> Set[str]:
    return _number_signatures(text)


def _achievement_exists_elsewhere(achievement: str, other_text: str, other_canonical: str) -> bool:
    canonical = _canonical_claim(achievement)
    if canonical and canonical in other_canonical:
        return True

    achievement_numbers = _claim_number_signatures(achievement)
    other_numbers = _claim_number_signatures(other_text)
    if achievement_numbers and achievement_numbers.issubset(other_numbers):
        achievement_tokens = _claim_tokens(achievement)
        other_tokens = _claim_tokens(other_text)
        overlap = achievement_tokens & other_tokens
        if len(overlap) >= min(3, len(achievement_tokens)):
            return True

    achievement_lower = achievement.lower()
    if any(word in achievement_lower for word in ("hackathon", "prize", "winner", "competition", "foundation")):
        achievement_tokens = _claim_tokens(achievement)
        other_tokens = _claim_tokens(other_text)
        if len(achievement_tokens & other_tokens) >= 4:
            return True

    return False


def _filter_duplicate_achievements(resume_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    other_sections_text = "\n".join(
        _text_parts(
            {
                "work_experience_section": resume_data.get("work_experience_section", []),
                "projects_section": resume_data.get("projects_section", []),
                "education_section": resume_data.get("education_section", []),
                "certifications_section": resume_data.get("certifications_section", []),
            }
        )
    )
    other_canonical = _canonical_claim(other_sections_text)

    filtered = []
    seen = set()
    for achievement in resume_data.get("achievements_section", []) or []:
        if not isinstance(achievement, dict):
            continue

        name = str(achievement.get("name") or "").strip()
        if not name:
            continue

        canonical = _canonical_claim(name)
        if not canonical or canonical in seen:
            continue
        if _achievement_exists_elsewhere(name, other_sections_text, other_canonical):
            continue

        filtered.append(achievement)
        seen.add(canonical)

    return filtered


def build_resume(
    job_details: Dict[str, Any],
    resume_data: Dict[str, Any],
    resume_file_id: str,
    output_dir: str,
    rag_context: Dict[str, Any] | None = None,
    knowledge_graph: Dict[str, Any] | None = None,
    agent_evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    resume_data = _apply_agent_evidence_to_resume(resume_data, agent_evidence)
    plan = _build_tailoring_plan(job_details, resume_data)

    # append static fields from input resume
    tailored_resume = {
        "name": resume_data["name"],
        "summary": _tailor_summary(resume_data, job_details, plan),
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

    tailored_resume["work_experience_section"] = _tailor_work_experience(
        resume_data,
        job_details,
        plan,
        agent_evidence,
    )
    tailored_resume["projects_section"] = _tailor_projects(
        resume_data,
        job_details,
        plan,
        agent_evidence,
    )
    tailored_resume["skills_section"] = _tailor_skills(resume_data, plan)
    tailored_resume["education_section"] = _sanitize_education_section(resume_data, plan)
    tailored_resume["certifications_section"] = resume_data.get("certifications_section", [])
    tailored_resume["achievements_section"] = _filter_duplicate_achievements(resume_data)

    tailored_resume = _clean_missing_values(tailored_resume)

    # validate the result (force convert to Resume object and back to JSON dictionary)
    validated_resume = Resume(**tailored_resume).model_dump(mode="json")

    # save to JSON
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / "resume_tailored.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(validated_resume, f, indent=2, ensure_ascii=False)

    return validated_resume
