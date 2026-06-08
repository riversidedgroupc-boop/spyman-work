"""Report generation worker — multi-format (Markdown, HTML, PDF, CSV, JSON)."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from core.workspace_paths import get_reports_root, ensure_dir
from desktop_app.i18n import tr
from desktop_app.workers.base_worker import BaseWorker


SUPPORTED_FORMATS = ("md", "html", "pdf", "csv", "json")


class ReportWorker(BaseWorker):
    """Generates project/batch/system reports in multiple formats."""

    def __init__(
        self,
        report_type: str,
        project_name: str = "",
        output_dir: str = "",
        context: dict | None = None,
        export_format: str = "md",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report_type = report_type
        self._project_name = project_name
        self._output_dir = output_dir or ensure_dir(get_reports_root())
        self._context = context or {}
        self._export_format = export_format if export_format in SUPPORTED_FORMATS else "md"
        self._output_path = ""

    def _run_impl(self) -> None:
        os.makedirs(self._output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build Markdown content first
        md_lines = self._build_report()
        md_content = "\n".join(md_lines)

        if self._export_format == "md":
            self._output_path = os.path.join(
                self._output_dir, f"{self._report_type}_report_{ts}.md"
            )
            with open(self._output_path, "w", encoding="utf-8") as f:
                f.write(md_content)

        elif self._export_format == "html":
            self._output_path = os.path.join(
                self._output_dir, f"{self._report_type}_report_{ts}.html"
            )
            html = self._md_to_html(md_content)
            with open(self._output_path, "w", encoding="utf-8") as f:
                f.write(html)

        elif self._export_format == "pdf":
            self._output_path = os.path.join(
                self._output_dir, f"{self._report_type}_report_{ts}.pdf"
            )
            try:
                self._write_pdf(md_content)
            except ImportError:
                # Fallback to HTML
                self._output_path = os.path.join(
                    self._output_dir, f"{self._report_type}_report_{ts}.html"
                )
                html = self._md_to_html(md_content)
                with open(self._output_path, "w", encoding="utf-8") as f:
                    f.write(html)
                self.message.emit(tr("report.pdf_fallback"))

        elif self._export_format == "csv":
            self._output_path = os.path.join(
                self._output_dir, f"{self._report_type}_report_{ts}.csv"
            )
            self._write_csv()

        elif self._export_format == "json":
            self._output_path = os.path.join(
                self._output_dir, f"{self._report_type}_report_{ts}.json"
            )
            data = {
                "report_type": self._report_type,
                "project_name": self._project_name,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "context": self._context,
            }
            with open(self._output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        self.message.emit(tr("report.generated_to", path=self._output_path))

    # ------------------------------------------------------------------
    # Markdown content builder (same as before)
    # ------------------------------------------------------------------

    def _build_report(self) -> list[str]:
        _title_keys = {
            "project": "worker.report_project_title",
            "batch": "worker.report_batch_title",
            "system": "worker.report_system_title",
        }
        title_key = _title_keys.get(self._report_type, "worker.report_project_title")
        lines = [
            tr(title_key),
            "",
            f"**{tr('worker.report_generated_time')}:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**{tr('app.name')}:** {self._project_name or 'N/A'}",
            "",
            "---",
            "",
        ]

        if self._report_type == "project":
            lines += self._project_section()
        elif self._report_type == "batch":
            lines += self._batch_section()
        elif self._report_type == "system":
            lines += self._system_section()

        lines += [
            "",
            "---",
            "",
            f"*{tr('worker.report_footer', version=self._context.get('version', '0.6.0'))}*",
        ]
        return lines

    def _project_section(self) -> list[str]:
        lines = [tr("worker.report_project_section"), ""]
        ctx = self._context
        lines.append(f"- **{tr('project.col_customer')}:** {ctx.get('customer', 'N/A')}")
        lines.append(f"- **{tr('project.col_spec_name')}:** {ctx.get('spec', 'N/A')}")
        lines.append(f"- **{tr('worker.report_material')}:** {ctx.get('material', 'N/A')}")
        lines.append(f"- **{tr('worker.report_morphology')}:** {ctx.get('morphology', 'N/A')}")
        lines.append(
            f"- **{tr('worker.report_line_speed')}:** {ctx.get('line_speed', 'N/A')} m/min"
        )
        lines.append(f"- **{tr('worker.report_camera_count')}:** {ctx.get('camera_count', 'N/A')}")
        lines.append("")
        # Workflow status
        wf_state = ctx.get("workflow_state", "")
        if wf_state:
            lines.append("## Workflow Status")
            lines.append(f"- **State:** {wf_state}")
            lines.append(f"- **Next Action:** {ctx.get('workflow_next_action', 'N/A')}")
            wf_details = ctx.get("workflow_details", {})
            if wf_details:
                lines.append("- **Evidence:**")
                for k, v in wf_details.items():
                    lines.append(f"  - {k}: {v}")
            lines.append("")
        lines.append(tr("worker.report_model_section"))
        lines.append(f"- **{tr('worker.report_model_name')}:** {ctx.get('model_name', 'N/A')}")
        lines.append(f"- **{tr('worker.report_model_path')}:** {ctx.get('model_path', 'N/A')}")
        lines.append("")
        lines.append(tr("worker.report_sample_section"))
        lines.append(f"- **{tr('worker.report_total_samples')}:** {ctx.get('total_samples', 0)}")
        lines.append(f"- **OK:** {ctx.get('ok_count', 0)}")
        lines.append(f"- **NG_A:** {ctx.get('nga_count', 0)}")
        lines.append(f"- **NG_B:** {ctx.get('ngb_count', 0)}")
        lines.append(f"- **UNKNOWN:** {ctx.get('unknown_count', 0)}")
        return lines

    def _batch_section(self) -> list[str]:
        lines = [tr("worker.report_batch_section"), ""]
        ctx = self._context
        lines.append(f"- **{tr('worker.report_batch_id')}:** {ctx.get('batch_id', 'N/A')}")
        lines.append(f"- **{tr('worker.report_start_time')}:** {ctx.get('start_time', 'N/A')}")
        lines.append(f"- **{tr('worker.report_end_time')}:** {ctx.get('end_time', 'N/A')}")
        lines.append(
            f"- **{tr('worker.report_total_inspected')}:** {ctx.get('total_inspected', 0)}"
        )
        lines.append(f"- **{tr('worker.report_ng_count')}:** {ctx.get('ng_count', 0)}")
        ng_rate = ctx.get("ng_rate")
        if ng_rate is not None:
            lines.append(f"- **{tr('worker.report_ng_rate')}:** {ng_rate:.2%}")
        else:
            lines.append(f"- **{tr('worker.report_ng_rate')}:** N/A")
        lines.append("")
        lines.append(tr("worker.report_defect_section"))
        for item in ctx.get("defect_distribution", []):
            lines.append(f"- **{item.get('label', '')}:** {item.get('count', 0)}")
        return lines

    def _system_section(self) -> list[str]:
        lines = [tr("worker.report_system_section"), ""]
        ctx = self._context
        health = ctx.get("health", {})
        lines.append(f"- **{tr('worker.report_uptime')}:** {health.get('uptime_seconds', 0):.0f} s")
        lines.append(f"- **{tr('worker.report_disk_usage')}:** {health.get('disk_percent', 0)}%")
        lines.append(f"- **{tr('worker.report_disk_free')}:** {health.get('disk_free_gb', 0)} GB")
        lines.append(f"- **{tr('worker.report_platform')}:** {health.get('platform', 'N/A')}")
        return lines

    # ------------------------------------------------------------------
    # Format converters
    # ------------------------------------------------------------------

    def _md_to_html(self, md: str) -> str:
        """Basic Markdown-to-HTML conversion (bold, headers, lists, hr)."""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{self._report_type} Report</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #222; }}
h1 {{ border-bottom: 2px solid #ddd; padding-bottom: 8px; }}
h2 {{ margin-top: 24px; }}
hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
strong {{ color: #444; }}
ul {{ padding-left: 20px; }}
</style></head><body>
"""
        for line in md.split("\n"):
            line = line.strip()
            if not line:
                html += "<br>\n"
            elif line == "---":
                html += "<hr>\n"
            elif line.startswith("# "):
                html += f"<h1>{line[2:]}</h1>\n"
            elif line.startswith("## "):
                html += f"<h2>{line[3:]}</h2>\n"
            elif line.startswith("- "):
                # Basic bold handling
                content = line[2:]
                content = content.replace("**", "<strong>").replace("**", "</strong>")
                # Fix alternating strong tags
                import re

                content = re.sub(r"<strong>(.*?)</strong>", r"<strong>\1</strong>", content)
                # Simple approach: just replace pairs
                content = _replace_bold(content)
                html += f"<li>{content}</li>\n"
            else:
                content = _replace_bold(line)
                html += f"<p>{content}</p>\n"

        html += "</body></html>\n"
        return html

    def _write_pdf(self, md: str) -> None:
        """Write PDF using fpdf2."""
        from fpdf import FPDF  # type: ignore

        pdf = FPDF()
        pdf.add_page()
        # Use built-in font that supports Latin-1
        pdf.set_font("Helvetica", size=10)

        for line in md.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(4)
            elif line.startswith("# "):
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, line[2:], ln=True)
                pdf.set_font("Helvetica", size=10)
            elif line.startswith("## "):
                pdf.set_font("Helvetica", "B", 13)
                pdf.cell(0, 10, line[3:], ln=True)
                pdf.set_font("Helvetica", size=10)
            elif line == "---":
                pdf.ln(4)
            else:
                # Strip markdown formatting
                clean = line.replace("**", "").replace("*", "")
                pdf.multi_cell(0, 5, clean)

        pdf.output(self._output_path)

    def _write_csv(self) -> None:
        """Write key-value pairs as CSV."""
        rows = [("Key", "Value")]
        for key, value in self._context.items():
            if isinstance(value, dict):
                for sub_k, sub_v in value.items():
                    rows.append((f"{key}.{sub_k}", str(sub_v)))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_k, sub_v in item.items():
                            rows.append((f"{key}[{i}].{sub_k}", str(sub_v)))
                    else:
                        rows.append((f"{key}[{i}]", str(item)))
            else:
                rows.append((key, str(value)))

        with open(self._output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def get_output_path(self) -> str:
        return self._output_path


def _replace_bold(text: str) -> str:
    """Replace **text** with <strong>text</strong>."""
    parts = text.split("**")
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result.append(f"<strong>{part}</strong>")
        else:
            result.append(part)
    return "".join(result)
