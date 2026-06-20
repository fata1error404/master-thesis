import time
import json
import asyncio
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict
from uuid import uuid4

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from llm.context_builder import introduce_context
from llm.job_details_extractor import extract_job_details
from llm.resume_extractor import extract_resume
from llm.rag_retriever import retrieve_rag_context
from llm.knowledge_graph_builder import build_knowledge_graph
from llm.resume_builder import build_resume
from llm.metric_job_alignment import compute_job_alignment
from llm.metric_content_preservation import compute_content_preservation
from llm.metric_structural_validity import compute_structural_validity
from llm.metric_resume_flow import compute_resume_flow_metrics
from latex.json2pdf import json_to_pdf

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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = "outputs"

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
                open_file,
                "outputs/resume.json"
            )

            # state.resume_original_data = await asyncio.to_thread(
            #     extract_resume,
            #     request.resume_file_id,
            #     OUTPUT_DIR
            # )

            yield json.dumps({
                "type": "resume_original_data",
                "data": state.resume_original_data,
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "resume_details_extraction",
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
                open_file,
                "outputs/resume_tailored.json"
            )

            # state.resume_tailored_data = await asyncio.to_thread(
            #     build_resume,
            #     state.job_details,
            #     state.resume_original_data,
            #     request.resume_file_id,
            #     OUTPUT_DIR
            # )

            yield json.dumps({
                "type": "resume_tailored_data",
                "data": state.resume_tailored_data,
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "resume_tailoring",
                "message": str(e)
            }) + "\n"

        try:
            original_pdf_bytes = await asyncio.to_thread(
                lambda: Path("outputs", f"{request.resume_file_id}.pdf").read_bytes()
            )

            original_pdf_base64 = base64.b64encode(original_pdf_bytes).decode("utf-8")

            # new_pdf_path = await asyncio.to_thread(
            #     json_to_pdf,
            #     "/app/outputs/resume_tailored.json"
            # )

            new_pdf_bytes = await asyncio.to_thread(
                Path("outputs/resume_tailored.pdf").read_bytes
            )

            new_pdf_base64 = base64.b64encode(new_pdf_bytes).decode("utf-8")

            yield json.dumps({
                "type": "resume_tailored_pdf",
                "data": {
                    "original_pdf_content_base64": original_pdf_base64,
                    "new_pdf_content_base64": new_pdf_base64}
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
