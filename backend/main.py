from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()


class TailorRequest(BaseModel):
    resume_text: str
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
        result = f"Tailored resume for: {request.job_description[:50]}..."
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}