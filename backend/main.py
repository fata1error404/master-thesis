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
from latex.json2pdf import json_to_pdf

@dataclass
class PipelineState:
    job_description: str
    job_context: str | None = None
    job_details: Dict[str, Any] | None = None
    resume_data: Dict[str, Any] | None = None
    rag_context: Dict[str, Any] | None = None 

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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            #     save_path="outputs/job_details.json"
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
            state.resume_data = await asyncio.to_thread(
                open_file,
                "outputs/resume.json"
            )

            # state.resume_data = await asyncio.to_thread(
            #     extract_resume,
            #     request.resume_file_id,
            #     save_path="outputs/resume.json"
            # )

            yield json.dumps({
                "type": "resume_data",
                "data": state.resume_data,
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "resume_details_extraction",
                "message": str(e)
            }) + "\n"

        try:
            # vector_db = app.state.resume_vector_db

            # state.rag_context = await asyncio.to_thread(
            #     retrieve_rag_context,
            #     vector_db,
            #     state.job_details,
            #     8
            # )

            yield json.dumps({
                "type": "rag_context",
                "data": 8,
            }) + "\n"

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "rag_retrieval",
                "message": str(e)
            }) + "\n"

        try:
            # pdf_path = await asyncio.to_thread(
            #     json_to_pdf,
            #     "outputs/resume.json"
            # )

            pdf_bytes = await asyncio.to_thread(
                Path("outputs/CV.pdf").read_bytes
            )

            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            yield json.dumps({
                "type": "new_resume_data",
                "data": {"pdf_content_base64": pdf_base64}
            }) + "\n"

            await asyncio.sleep(0)

        except Exception as e:
            yield json.dumps({
                "type": "error",
                "step": "pdf_generation",
                "message": str(e)
            }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")