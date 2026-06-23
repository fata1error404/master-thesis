from __future__ import annotations

import json
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Any

import jinja2


MODULE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MODULE_DIR.parent
DEFAULT_TEMPLATE_DIR = MODULE_DIR
DEFAULT_TEMPLATE_NAME = "resume.tex.jinja"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "outputs"
LATEX_ARTIFACT_SUFFIXES = (
    ".aux",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".pdf",
    ".synctex.gz",
    ".tex",
    ".xdv",
)
LATEX_EXTRA_ARTIFACTS = ("missfont.log",)


LATEX_ESCAPE_MAP = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\^{}",
    "\\": r"\textbackslash{}",
    "\n": r"\newline{}",
    "-": r"{-}",
    "\xA0": "~",
    "[": r"{[}",
    "]": r"{]}",
}


def latex_escape(text: str) -> str:
    return "".join(LATEX_ESCAPE_MAP.get(ch, ch) for ch in text)


def deep_escape(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: deep_escape(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_escape(x) for x in obj]
    if isinstance(obj, str):
        return latex_escape(obj)
    return obj


def render_tex(
    json_path: str | Path,
    template_dir: str | Path = DEFAULT_TEMPLATE_DIR,
    tex_path: str | Path | None = None,
    template_name: str = DEFAULT_TEMPLATE_NAME,
) -> Path:
    json_path = Path(json_path)
    template_dir = Path(template_dir)

    if tex_path is None:
        tex_path = DEFAULT_OUTPUT_DIR / "resume.tex"
    tex_path = Path(tex_path)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    if not template_dir.is_dir():
        raise NotADirectoryError(f"Template path is not a directory: {template_dir}")

    template_path = template_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data = deep_escape(data)

    if isinstance(data, dict):
        data.setdefault("keywords", "")
        data.setdefault("media", {})
        data.setdefault("work_experience_section", [])
        data.setdefault("education_section", [])
        data.setdefault("skills_section", [])
        data.setdefault("projects_section", [])
        data.setdefault("certifications_section", [])
        data.setdefault("achievements_section", [])

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=jinja2.StrictUndefined,
    )

    template = env.get_template(template_name)

    if isinstance(data, dict):
        tex = template.render(**data)
    else:
        tex = template.render(json_resume=data)

    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")

    return tex_path


def compile_pdf(
    tex_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    tex_path = Path(tex_path)
    output_dir = Path(output_dir)

    print(f"[compile_pdf] cwd={Path.cwd()}", flush=True)
    print(f"[compile_pdf] tex_path={tex_path}", flush=True)
    print(f"[compile_pdf] output_dir={output_dir}", flush=True)
    print(f"[compile_pdf] tex_path.exists()={tex_path.exists()}", flush=True)

    if not tex_path.exists():
        raise FileNotFoundError(f"TeX file not found: {tex_path}")

    print(f"[compile_pdf] tex_path.resolve()={tex_path.resolve()}", flush=True)
    print(f"[compile_pdf] tex_path.parent={tex_path.parent}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[compile_pdf] output_dir.exists()={output_dir.exists()}", flush=True)
    print(f"[compile_pdf] output_dir.resolve()={output_dir.resolve()}", flush=True)

    command = [
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        str(output_dir),
        str(tex_path),
    ]

    print(f"[compile_pdf] command={' '.join(command)}", flush=True)

    try:
        result = None
        for _ in range(2):
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )

        assert result is not None
        print(f"[compile_pdf] returncode={result.returncode}", flush=True)

        if result.stdout:
            print("[compile_pdf] stdout:", flush=True)
            print(result.stdout, flush=True)

        if result.stderr:
            print("[compile_pdf] stderr:", flush=True)
            print(result.stderr, flush=True)

    except FileNotFoundError:
        print("[compile_pdf] ERROR: xelatex executable not found", flush=True)
        raise

    except subprocess.CalledProcessError as e:
        print(f"[compile_pdf] ERROR: xelatex failed with return code {e.returncode}", flush=True)

        if e.stdout:
            print("[compile_pdf] stdout:", flush=True)
            print(e.stdout, flush=True)

        if e.stderr:
            print("[compile_pdf] stderr:", flush=True)
            print(e.stderr, flush=True)

        log_path = output_dir / f"{tex_path.stem}.log"
        if log_path.exists():
            print(f"[compile_pdf] LaTeX log file: {log_path}", flush=True)
            print("[compile_pdf] --- Begin .log file ---", flush=True)
            print(log_path.read_text(encoding="utf-8", errors="replace"), flush=True)
            print("[compile_pdf] --- End .log file ---", flush=True)

        raise

    pdf_path = output_dir / f"{tex_path.stem}.pdf"

    print(f"[compile_pdf] expected pdf_path={pdf_path}", flush=True)
    print(f"[compile_pdf] pdf_path.exists()={pdf_path.exists()}", flush=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF was not created: {pdf_path}")

    print(f"[compile_pdf] pdf_path.resolve()={pdf_path.resolve()}", flush=True)
    print(f"[compile_pdf] pdf_size={pdf_path.stat().st_size} bytes", flush=True)

    return pdf_path


def cleanup_latex_artifacts(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
) -> None:
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir) if output_dir is not None else pdf_path.parent

    for suffix in LATEX_ARTIFACT_SUFFIXES:
        (output_dir / f"{pdf_path.stem}{suffix}").unlink(missing_ok=True)

    for file_name in LATEX_EXTRA_ARTIFACTS:
        (output_dir / file_name).unlink(missing_ok=True)


def json_to_pdf(
    json_path: str | Path,
    template_dir: str | Path = DEFAULT_TEMPLATE_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    template_name: str = DEFAULT_TEMPLATE_NAME,
    output_stem: str = "resume",
    write_overleaf_zip: bool = True,
) -> Path:
    output_dir = Path(output_dir)
    tex_path = output_dir / f"{output_stem}.tex"

    rendered_tex_path = render_tex(
        json_path=json_path,
        template_dir=template_dir,
        tex_path=tex_path,
        template_name=template_name,
    )

    cls_path = Path(template_dir) / "resume.cls"
    staged_cls_path = output_dir / "resume.cls"

    if not cls_path.exists():
        raise FileNotFoundError(f"LaTeX class file not found: {cls_path}")

    if cls_path.resolve() != staged_cls_path.resolve():
        shutil.copy2(cls_path, staged_cls_path)

    if write_overleaf_zip:
        zip_path = output_dir / "overleaf.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(rendered_tex_path, arcname="resume.tex")
            zipf.write(staged_cls_path, arcname="resume.cls")

    # return rendered_tex_path
    return compile_pdf(tex_path=rendered_tex_path, output_dir=output_dir)
