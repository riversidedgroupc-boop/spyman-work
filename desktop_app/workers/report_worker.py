"""Report generation worker — generates Markdown reports in background."""
from __future__ import annotations

import os
from datetime import datetime

from desktop_app.i18n import tr
from desktop_app.workers.base_worker import BaseWorker


class ReportWorker(BaseWorker):
    """Generates project or batch reports in background thread."""

    def __init__(
        self,
        report_type: str,  # "project" or "batch" or "system"
        project_name: str = "",
        output_dir: str = "",
        context: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report_type = report_type
        self._project_name = project_name
        self._output_dir = output_dir or os.path.join("outputs", "reports")
        self._context = context or {}
        self._output_path = ""

    def _run_impl(self) -> None:
        os.makedirs(self._output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self._report_type}_report_{ts}.md"
        self._output_path = os.path.join(self._output_dir, filename)

        lines = self._build_report()
        with open(self._output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.message.emit(tr("report.generated_to", path=self._output_path))

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
            f"*{tr('worker.report_footer', version=self._context.get('version', '0.5.0'))}*",
        ]
        return lines

    def _project_section(self) -> list[str]:
        lines = [tr("worker.report_project_section"), ""]
        ctx = self._context
        lines.append(f"- **{tr('project.col_customer')}:** {ctx.get('customer', 'N/A')}")
        lines.append(f"- **{tr('project.col_spec_name')}:** {ctx.get('spec', 'N/A')}")
        lines.append(f"- **{tr('worker.report_material')}:** {ctx.get('material', 'N/A')}")
        lines.append(f"- **{tr('worker.report_morphology')}:** {ctx.get('morphology', 'N/A')}")
        lines.append(f"- **{tr('worker.report_line_speed')}:** {ctx.get('line_speed', 'N/A')} m/min")
        lines.append(f"- **{tr('worker.report_camera_count')}:** {ctx.get('camera_count', 'N/A')}")
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
        lines.append(f"- **{tr('worker.report_total_inspected')}:** {ctx.get('total_inspected', 0)}")
        lines.append(f"- **{tr('worker.report_ng_count')}:** {ctx.get('ng_count', 0)}")
        lines.append(f"- **{tr('worker.report_ng_rate')}:** {ctx.get('ng_rate', 0):.2%}" if ctx.get('ng_rate') is not None else f"- **{tr('worker.report_ng_rate')}:** N/A")
        lines.append("")
        lines.append(tr("worker.report_defect_section"))
        for item in ctx.get('defect_distribution', []):
            lines.append(f"- **{item.get('label', '')}:** {item.get('count', 0)}")
        return lines

    def _system_section(self) -> list[str]:
        lines = [tr("worker.report_system_section"), ""]
        ctx = self._context
        health = ctx.get("health", {})
        lines.append(f"- **{tr('worker.report_uptime')}:** {health.get('uptime_seconds', 0):.0f} 秒")
        lines.append(f"- **{tr('worker.report_disk_usage')}:** {health.get('disk_percent', 0)}%")
        lines.append(f"- **{tr('worker.report_disk_free')}:** {health.get('disk_free_gb', 0)} GB")
        lines.append(f"- **{tr('worker.report_platform')}:** {health.get('platform', 'N/A')}")
        return lines

    def get_output_path(self) -> str:
        return self._output_path
