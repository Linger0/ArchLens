from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .store import ensure_dir


@dataclass(slots=True)
class SourceMarkdown:
    markdown: str
    parser: str
    image_paths: list[Path]


def available_source_extractors() -> list[str]:
    extractors: list[str] = []
    try:
        import fitz  # type: ignore

        if fitz:
            extractors.append("pymupdf")
    except Exception:
        pass
    if shutil.which("pdftotext"):
        extractors.append("pdftotext")
    try:
        from pypdf import PdfReader  # type: ignore

        if PdfReader:
            extractors.append("pypdf")
    except Exception:
        pass
    return extractors


def convert_source_to_markdown(source_path: Path, assets_dir: Path | None = None) -> SourceMarkdown:
    path = source_path.resolve()
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return SourceMarkdown(path.read_text(encoding="utf-8", errors="ignore"), "local-markdown", [])
    if suffix == ".txt":
        return SourceMarkdown(_wrap_plain_text_as_markdown(path, path.read_text(encoding="utf-8", errors="ignore")), "local-text", [])
    if suffix == ".pdf":
        return _pdf_to_markdown(path, assets_dir)
    raise RuntimeError(
        f"Unsupported local file type: {path.suffix or '<no extension>'}. Supported: .pdf, .md, .markdown, .txt"
    )


def _pdf_to_markdown(pdf_path: Path, assets_dir: Path | None) -> SourceMarkdown:
    errors: list[str] = []
    try:
        result = _pdf_to_markdown_with_pymupdf(pdf_path, assets_dir)
        if result.markdown.strip():
            return result
    except Exception as error:  # noqa: PERF203
        errors.append(f"pymupdf: {error}")

    try:
        text = _extract_pdf_text_with_pdftotext(pdf_path)
        if text:
            return SourceMarkdown(_wrap_plain_text_as_markdown(pdf_path, text), "pdftotext", [])
    except Exception as error:  # noqa: PERF203
        errors.append(f"pdftotext: {error}")

    try:
        text = _extract_pdf_text_with_pypdf(pdf_path)
        if text:
            return SourceMarkdown(_wrap_plain_text_as_markdown(pdf_path, text), "pypdf", [])
    except Exception as error:  # noqa: PERF203
        errors.append(f"pypdf: {error}")

    available = ", ".join(available_source_extractors()) or "none"
    detail = "; ".join(errors) if errors else "no extractor produced text"
    raise RuntimeError(
        "No local PDF extractor produced usable Markdown. Configure MINERU_API_KEY or install PyMuPDF / pdftotext / pypdf. "
        f"Detected local extractors: {available}. Detail: {detail}"
    )


def _pdf_to_markdown_with_pymupdf(pdf_path: Path, assets_dir: Path | None) -> SourceMarkdown:
    import fitz  # type: ignore

    image_paths: list[Path] = []
    sections = [f"# {_title_from_path(pdf_path)}", "", f"> Converted by ArchLens source_to_md at {_timestamp()}.", ""]
    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                sections.extend([f"## Page {page_index}", "", text, ""])

            if assets_dir is not None:
                image_paths.extend(_extract_page_images(document, page, page_index, assets_dir))
                for image_path in image_paths:
                    if image_path.parent == assets_dir and image_path.stem.startswith(f"page-{page_index:03d}-"):
                        sections.extend([f"![{image_path.stem}]({image_path.as_posix()})", ""])

    return SourceMarkdown("\n".join(sections).strip() + "\n", "pymupdf", image_paths)


def _extract_page_images(document: object, page: object, page_index: int, assets_dir: Path) -> list[Path]:
    ensure_dir(assets_dir)
    extracted: list[Path] = []
    seen: set[int] = set()
    for image_index, image_info in enumerate(page.get_images(full=True), start=1):  # type: ignore[attr-defined]
        xref = int(image_info[0])
        if xref in seen:
            continue
        seen.add(xref)
        image = document.extract_image(xref)  # type: ignore[attr-defined]
        extension = image.get("ext", "png")
        image_path = assets_dir / f"page-{page_index:03d}-image-{image_index:02d}.{extension}"
        image_path.write_bytes(image["image"])
        extracted.append(image_path)
    return extracted


def _extract_pdf_text_with_pdftotext(source_path: Path) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    result = subprocess.run(
        ["pdftotext", "-layout", str(source_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def _extract_pdf_text_with_pypdf(source_path: Path) -> str | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None

    reader = PdfReader(str(source_path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(page for page in pages if page)
    return text.strip() or None


def _wrap_plain_text_as_markdown(source_path: Path, text: str) -> str:
    return f"# {_title_from_path(source_path)}\n\n{text.strip()}\n"


def _title_from_path(source_path: Path) -> str:
    title = source_path.stem.replace("_", " ").replace("-", " ").strip()
    return title or source_path.name


def _timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
