import time
import json
import asyncio
import base64
import re
import copy
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict
from uuid import uuid4

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from llm.context_builder import introduce_context
from llm.job_details_extractor import extract_job_details
from llm.resume_extractor import extract_resume, postprocess_extracted_resume
from llm.rag_retriever import retrieve_rag_context
from llm.knowledge_graph_builder import build_knowledge_graph
from llm.resume_builder import build_resume
from llm.metric_job_alignment import compute_job_alignment
from llm.metric_content_preservation import compute_content_preservation
from llm.metric_structural_validity import compute_structural_validity
from llm.metric_resume_flow import compute_resume_flow_metrics
from latex.json2pdf import cleanup_latex_artifacts, json_to_pdf

@dataclass
class PipelineState:
    job_description: str
    job_context: str | None = None
    job_details: Dict[str, Any] | None = None
    resume_original_data: Dict[str, Any] | None = None
    resume_tailored_data: Dict[str, Any] | None = None
    rag_context: Dict[str, Any] | None = None
    knowledge_graph: Dict[str, Any] | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    embedding_model = OpenAIEmbeddings()

    app.state.resume_vector_db = Chroma(
        persist_directory="/app/database",
        embedding_function=embedding_model
    )

    yield

app = FastAPI(lifespan=lifespan)

class TailorRequest(BaseModel):
    resume_file_id: str
    job_description: str
    enable_rag: bool = True
    enable_knowledge_graph: bool = True
    enable_agent_mode: bool = False
    agent_evidence: Dict[str, Any] | None = None


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = "outputs"
ENABLE_AGENT_MISSING_INFO_QUESTIONS = False

BASE_DIR = Path(__file__).parent
_next_dir = BASE_DIR / ".next"
public_dir = BASE_DIR / "public"
static_dir = _next_dir / "static"

if static_dir.exists():
    app.mount("/_next/static", StaticFiles(directory=str(static_dir)), name="static")
if public_dir.exists():
    app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")


def open_file(file_name: str):
    with open(file_name, "r", encoding="utf-8") as f:
        return json.load(f)


def read_pdf_text(file_name: str) -> str:
    try:
        import fitz
    except Exception:
        return ""

    pdf_path = Path(file_name)
    if not pdf_path.exists():
        return ""

    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    resume_text = "\n\n".join(pages_text).strip()
    resume_text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", resume_text)
    resume_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]+", " ", resume_text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in resume_text.split("\n")]
    return "\n".join(lines)


def _text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
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


def _agent_item_key(item: Dict[str, Any], fields: list[str]) -> str:
    parts = []
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#./-]+", " ", value.lower())).strip())
    return "::".join(parts) if parts else str(uuid4())


def _agent_tokens(text: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#]+", str(text or "").lower())
        if len(token) >= 3
    }


def _job_tokens(job_details: Dict[str, Any] | None) -> set[str]:
    if not job_details:
        return set()
    generic = {
        "and", "the", "for", "with", "you", "are", "our", "will", "that", "this",
        "work", "team", "role", "experience", "strong", "using", "build",
    }
    return {
        token
        for token in _agent_tokens(" ".join(_text_values(job_details)))
        if token not in generic
    }


def _agent_relevance_score(value: Any, job_details: Dict[str, Any] | None) -> int:
    return len(_agent_tokens(" ".join(_text_values(value))) & _job_tokens(job_details))


def _agent_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _has_feature_evidence(text: str) -> bool:
    normalized = _normalize_compare_text(text)
    return any(
        term in normalized
        for term in (
            "implemented",
            "built",
            "developed",
            "created",
            "designed",
            "engineered",
            "integrated",
            "dashboard",
            "interface",
            "component",
            "page",
            "view",
            "form",
            "api",
            "bot",
            "pipeline",
            "model",
            "system",
        )
    )


def _has_impact_evidence(text: str) -> bool:
    normalized = _normalize_compare_text(text)
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:%|x|ms|sec|seconds?|users?|requests?|pages?|components?|apis?|models?)\b", normalized):
        return True
    return any(
        term in normalized
        for term in (
            "improved",
            "increased",
            "reduced",
            "optimized",
            "accelerated",
            "faster",
            "accuracy",
            "performance",
            "latency",
            "conversion",
            "engagement",
            "maintainability",
            "reliability",
            "usability",
        )
    )


def _has_collaboration_evidence(text: str) -> bool:
    normalized = _normalize_compare_text(text)
    return any(
        term in normalized
        for term in (
            "collaborated",
            "communicated",
            "coordinated",
            "worked with",
            "partnered",
            "team",
            "teammates",
            "stakeholders",
            "designers",
            "users",
            "clients",
            "cross-functional",
            "led",
            "mentored",
        )
    )


def build_agent_question_plan(
    resume_data: Dict[str, Any] | None,
    job_details: Dict[str, Any] | None,
    max_questions: int | None = None,
) -> Dict[str, Any]:
    resume_data = resume_data or {}
    questions: list[Dict[str, Any]] = []

    def add_question(
        *,
        question_id: str,
        stage: str,
        target_section: str,
        target_item_key: str,
        target_field: str,
        question: str,
        context: str = "",
        priority: int = 0,
    ) -> None:
        if any(q["question_id"] == question_id for q in questions):
            return
        questions.append({
            "question_id": question_id,
            "stage": stage,
            "target_section": target_section,
            "target_item_key": target_item_key,
            "target_field": target_field,
            "question": question,
            "context": context,
            "priority": priority,
        })

    if ENABLE_AGENT_MISSING_INFO_QUESTIONS:
        for index, edu in enumerate(resume_data.get("education_section", []) or []):
            if not isinstance(edu, dict):
                continue
            key = _agent_item_key(edu, ["university", "degree"])
            label = edu.get("university") or "this education entry"
            if _agent_missing(edu.get("degree")):
                add_question(
                    question_id=f"education_{index}_degree",
                    stage="missing_info",
                    target_section="education_section",
                    target_item_key=key,
                    target_field="degree",
                    question=f"What is the exact diploma or degree name for {label}?",
                    context=str(label),
                    priority=95,
                )
            if _agent_missing(edu.get("from_date")) or _agent_missing(edu.get("to_date")):
                add_question(
                    question_id=f"education_{index}_dates",
                    stage="missing_info",
                    target_section="education_section",
                    target_item_key=key,
                    target_field="from_date/to_date",
                    question=f"What were the start and end dates for {label}?",
                    context=str(label),
                    priority=90,
                )

        for section_key, key_fields, label_field in (
            ("work_experience_section", ["company", "role"], "company"),
            ("projects_section", ["name"], "name"),
            ("certifications_section", ["name"], "name"),
        ):
            for index, item in enumerate(resume_data.get(section_key, []) or []):
                if not isinstance(item, dict):
                    continue
                key = _agent_item_key(item, key_fields)
                label = item.get(label_field) or item.get("role") or "this entry"
                if section_key != "certifications_section" and (_agent_missing(item.get("from_date")) or _agent_missing(item.get("to_date"))):
                    add_question(
                        question_id=f"{section_key}_{index}_dates",
                        stage="missing_info",
                        target_section=section_key,
                        target_item_key=key,
                        target_field="from_date/to_date",
                        question=f"What were the start and end dates for {label}?",
                        context=str(label),
                        priority=85,
                    )
                if section_key == "projects_section" and _agent_missing(item.get("link")):
                    add_question(
                        question_id=f"project_{index}_link",
                        stage="missing_info",
                        target_section=section_key,
                        target_item_key=key,
                        target_field="link",
                        question=f"Do you have a GitHub, demo, publication, or project link for {label}?",
                        context=str(label),
                        priority=70,
                    )
                if section_key == "certifications_section" and _agent_missing(item.get("link")):
                    add_question(
                        question_id=f"certification_{index}_link",
                        stage="missing_info",
                        target_section=section_key,
                        target_item_key=key,
                        target_field="link",
                        question=f"Do you have a verification link for {label}?",
                        context=str(label),
                        priority=55,
                    )

    for section_key, key_fields, label_field in (
        ("work_experience_section", ["company", "role"], "company"),
        ("projects_section", ["name"], "name"),
    ):
        ranked_items = []
        for index, item in enumerate(resume_data.get(section_key, []) or []):
            if not isinstance(item, dict):
                continue
            descriptions = [
                bullet for bullet in item.get("description", []) or []
                if isinstance(bullet, str) and bullet.strip() and not _is_award_or_funding_text(bullet)
            ]
            if not descriptions:
                continue
            score = _agent_relevance_score(item, job_details)
            if score <= 0:
                continue
            ranked_items.append((score, index, item, descriptions))

        for score, index, item, descriptions in sorted(ranked_items, reverse=True)[:3]:
            key = _agent_item_key(item, key_fields)
            label = item.get(label_field) or item.get("role") or "this entry"
            context = descriptions[0]
            item_text = " ".join(_text_values(item))
            if not _has_feature_evidence(item_text):
                add_question(
                    question_id=f"{section_key}_{index}_feature",
                    stage="rewrite_evidence",
                    target_section=section_key,
                    target_item_key=key,
                    target_field="description",
                    question=f"For {label}, what exact feature, interface, or technical component did you personally implement?",
                    context=context,
                    priority=60 + min(score, 30),
                )
            if not _has_impact_evidence(item_text):
                add_question(
                    question_id=f"{section_key}_{index}_impact",
                    stage="rewrite_evidence",
                    target_section=section_key,
                    target_item_key=key,
                    target_field="description",
                    question=f"For {label}, was there any measurable result or clear improvement? If not, you can say no.",
                    context=context,
                    priority=58 + min(score, 30),
                )
            if not _has_collaboration_evidence(item_text):
                add_question(
                    question_id=f"{section_key}_{index}_collaboration",
                    stage="rewrite_evidence",
                    target_section=section_key,
                    target_item_key=key,
                    target_field="description",
                    question=f"For {label}, did you collaborate or communicate with teammates, users, designers, or stakeholders?",
                    context=context,
                    priority=52 + min(score, 25),
                )

    selected = sorted(questions, key=lambda q: q["priority"], reverse=True)
    if max_questions is not None:
        selected = selected[:max_questions]
    return {
        "enabled": True,
        "question_count": len(selected),
        "questions": selected,
    }


def _normalize_compare_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _entry_compare_key(entry: Dict[str, Any], fields: list[str]) -> str:
    return "::".join(_normalize_compare_text(entry.get(field)) for field in fields)


def _is_award_or_funding_text(text: Any) -> bool:
    normalized = _normalize_compare_text(text)
    if re.search(r"\$\s*\d", normalized) and any(
        term in normalized
        for term in ("hackathon", "competition", "prize", "winner", "fund", "foundation")
    ):
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
            "competition",
            "award",
            "grant",
        )
    )


def _token_set(text: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", _normalize_compare_text(text)))


def _should_highlight_tailored_bullet(
    tailored_bullet: Any,
    original_entry: Dict[str, Any] | None,
) -> bool:
    if not isinstance(tailored_bullet, str) or not tailored_bullet.strip():
        return False
    if _is_award_or_funding_text(tailored_bullet):
        return False
    if not original_entry:
        return True

    original_bullets = [
        bullet
        for bullet in original_entry.get("description", []) or []
        if isinstance(bullet, str) and bullet.strip()
    ]
    tailored_norm = _normalize_compare_text(tailored_bullet)

    for original_bullet in original_bullets:
        original_norm = _normalize_compare_text(original_bullet)
        if tailored_norm == original_norm or tailored_norm in original_norm or original_norm in tailored_norm:
            return False

    original_text = " ".join(str(value) for value in original_entry.values())
    original_tokens = _token_set(original_text)
    tailored_tokens = {token for token in _token_set(tailored_bullet) if len(token) >= 3}
    if not tailored_tokens:
        return False

    new_tokens = tailored_tokens - original_tokens
    new_token_ratio = len(new_tokens) / max(len(tailored_tokens), 1)

    return len(new_tokens) >= 3 and new_token_ratio >= 0.25


def build_compare_resume_data(
    original_resume: Dict[str, Any] | None,
    tailored_resume: Dict[str, Any] | None,
) -> Dict[str, Any]:
    compare_resume = copy.deepcopy(tailored_resume or {})
    original_resume = original_resume or {}

    original_summary = _normalize_compare_text(original_resume.get("summary"))
    tailored_summary = compare_resume.get("summary")
    if isinstance(tailored_summary, str) and tailored_summary.strip():
        compare_resume["summary"] = {
            "text": tailored_summary,
            "highlight": _normalize_compare_text(tailored_summary) != original_summary,
        }

    section_keys = {
        "work_experience_section": ["company", "role"],
        "projects_section": ["name"],
    }

    for section_key, key_fields in section_keys.items():
        original_items = {
            _entry_compare_key(item, key_fields): item
            for item in original_resume.get(section_key, []) or []
            if isinstance(item, dict)
        }

        for item in compare_resume.get(section_key, []) or []:
            if not isinstance(item, dict):
                continue

            original_item = original_items.get(_entry_compare_key(item, key_fields))
            highlighted_description = []
            for bullet in item.get("description", []) or []:
                highlight = _should_highlight_tailored_bullet(bullet, original_item)
                highlighted_description.append({
                    "text": bullet,
                    "highlight": highlight,
                })
            item["description"] = highlighted_description

    return compare_resume


def write_compare_resume_json(
    original_resume: Dict[str, Any] | None,
    tailored_resume: Dict[str, Any] | None,
    output_dir: str,
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    compare_path = output_path / "resume_tailored_compare.json"
    compare_data = build_compare_resume_data(original_resume, tailored_resume)

    with compare_path.open("w", encoding="utf-8") as f:
        json.dump(compare_data, f, indent=2, ensure_ascii=False)

    return compare_path


@app.get("/")
async def root():
    return {"message": "Hello from backend — API docs at /docs"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    file_id = str(uuid4())

    contents = await file.read()

    with open(f"outputs/{file_id}.pdf", "wb") as f:
        f.write(contents)

    return {"id": file_id}


@app.get("/api/overleaf.zip")
async def overleaf_zip():
    zip_path = Path(OUTPUT_DIR) / "overleaf.zip"

    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Overleaf zip has not been generated yet.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="overleaf.zip",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.post("/api/tailor")
async def tailor(request: TailorRequest):
    async def event_stream():
        generation_start = time.perf_counter()

        state = PipelineState(job_description=request.job_description)

        state = introduce_context(state)

        try:
            state.job_details = await asyncio.to_thread(
                open_file,
                "outputs/job_details.json"
            )

            # state.job_details = await asyncio.to_thread(
            #     extract_job_details,
            #     state.job_description,
            #     OUTPUT_DIR
            # )

            yield json.dumps({
                "type": "job_details",
                "data": state.job_details,
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "job_details_extraction",
                "message": str(e)
            }) + "\n"

        try:
            state.resume_original_data = await asyncio.to_thread(
                extract_resume,
                request.resume_file_id,
                OUTPUT_DIR
            )

            yield json.dumps({
                "type": "resume_original_data",
                "data": state.resume_original_data,
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            try:
                state.resume_original_data = await asyncio.to_thread(
                    open_file,
                    "outputs/resume.json"
                )
                resume_text = await asyncio.to_thread(
                    read_pdf_text,
                    f"outputs/{request.resume_file_id}.pdf",
                )
                state.resume_original_data = postprocess_extracted_resume(
                    state.resume_original_data,
                    resume_text,
                )

                yield json.dumps({
                    "type": "resume_original_data",
                    "data": state.resume_original_data,
                    "meta": {
                        "source": "cached_fallback",
                        "fallback_reason": str(e),
                    },
                }) + "\n"

                await asyncio.sleep(0)

            except Exception as fallback_error:
                yield json.dumps({
                    "type": "error",
                    "step": "resume_details_extraction",
                    "message": str(e),
                    "fallback_message": str(fallback_error),
                }) + "\n"

        if request.enable_agent_mode and not request.agent_evidence:
            try:
                question_plan = await asyncio.to_thread(
                    build_agent_question_plan,
                    state.resume_original_data,
                    state.job_details,
                )

                yield json.dumps({
                    "type": "agent_questions",
                    "data": question_plan,
                }) + "\n"

                if question_plan.get("question_count", 0) > 0:
                    return

            except Exception as e:
                yield json.dumps({
                    "type": "error",
                    "step": "agent_question_planning",
                    "message": str(e)
                }) + "\n"

        try:
            if request.enable_rag:
                vector_db = app.state.resume_vector_db

                state.rag_context = await asyncio.to_thread(
                    retrieve_rag_context,
                    vector_db,
                    state.job_details,
                    8
                )

                rag_data = {
                    "enabled": True,
                    "retrieved_count": state.rag_context.get("retrieved_count", 0),
                }
            else:
                state.rag_context = None
                rag_data = {
                    "enabled": False,
                    "retrieved_count": 0,
                }

            yield json.dumps({
                "type": "rag_context",
                "data": rag_data,
            }) + "\n"

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "rag_retrieval",
                "message": str(e)
            }) + "\n"

        try:
            if request.enable_knowledge_graph:
                from schemas.job_details_schema import JobDetails
                from schemas.resume_schema import Resume

                job_obj = JobDetails(**state.job_details)
                resume_obj = Resume(**state.resume_original_data)

                kg = build_knowledge_graph(job_obj, resume_obj)
                state.knowledge_graph = kg.model_dump()
            else:
                state.knowledge_graph = None

            yield json.dumps({
                "type": "knowledge_graph",
                "data": {
                    "enabled": request.enable_knowledge_graph,
                    "graph": state.knowledge_graph,
                }
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "knowledge_graph_building",
                "message": str(e)
            }) + "\n"

        try:
            state.resume_tailored_data = await asyncio.to_thread(
                build_resume,
                state.job_details,
                state.resume_original_data,
                request.resume_file_id,
                OUTPUT_DIR,
                state.rag_context if request.enable_rag else None,
                state.knowledge_graph if request.enable_knowledge_graph else None,
                request.agent_evidence if request.enable_agent_mode else None,
            )

            yield json.dumps({
                "type": "resume_tailored_data",
                "data": state.resume_tailored_data,
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            try:
                state.resume_tailored_data = await asyncio.to_thread(
                    open_file,
                    "outputs/resume_tailored.json"
                )

                yield json.dumps({
                    "type": "resume_tailored_data",
                    "data": state.resume_tailored_data,
                    "meta": {
                        "source": "cached_fallback",
                        "fallback_reason": str(e),
                    },
                }) + "\n"

                await asyncio.sleep(0)

            except Exception as fallback_error:
                yield json.dumps({
                    "type": "error",
                    "step": "resume_tailoring",
                    "message": str(e),
                    "fallback_message": str(fallback_error),
                }) + "\n"

        try:
            original_pdf_bytes = await asyncio.to_thread(
                lambda: Path("outputs", f"{request.resume_file_id}.pdf").read_bytes()
            )

            original_pdf_base64 = base64.b64encode(original_pdf_bytes).decode("utf-8")

            new_pdf_path = await asyncio.to_thread(
                json_to_pdf,
                "/app/outputs/resume_tailored.json"
            )
            overleaf_zip_url = f"http://localhost:8000/api/overleaf.zip?v={uuid4()}"

            new_pdf_bytes = await asyncio.to_thread(
                new_pdf_path.read_bytes
            )
            await asyncio.to_thread(cleanup_latex_artifacts, new_pdf_path)

            new_pdf_base64 = base64.b64encode(new_pdf_bytes).decode("utf-8")

            compare_json_path = await asyncio.to_thread(
                write_compare_resume_json,
                state.resume_original_data,
                state.resume_tailored_data,
                OUTPUT_DIR,
            )

            compare_pdf_path = await asyncio.to_thread(
                lambda: json_to_pdf(
                    compare_json_path,
                    template_name="resume_compare.tex.jinja",
                    output_stem="resume_compare",
                    write_overleaf_zip=False,
                )
            )

            compare_pdf_bytes = await asyncio.to_thread(
                compare_pdf_path.read_bytes
            )
            await asyncio.to_thread(cleanup_latex_artifacts, compare_pdf_path)

            compare_pdf_base64 = base64.b64encode(compare_pdf_bytes).decode("utf-8")

            yield json.dumps({
                "type": "resume_tailored_pdf",
                "data": {
                    "original_pdf_content_base64": original_pdf_base64,
                    "new_pdf_content_base64": new_pdf_base64,
                    "compare_pdf_content_base64": compare_pdf_base64,
                    "overleaf_zip_url": overleaf_zip_url,
                }
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "pdf_generation",
                "message": str(e)
            }) + "\n"

        try:
            generation_time = time.perf_counter() - generation_start

            job_alignment = await asyncio.to_thread(
                compute_job_alignment,
                state.job_details,
                state.resume_tailored_data,
            )

            temp = await asyncio.to_thread(
                compute_job_alignment,
                state.job_details,
                state.resume_original_data,
            )

            content_preservation = await asyncio.to_thread(
                compute_content_preservation,
                state.job_details,
                state.resume_original_data,
                state.resume_tailored_data,
                state.knowledge_graph,
            )

            structural_validity = await asyncio.to_thread(
                compute_structural_validity,
                state.resume_tailored_data,
            )

            resume_flow = await asyncio.to_thread(
                compute_resume_flow_metrics,
                state.job_details,
                state.resume_original_data,
                state.resume_tailored_data,
            )

            # print(content_preservation["skill_overlap"])
            # print(content_preservation["semantic_similarity"])

            improvement_based_utility = (
                (
                    job_alignment["job_alignment"]
                    - temp["job_alignment"]
                )
                * content_preservation["content_preservation"]
            )

            yield json.dumps({
                "type": "metrics_data",
                "data": {
                    "generation_time": generation_time,
                    "job_alignment": job_alignment,
                    "content_preservation": content_preservation,
                    "improvement_based_utility": {
                        "improvement_based_utility": improvement_based_utility,
                        "temp": temp,
                    },
                    "structural_validity": structural_validity,
                    "resume_flow": resume_flow
                }
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "metrics_calculation",
                "message": str(e)
            }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
