from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from typing import Any, Dict

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm.context_builder import introduce_context
from llm.job_details_extractor import extract_job_details

@dataclass
class PipelineState:
    job_description: str
    job_context: str | None = None
    job_details: Dict[str, Any] | None = None
    resume_data: Dict[str, Any] | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

class TailorRequest(BaseModel):
    resume_text: Optional[str] = ""
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


@app.get("/")
async def root():
    return {"message": "Hello from backend — API docs at /docs"}


@app.post("/api/tailor")
async def tailor(request: TailorRequest):
    try:
        state = PipelineState(job_description=request.job_description)

        state = introduce_context(state)

        details = extract_job_details(
            state.job_description,
            save_path="outputs/job_details.json"
        )

        state.job_details = details

        return state.job_details

    except Exception as e:
        return {"error": str(e)}