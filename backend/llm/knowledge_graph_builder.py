from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from schemas.knowledge_graph import KnowledgeGraph, KGNode, KGEdge
from schemas.job_details_schema import JobDetails
from schemas.resume_schema import Resume


# -----------------------------------------------------------------------------
# Normalization helpers
# -----------------------------------------------------------------------------

_DISPLAY_ALIASES: Dict[str, str] = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "python": "Python",
    "sql": "SQL",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "api": "API",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "html": "HTML",
    "css": "CSS",
    "ui": "UI",
    "ux": "UX",
    "ml": "ML",
    "ai": "AI",
    "llm": "LLM",
    "nlp": "NLP",
    "csharp": "C#",
    "cpp": "C++",
    "ci cd": "CI/CD",
    "node js": "Node.js",
    "react": "React",
    "next js": "Next.js",
    "vue": "Vue",
    "angular": "Angular",
    "frontend": "Frontend",
    "front end": "Frontend",
    "backend": "Backend",
    "back end": "Backend",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "data science": "Data Science",
    "data analysis": "Data Analysis",
    "devops": "DevOps",
    "full stack": "Full Stack",
    "natural language processing": "NLP",
    "computer vision": "Computer Vision",
    "object oriented programming": "OOP",
}

_CANONICAL_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\breact\.?\s*js\b", "react"),
    (r"\breactjs\b", "react"),
    (r"\bnext\.?\s*js\b", "next js"),
    (r"\bnode\.?\s*js\b", "node js"),
    (r"\bvue\.?\s*js\b", "vue"),
    (r"\bfront[-\s]?end\b", "frontend"),
    (r"\bback[-\s]?end\b", "backend"),
    (r"\bci/cd\b", "ci cd"),
    (r"\bc\+\+\b", "cpp"),
    (r"\bc#\b", "csharp"),
    (r"\brest[-\s]?api\b", "rest api"),
    (r"\bnatural language processing\b", "nlp"),
    (r"\bartificial intelligence\b", "ai"),
    (r"\bmachine learning\b", "machine learning"),
    (r"\bdeep learning\b", "deep learning"),
    (r"\bfull[-\s]?stack\b", "full stack"),
    (r"\bdev[-\s]?ops\b", "devops"),
    (r"\bdata[-\s]?science\b", "data science"),
    (r"\bdata[-\s]?analysis\b", "data analysis"),
    (r"\bobject[-\s]?oriented programming\b", "object oriented programming"),
]

_GENERIC_REQUIREMENT_PREFIXES = (
    "experience",
    "proficiency",
    "knowledge",
    "familiarity",
    "ability",
    "able",
    "degree",
    "bachelor",
    "master",
    "certificate",
    "certification",
    "preferred",
    "required",
)


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    for pattern, replacement in _CANONICAL_REPLACEMENTS:
        t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)
    t = (
        t.replace("&", " and ")
        .replace("/", " ")
        .replace("-", " ")
        .replace(".", " ")
        .replace(",", " ")
        .replace(":", " ")
        .replace(";", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("[", " ")
        .replace("]", " ")
        .replace("{", " ")
        .replace("}", " ")
        .replace("|", " ")
        .replace("_", " ")
        .replace("+", " ")
        .replace("?", " ")
        .replace("!", " ")
        .replace('"', " ")
        .replace("'", " ")
    )
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _slugify(text: str) -> str:
    text = _normalize_text(text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "item"


def _shorten(text: str, max_len: int = 90) -> str:
    text = " ".join((text or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _canonical_skill_key(text: str) -> str:
    return _normalize_text(text)


def _display_skill_label(canonical_key: str) -> str:
    canonical_key = _canonical_skill_key(canonical_key)
    if canonical_key in _DISPLAY_ALIASES:
        return _DISPLAY_ALIASES[canonical_key]

    parts = canonical_key.split()
    if not parts:
        return canonical_key

    def _title_word(word: str) -> str:
        if word in _DISPLAY_ALIASES:
            return _DISPLAY_ALIASES[word]
        if word.isupper():
            return word
        return word[:1].upper() + word[1:]

    return " ".join(_title_word(part) for part in parts)


def _token_set(text: str) -> set[str]:
    t = _normalize_text(text)
    return set(t.split()) if t else set()


def _looks_like_skill_phrase(text: str) -> bool:
    norm = _normalize_text(text)
    if not norm:
        return False
    tokens = norm.split()
    if not tokens or len(tokens) > 6:
        return False
    if tokens[0] in _GENERIC_REQUIREMENT_PREFIXES and len(tokens) > 2:
        return False
    return True


def _score_match(a: str, b: str) -> float:
    a = _normalize_text(a)
    b = _normalize_text(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        longer = max(len(a), len(b))
        shorter = min(len(a), len(b))
        return min(1.0, 0.82 + (shorter / max(longer, 1)) * 0.18)

    a_tokens = _token_set(a)
    b_tokens = _token_set(b)
    if not a_tokens or not b_tokens:
        return SequenceMatcher(None, a, b).ratio()

    overlap = len(a_tokens & b_tokens)
    if overlap == 0:
        return SequenceMatcher(None, a, b).ratio() * 0.65

    union = len(a_tokens | b_tokens)
    jaccard = overlap / max(union, 1)
    coverage = overlap / max(len(b_tokens), 1)
    seq = SequenceMatcher(None, a, b).ratio()
    return max(jaccard, coverage * 0.9, seq * 0.8)


def _threshold_for_term(term: str) -> float:
    tokens = _normalize_text(term).split()
    if not tokens:
        return 1.0
    if len(tokens) <= 3:
        return 0.45
    if len(tokens) <= 6:
        return 0.55
    return 0.62


def _relation_for_score(score: float) -> str:
    return "strong_match" if score >= 0.82 else "matches"


def _parent_semantic_relation(parent_kind: str) -> str:
    if parent_kind == "experience":
        return "demonstrates"
    if parent_kind == "project":
        return "supports"
    if parent_kind == "education":
        return "supports"
    if parent_kind == "certification":
        return "supports"
    if parent_kind == "summary":
        return "indicates"
    return "supports"


def _merge_meta(existing: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = dict(existing or {})
    if not incoming:
        return base

    for key, value in incoming.items():
        if value is None:
            continue

        if key not in base:
            base[key] = value
            continue

        current = base[key]

        if isinstance(current, list) and isinstance(value, list):
            merged = list(current)
            for item in value:
                if item not in merged:
                    merged.append(item)
            base[key] = merged
        elif isinstance(current, dict) and isinstance(value, dict):
            merged = dict(current)
            merged.update(value)
            base[key] = merged
        elif current != value:
            base[key] = value

    return base


# -----------------------------------------------------------------------------
# Builder
# -----------------------------------------------------------------------------

class _KnowledgeGraphBuilder:
    def __init__(self) -> None:
        self.nodes: Dict[str, KGNode] = {}
        self.edges: List[KGEdge] = []
        self.edge_index: Dict[Tuple[str, str, str], int] = {}

        self.job_requirement_nodes: List[Dict[str, Any]] = []
        self.canonical_skill_nodes: Dict[str, str] = {}
        self.parent_canonical_matches: Dict[str, set[str]] = defaultdict(set)

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = KGNode(
                id=node_id,
                type=node_type,  # type: ignore[arg-type]
                label=label,
                meta=meta or {},
            )
            return

        existing = self.nodes[node_id]
        existing.meta = _merge_meta(existing.meta, meta)

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        weight: float = 1.0,
        confidence: float = 1.0,
        evidence: Optional[str] = None,
        provenance: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        key = (source, target, relation)
        if key in self.edge_index:
            edge = self.edges[self.edge_index[key]]
            edge.weight = max(edge.weight, weight)
            edge.confidence = max(edge.confidence, confidence)
            if evidence and not edge.evidence:
                edge.evidence = evidence
            if provenance and not edge.provenance:
                edge.provenance = provenance
            edge.meta = _merge_meta(edge.meta, meta)
            return

        edge = KGEdge(
            source=source,
            target=target,
            relation=relation,
            weight=weight,
            confidence=confidence,
            evidence=evidence,
            provenance=provenance,
            meta=meta or {},
        )
        self.edge_index[key] = len(self.edges)
        self.edges.append(edge)

    def add_canonical_skill(
        self,
        raw_text: str,
        source_kind: str,
        source_id: str,
    ) -> Optional[str]:
        canonical_key = _canonical_skill_key(raw_text)
        if not canonical_key:
            return None

        canonical_id = self.canonical_skill_nodes.get(canonical_key)
        if not canonical_id:
            canonical_id = f"skill_can_{_slugify(canonical_key)}"
            self.canonical_skill_nodes[canonical_key] = canonical_id
            self.add_node(
                canonical_id,
                "canonical_skill",
                _display_skill_label(canonical_key),
                meta={
                    "kind": "canonical_skill",
                    "canonical": True,
                    "normalized_label": canonical_key,
                    "raw_labels": [raw_text],
                    "sources": [source_kind],
                    "job_mentions": 0,
                    "resume_mentions": 0,
                    "evidence_mentions": 0,
                    "best_match_score": 0.0,
                },
            )
        else:
            self.add_node(canonical_id, "canonical_skill", _display_skill_label(canonical_key), meta={})

        node = self.nodes[canonical_id]
        node.meta = _merge_meta(
            node.meta,
            {"raw_labels": [raw_text], "sources": [source_kind]},
        )

        if source_kind == "job_requirement":
            node.meta["job_mentions"] = int(node.meta.get("job_mentions", 0) or 0) + 1
        elif source_kind == "resume_skill":
            node.meta["resume_mentions"] = int(node.meta.get("resume_mentions", 0) or 0) + 1
        else:
            node.meta["evidence_mentions"] = int(node.meta.get("evidence_mentions", 0) or 0) + 1

        self.add_edge(source_id, canonical_id, "canonicalizes_to", weight=1.0, confidence=1.0)
        return canonical_id

    def add_job_root(self, job: JobDetails) -> Tuple[str, str]:
        job_id = "job_0"
        company_id = "company_target_0"

        self.add_node(
            job_id,
            "job",
            job.job_title,
            meta={
                "company": job.company_name,
                "job_purpose": _shorten(job.job_purpose, 180),
                "company_details": _shorten(job.company_details, 240),
                "keywords_count": len(job.keywords),
                "requirements_count": len(job.job_duties_and_responsibilities)
                + len(job.required_qualifications)
                + len(job.preferred_qualifications),
                "matched_requirement_ids": [],
                "matched_canonical_skill_ids": [],
                "match_count": 0,
            },
        )

        self.add_node(
            company_id,
            "company",
            job.company_name,
            meta={
                "kind": "target_company",
                "company_details": _shorten(job.company_details, 240),
            },
        )

        self.add_edge(job_id, company_id, "target_company", weight=1.0, confidence=1.0)
        return job_id, company_id

    def add_resume_root(self, resume: Resume) -> str:
        resume_id = "resume_profile_0"
        self.add_node(
            resume_id,
            "person",
            resume.name,
            meta={
                "kind": "resume_profile",
                "candidate_name": resume.name,
                "summary": _shorten(resume.summary or "", 180) if resume.summary else None,
                "phone": resume.phone,
                "email": resume.email,
                "matched_requirement_ids": [],
                "matched_canonical_skill_ids": [],
                "match_count": 0,
            },
        )
        return resume_id

    def add_summary_node(self, resume_id: str, summary: str) -> Optional[str]:
        if not summary:
            return None

        summary_id = "summary_0"
        self.add_node(
            summary_id,
            "keyword",
            _shorten(summary, 110),
            meta={
                "kind": "summary",
                "full_text": summary,
                "parent_id": resume_id,
                "matched_requirement_ids": [],
                "matched_canonical_skill_ids": [],
                "best_match_score": 0.0,
                "match_count": 0,
            },
        )
        self.add_edge(resume_id, summary_id, "has_summary", weight=1.0, confidence=1.0)
        return summary_id

    def add_contact_nodes(self, resume_id: str, resume: Resume) -> None:
        contact_items: List[Tuple[str, str]] = [
            ("email", resume.email),
            ("phone", resume.phone),
        ]

        media = resume.media
        if media.linkedin:
            contact_items.append(("linkedin", str(media.linkedin)))
        if media.github:
            contact_items.append(("github", str(media.github)))
        if media.medium:
            contact_items.append(("medium", str(media.medium)))
        if media.devpost:
            contact_items.append(("devpost", str(media.devpost)))

        for index, (kind, value) in enumerate(contact_items):
            node_id = f"contact_{kind}_{index}"
            label = kind.capitalize()
            self.add_node(
                node_id,
                "keyword",
                label,
                meta={
                    "kind": "contact",
                    "value": value,
                    "order": index,
                },
            )
            self.add_edge(resume_id, node_id, "has_contact", weight=1.0, confidence=1.0)

    def add_requirement_node(
        self,
        job_id: str,
        raw_text: str,
        category: str,
        order: int,
    ) -> Dict[str, Any]:
        normalized = _normalize_text(raw_text)
        req_id = f"job_req_{category}_{order}_{_slugify(raw_text)}"

        self.add_node(
            req_id,
            "keyword",
            _shorten(raw_text, 95),
            meta={
                "kind": "job_requirement",
                "category": category,
                "raw_text": raw_text,
                "normalized_text": normalized,
                "order": order,
                "match_count": 0,
                "best_match_score": 0.0,
                "matched_evidence_ids": [],
                "matched_canonical_skill_ids": [],
            },
        )

        relation_by_category = {
            "keyword": "requires",
            "duty": "covers",
            "required_qualification": "requires",
            "preferred_qualification": "prefers",
        }
        self.add_edge(
            job_id,
            req_id,
            relation_by_category.get(category, "includes"),
            weight=1.0,
            confidence=1.0,
        )

        canonical_id = None
        if _looks_like_skill_phrase(raw_text):
            canonical_id = self.add_canonical_skill(
                raw_text=raw_text,
                source_kind="job_requirement",
                source_id=req_id,
            )
            if canonical_id:
                self.add_edge(req_id, canonical_id, "canonicalizes_to", weight=1.0, confidence=1.0)

        spec = {
            "id": req_id,
            "text": raw_text,
            "category": category,
            "canonical_id": canonical_id,
        }
        self.job_requirement_nodes.append(spec)
        return spec

    def add_company_node(self, company_name: str, meta: Optional[Dict[str, Any]] = None) -> str:
        company_id = f"company_{_slugify(company_name)}"
        self.add_node(
            company_id,
            "company",
            company_name,
            meta=meta or {},
        )
        return company_id

    def add_skill_group_and_terms(
        self,
        resume_id: str,
        section_name: str,
        section_index: int,
        skills: List[str],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        group_id = f"resume_skill_group_{section_index}"
        self.add_node(
            group_id,
            "person_skill",
            _shorten(section_name, 80),
            meta={
                "kind": "skill_group",
                "section_name": section_name,
                "order": section_index,
                "source": "resume.skills_section",
                "skill_count": len(skills),
            },
        )
        self.add_edge(resume_id, group_id, "has_skill_group", weight=1.0, confidence=1.0)

        terms: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for skill_index, skill in enumerate(skills):
            normalized = _normalize_text(skill)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            skill_id = f"resume_skill_{section_index}_{skill_index}_{_slugify(skill)}"
            canonical_id = self.add_canonical_skill(
                raw_text=skill,
                source_kind="resume_skill",
                source_id=skill_id,
            )

            self.add_node(
                skill_id,
                "person_skill",
                _shorten(skill, 80),
                meta={
                    "kind": "resume_skill",
                    "source": "resume.skills_section",
                    "section_name": section_name,
                    "section_index": section_index,
                    "raw_label": skill,
                    "normalized_label": normalized,
                    "canonical_id": canonical_id,
                    "matched_requirement_ids": [],
                    "matched_canonical_skill_ids": [],
                    "best_match_score": 0.0,
                    "match_count": 0,
                },
            )
            self.add_edge(group_id, skill_id, "contains", weight=1.0, confidence=1.0)
            terms.append(
                {
                    "id": skill_id,
                    "text": skill,
                    "canonical_id": canonical_id,
                    "kind": "resume_skill",
                    "parent_id": group_id,
                }
            )

        return group_id, terms

    def add_evidence_parent(
        self,
        resume_id: str,
        parent_kind: str,
        parent_id: str,
        parent_label: str,
        parent_meta: Dict[str, Any],
        child_texts: List[str],
        child_relation: str,
        child_kind: str,
        company_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if company_name:
            parent_meta = _merge_meta(parent_meta, {"company": company_name})

        self.add_node(parent_id, parent_kind, parent_label, meta=parent_meta)

        relation = {
            "experience": "has_experience",
            "project": "has_project",
            "education": "has_education",
            "certification": "has_certification",
            "keyword": "has_achievement",
            "summary": "has_summary",
        }.get(parent_kind, "contains")

        self.add_edge(resume_id, parent_id, relation, weight=1.0, confidence=1.0)

        leaves: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for index, text in enumerate(child_texts):
            normalized = _normalize_text(text)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            leaf_id = f"{parent_id}_{child_kind}_{index}_{_slugify(text)}"
            self.add_node(
                leaf_id,
                "keyword",
                _shorten(text, 95),
                meta={
                    "kind": child_kind,
                    "parent_id": parent_id,
                    "parent_kind": parent_kind,
                    "full_text": text,
                    "normalized_text": normalized,
                    "best_match_score": 0.0,
                    "match_count": 0,
                    "matched_requirement_ids": [],
                    "matched_canonical_skill_ids": [],
                },
            )
            self.add_edge(parent_id, leaf_id, child_relation, weight=1.0, confidence=1.0)
            leaves.append(
                {
                    "id": leaf_id,
                    "text": text,
                    "parent_id": parent_id,
                    "parent_kind": parent_kind,
                    "canonical_id": None,
                    "kind": child_kind,
                }
            )

        return leaves

    def match_requirement_and_skill_graph(
        self,
        evidence_id: str,
        evidence_text: str,
        parent_id: Optional[str] = None,
    ) -> None:
        evidence_norm = _normalize_text(evidence_text)
        if not evidence_norm:
            return

        evidence_node = self.nodes[evidence_id]

        # Match against job requirements
        requirement_scores: List[Tuple[float, Dict[str, Any]]] = []
        for req in self.job_requirement_nodes:
            req_text = req["text"]
            score = _score_match(evidence_text, req_text)
            threshold = _threshold_for_term(req_text)
            if score >= threshold:
                requirement_scores.append((score, req))

        requirement_scores.sort(key=lambda x: x[0], reverse=True)
        requirement_scores = requirement_scores[:5]

        for score, req in requirement_scores:
            req_id = req["id"]
            relation = _relation_for_score(score)

            self.add_edge(
                evidence_id,
                req_id,
                relation,
                weight=round(score, 3),
                confidence=round(score, 3),
                evidence=_shorten(evidence_text, 160),
                provenance="rule",
            )

            req_node = self.nodes[req_id]
            req_node.meta = _merge_meta(req_node.meta, None)
            req_node.meta["match_count"] = int(req_node.meta.get("match_count", 0) or 0) + 1
            req_node.meta["best_match_score"] = max(
                float(req_node.meta.get("best_match_score", 0.0) or 0.0),
                round(score, 3),
            )
            req_node.meta["matched_evidence_ids"] = list(
                dict.fromkeys((req_node.meta.get("matched_evidence_ids", []) or []) + [evidence_id])
            )

            evidence_node.meta = _merge_meta(evidence_node.meta, None)
            evidence_node.meta["match_count"] = int(evidence_node.meta.get("match_count", 0) or 0) + 1
            evidence_node.meta["best_match_score"] = max(
                float(evidence_node.meta.get("best_match_score", 0.0) or 0.0),
                round(score, 3),
            )
            evidence_node.meta["matched_requirement_ids"] = list(
                dict.fromkeys((evidence_node.meta.get("matched_requirement_ids", []) or []) + [req_id])
            )

            canonical_id = req.get("canonical_id")
            if canonical_id:
                self.add_edge(
                    evidence_id,
                    canonical_id,
                    "supports",
                    weight=round(score, 3),
                    confidence=round(score, 3),
                    evidence=_shorten(evidence_text, 160),
                    provenance="rule",
                )
                evidence_node.meta["matched_canonical_skill_ids"] = list(
                    dict.fromkeys((evidence_node.meta.get("matched_canonical_skill_ids", []) or []) + [canonical_id])
                )
                req_node.meta["matched_canonical_skill_ids"] = list(
                    dict.fromkeys((req_node.meta.get("matched_canonical_skill_ids", []) or []) + [canonical_id])
                )
                self.parent_canonical_matches[parent_id or evidence_id].add(canonical_id)

        # Match against canonical skill hubs
        canonical_scores: List[Tuple[float, str]] = []
        for canonical_key, canonical_id in self.canonical_skill_nodes.items():
            canonical_label = _display_skill_label(canonical_key)
            score = _score_match(evidence_text, canonical_label)
            if score >= _threshold_for_term(canonical_label):
                canonical_scores.append((score, canonical_id))

        canonical_scores.sort(key=lambda x: x[0], reverse=True)
        canonical_scores = canonical_scores[:5]

        for score, canonical_id in canonical_scores:
            self.add_edge(
                evidence_id,
                canonical_id,
                "supports",
                weight=round(score, 3),
                confidence=round(score, 3),
                evidence=_shorten(evidence_text, 160),
                provenance="rule",
            )
            evidence_node.meta["matched_canonical_skill_ids"] = list(
                dict.fromkeys((evidence_node.meta.get("matched_canonical_skill_ids", []) or []) + [canonical_id])
            )
            evidence_node.meta["best_match_score"] = max(
                float(evidence_node.meta.get("best_match_score", 0.0) or 0.0),
                round(score, 3),
            )
            canonical_node = self.nodes[canonical_id]
            canonical_node.meta["evidence_mentions"] = int(canonical_node.meta.get("evidence_mentions", 0) or 0) + 1
            canonical_node.meta["best_match_score"] = max(
                float(canonical_node.meta.get("best_match_score", 0.0) or 0.0),
                round(score, 3),
            )
            self.parent_canonical_matches[parent_id or evidence_id].add(canonical_id)

        # Parent aggregation
        if parent_id and parent_id in self.nodes:
            parent_node = self.nodes[parent_id]
            parent_node.meta["best_match_score"] = max(
                float(parent_node.meta.get("best_match_score", 0.0) or 0.0),
                float(evidence_node.meta.get("best_match_score", 0.0) or 0.0),
            )
            parent_node.meta["matched_requirement_ids"] = list(
                dict.fromkeys((parent_node.meta.get("matched_requirement_ids", []) or []) + (evidence_node.meta.get("matched_requirement_ids", []) or []))
            )
            parent_node.meta["matched_canonical_skill_ids"] = list(
                dict.fromkeys((parent_node.meta.get("matched_canonical_skill_ids", []) or []) + (evidence_node.meta.get("matched_canonical_skill_ids", []) or []))
            )

    def add_parent_semantic_edges(self) -> None:
        for parent_id, canonical_ids in self.parent_canonical_matches.items():
            if parent_id not in self.nodes:
                continue
            parent_kind = self.nodes[parent_id].meta.get("kind", "")
            relation = _parent_semantic_relation(parent_kind)
            for canonical_id in canonical_ids:
                self.add_edge(
                    parent_id,
                    canonical_id,
                    relation,
                    weight=0.85,
                    confidence=0.85,
                    provenance="rule",
                )

    def finalize(self) -> KnowledgeGraph:
        self.add_parent_semantic_edges()

        nodes = sorted(self.nodes.values(), key=lambda n: n.id)
        edges = sorted(self.edges, key=lambda e: (e.source, e.target, e.relation))

        # Aggregate graph-level metadata
        graph_meta = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "canonical_skill_count": len(self.canonical_skill_nodes),
            "job_requirement_count": len(self.job_requirement_nodes),
        }

        return KnowledgeGraph(nodes=nodes, edges=edges, meta=graph_meta)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def build_knowledge_graph(job: JobDetails, resume: Resume) -> KnowledgeGraph:
    builder = _KnowledgeGraphBuilder()

    resume_id = builder.add_resume_root(resume)
    job_id, target_company_id = builder.add_job_root(job)

    builder.add_edge(resume_id, job_id, "applied_for", weight=1.0, confidence=1.0)

    # Resume-level nodes
    if resume.summary:
        summary_id = builder.add_summary_node(resume_id, resume.summary)
        if summary_id:
            builder.match_requirement_and_skill_graph(summary_id, resume.summary, parent_id=summary_id)

    builder.add_contact_nodes(resume_id, resume)

    # Job requirement nodes
    seen_job_terms: set[Tuple[str, str]] = set()

    for i, kw in enumerate(job.keywords):
        key = ("keyword", _normalize_text(kw))
        if key[1] and key not in seen_job_terms:
            seen_job_terms.add(key)
            builder.add_requirement_node(job_id=job_id, raw_text=kw, category="keyword", order=i)

    for i, duty in enumerate(job.job_duties_and_responsibilities):
        key = ("duty", _normalize_text(duty))
        if key[1] and key not in seen_job_terms:
            seen_job_terms.add(key)
            builder.add_requirement_node(job_id=job_id, raw_text=duty, category="duty", order=i)

    for i, rq in enumerate(job.required_qualifications):
        key = ("required_qualification", _normalize_text(rq))
        if key[1] and key not in seen_job_terms:
            seen_job_terms.add(key)
            builder.add_requirement_node(job_id=job_id, raw_text=rq, category="required_qualification", order=i)

    for i, pq in enumerate(job.preferred_qualifications):
        key = ("preferred_qualification", _normalize_text(pq))
        if key[1] and key not in seen_job_terms:
            seen_job_terms.add(key)
            builder.add_requirement_node(job_id=job_id, raw_text=pq, category="preferred_qualification", order=i)

    # Resume skill subgraph
    all_resume_skill_terms: List[Dict[str, Any]] = []
    for section_index, section in enumerate(resume.skills_section):
        _, skill_terms = builder.add_skill_group_and_terms(
            resume_id=resume_id,
            section_name=section.name,
            section_index=section_index,
            skills=section.skills,
        )
        all_resume_skill_terms.extend(skill_terms)

    # Direct alignment between resume skill nodes and job requirement nodes
    for skill_term in all_resume_skill_terms:
        skill_canonical = skill_term.get("canonical_id")
        if not skill_canonical:
            continue

        for req in builder.job_requirement_nodes:
            if req.get("canonical_id") and req["canonical_id"] == skill_canonical:
                builder.add_edge(
                    skill_term["id"],
                    req["id"],
                    "aligns_with",
                    weight=1.0,
                    confidence=1.0,
                    provenance="rule",
                )

    # Work experience
    company_nodes: Dict[str, str] = {}
    job_company_norm = _normalize_text(job.company_name)

    for i, exp in enumerate(resume.work_experience_section):
        exp_id = f"exp_{i}"
        exp_label = f"{exp.role} @ {exp.company}"

        company_norm = _normalize_text(exp.company)
        company_id = company_nodes.get(company_norm)
        if not company_id:
            company_id = builder.add_company_node(
                exp.company,
                meta={
                    "kind": "employer",
                    "normalized_name": company_norm,
                    "source": "resume.work_experience_section",
                },
            )
            company_nodes[company_norm] = company_id

        exp_meta = {
            "kind": "experience",
            "company": exp.company,
            "location": exp.location,
            "from_date": exp.from_date,
            "to_date": exp.to_date,
            "bullet_count": len(exp.description),
            "best_match_score": 0.0,
            "match_count": 0,
            "matched_requirement_ids": [],
            "matched_canonical_skill_ids": [],
        }

        bullet_leaves = builder.add_evidence_parent(
            resume_id=resume_id,
            parent_kind="experience",
            parent_id=exp_id,
            parent_label=exp_label,
            parent_meta=exp_meta,
            child_texts=exp.description,
            child_relation="contains_bullet",
            child_kind="experience_bullet",
            company_name=exp.company,
        )

        builder.add_edge(exp_id, company_id, "worked_at", weight=1.0, confidence=1.0)

        # If employer matches target company, surface it explicitly
        if company_norm == job_company_norm:
            builder.add_edge(company_id, target_company_id, "same_company", weight=1.0, confidence=1.0)
        else:
            sim = _score_match(exp.company, job.company_name)
            if sim >= 0.75:
                builder.add_edge(
                    company_id,
                    target_company_id,
                    "company_similarity",
                    weight=round(sim, 3),
                    confidence=round(sim, 3),
                    provenance="rule",
                )

        # Match the experience header and bullets
        builder.match_requirement_and_skill_graph(
            evidence_id=exp_id,
            evidence_text=" ".join(
                [exp.role, exp.company, exp.location, exp.from_date, exp.to_date, " ".join(exp.description)]
            ),
            parent_id=exp_id,
        )
        for leaf in bullet_leaves:
            builder.match_requirement_and_skill_graph(
                evidence_id=leaf["id"],
                evidence_text=leaf["text"],
                parent_id=exp_id,
            )

    # Projects
    for i, project in enumerate(resume.projects_section):
        project_id = f"project_{i}"
        project_label = project.name

        project_meta = {
            "kind": "project",
            "project_type": project.type,
            "link": project.link,
            "from_date": project.from_date,
            "to_date": project.to_date,
            "resource_count": len(project.resources or []),
            "bullet_count": len(project.description),
            "best_match_score": 0.0,
            "match_count": 0,
            "matched_requirement_ids": [],
            "matched_canonical_skill_ids": [],
        }

        project_bullets = builder.add_evidence_parent(
            resume_id=resume_id,
            parent_kind="project",
            parent_id=project_id,
            parent_label=project_label,
            parent_meta=project_meta,
            child_texts=project.description,
            child_relation="contains_bullet",
            child_kind="project_bullet",
        )

        builder.match_requirement_and_skill_graph(
            evidence_id=project_id,
            evidence_text=" ".join(
                [
                    project.name,
                    project.type or "",
                    project.link or "",
                    " ".join(project.description),
                ]
            ),
            parent_id=project_id,
        )
        for leaf in project_bullets:
            builder.match_requirement_and_skill_graph(
                evidence_id=leaf["id"],
                evidence_text=leaf["text"],
                parent_id=project_id,
            )

    # Education
    for i, edu in enumerate(resume.education_section):
        edu_id = f"edu_{i}"
        edu_label = edu.degree

        edu_meta = {
            "kind": "education",
            "university": edu.university,
            "from_date": edu.from_date,
            "to_date": edu.to_date,
            "course_count": len(edu.courses),
            "best_match_score": 0.0,
            "match_count": 0,
            "matched_requirement_ids": [],
            "matched_canonical_skill_ids": [],
        }

        course_leaves = builder.add_evidence_parent(
            resume_id=resume_id,
            parent_kind="education",
            parent_id=edu_id,
            parent_label=edu_label,
            parent_meta=edu_meta,
            child_texts=edu.courses,
            child_relation="covers_course",
            child_kind="education_course",
        )

        builder.match_requirement_and_skill_graph(
            evidence_id=edu_id,
            evidence_text=" ".join([edu.degree, edu.university, edu.from_date, edu.to_date, " ".join(edu.courses)]),
            parent_id=edu_id,
        )
        for leaf in course_leaves:
            builder.match_requirement_and_skill_graph(
                evidence_id=leaf["id"],
                evidence_text=leaf["text"],
                parent_id=edu_id,
            )

    # Certifications
    for i, cert in enumerate(resume.certifications_section):
        cert_id = f"cert_{i}"
        cert_label = cert.name

        cert_meta = {
            "kind": "certification",
            "issuer": cert.by,
            "link": cert.link,
            "best_match_score": 0.0,
            "match_count": 0,
            "matched_requirement_ids": [],
            "matched_canonical_skill_ids": [],
        }

        builder.add_node(cert_id, "certification", cert_label, meta=cert_meta)
        builder.add_edge(resume_id, cert_id, "has_certification", weight=1.0, confidence=1.0)

        builder.match_requirement_and_skill_graph(
            evidence_id=cert_id,
            evidence_text=" ".join([cert.name, cert.by, cert.link]),
            parent_id=cert_id,
        )

    # Achievements
    for i, achievement in enumerate(resume.achievements_section):
        ach_id = f"achievement_{i}"
        ach_label = _shorten(achievement, 95)

        builder.add_node(
            ach_id,
            "keyword",
            ach_label,
            meta={
                "kind": "achievement",
                "full_text": achievement,
                "order": i,
                "best_match_score": 0.0,
                "match_count": 0,
                "matched_requirement_ids": [],
                "matched_canonical_skill_ids": [],
            },
        )
        builder.add_edge(resume_id, ach_id, "has_achievement", weight=1.0, confidence=1.0)
        builder.match_requirement_and_skill_graph(
            evidence_id=ach_id,
            evidence_text=achievement,
            parent_id=ach_id,
        )

    return builder.finalize()