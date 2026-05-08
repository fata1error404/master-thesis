from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import jinja2


MODULE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = MODULE_DIR.parent
DEFAULT_TEMPLATE_DIR = MODULE_DIR / "latex"
DEFAULT_TEMPLATE_NAME = "resume.tex.jinja"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "outputs"


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

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data = deep_escape(data)

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
    tex = template.render(**data)

    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tex, encoding="utf-8")

    return tex_path


def compile_pdf(
    tex_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    tex_path = Path(tex_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory",
            str(output_dir),
            str(tex_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return output_dir / f"{tex_path.stem}.pdf"


def json_to_pdf(
    json_path: str | Path,
    template_dir: str | Path = DEFAULT_TEMPLATE_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    template_name: str = DEFAULT_TEMPLATE_NAME,
) -> Path:
    output_dir = Path(output_dir)
    tex_path = output_dir / "resume.tex"

    render_tex(
        json_path=json_path,
        template_dir=template_dir,
        tex_path=tex_path,
        template_name=template_name,
    )

    pdf_path = compile_pdf(tex_path=tex_path, output_dir=output_dir)
    return pdf_path


if __name__ == "__main__":
    json_file = BACKEND_DIR / "outputs" / "resume.json"
    pdf_file = json_to_pdf(json_file)
    print(f"PDF saved to: {pdf_file}")