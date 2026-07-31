from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from weasyprint import HTML


class PDFGenerationError(RuntimeError):
    pass


TEMPLATE_DIR = Path(__file__).parent / "templates"


def build_report_pdf(context: dict[str, Any]) -> bytes:
    try:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
        )
        template = env.get_template("report_template.html")
        rendered_html = template.render(**context)
        pdf_buffer = HTML(string=rendered_html).write_pdf()
        if not pdf_buffer:
            raise PDFGenerationError("Failed to render PDF output")
        return pdf_buffer
    except Exception as exc:
        if isinstance(exc, PDFGenerationError):
            raise
        raise PDFGenerationError("Report rendering failed") from exc
