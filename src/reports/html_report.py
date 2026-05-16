"""HTML report generation for visual inspection results."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def generate_html_report(
    title: str,
    metrics: dict[str, Any],
    records: list[Any],
    output_path: str | Path,
    include_plots: bool = False,
) -> str:
    """Generate a self-contained HTML report for the evaluation run.

    Args:
        title: Report title.
        metrics: Dict of summary metrics (ok_fpr, ng_miss_rate, etc.).
        records: List of ImageRecord objects.
        output_path: Path where the .html file will be written.
        include_plots: If True, placeholder divs are included for chart embedding
            (actual charts must be injected separately).

    Returns:
        The absolute path to the generated HTML file.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_images = metrics.get("total_images", len(records))
    ok_fpr = metrics.get("ok_fpr", 0)
    ng_miss_rate = metrics.get("ng_miss_rate", 0)
    unknown_recall = metrics.get("unknown_recall", 0)
    borderline_rate = metrics.get("borderline_detection_rate", 0)
    avg_time = metrics.get("avg_inference_time_ms", 0)

    # Count decisions
    decision_counts: dict[str, int] = {}
    for rec in records:
        if rec.fusion_decision:
            dec = rec.fusion_decision.final_decision.value
            decision_counts[dec] = decision_counts.get(dec, 0) + 1

    html_parts: list[str] = []

    # --- head ---
    html_parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; color: #333; background: #f9fafb; }}
    h1 {{ color: #1a365d; border-bottom: 2px solid #4472C4; padding-bottom: 8px; margin-bottom: 16px; }}
    h2 {{ color: #2d3748; margin: 24px 0 12px; }}
    p {{ margin: 4px 0; }}
    .timestamp {{ color: #718096; font-size: 13px; margin-bottom: 16px; }}

    /* metric cards */
    .metric-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
    .metric-card {{
        background: #fff; border-radius: 8px; padding: 16px 20px; min-width: 150px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #4472C4;
    }}
    .metric-card .value {{ font-size: 28px; font-weight: 700; color: #2b6cb0; }}
    .metric-card .label {{ font-size: 12px; color: #718096; text-transform: uppercase; letter-spacing: 0.5px; }}

    /* decision distribution */
    .decision-bar {{ display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }}
    .decision-chip {{
        padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
        color: #fff;
    }}
    .chip-OK {{ background: #38a169; }}
    .chip-ACCEPTABLE_MICRO_DEFECT {{ background: #d69e2e; }}
    .chip-SUSPECT {{ background: #dd6b20; }}
    .chip-NG {{ background: #e53e3e; }}

    /* table */
    .table-wrapper {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; font-size: 12px; }}
    th {{ background-color: #4472C4; color: #fff; font-weight: 600; position: sticky; top: 0; }}
    tr:nth-child(even) {{ background: #f7fafc; }}

    .row-NG {{ background-color: #fff5f5 !important; }}
    .row-OK {{ background-color: #f0fff4 !important; }}
    .row-SUSPECT {{ background-color: #fffaf0 !important; }}

    footer {{ margin-top: 32px; color: #a0aec0; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 8px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="timestamp">Generated: {now}</p>

<h2>Metrics Summary</h2>
<div class="metric-grid">
    <div class="metric-card"><div class="value">{total_images}</div><div class="label">Total Images</div></div>
    <div class="metric-card"><div class="value">{ok_fpr:.3f}</div><div class="label">OK FPR</div></div>
    <div class="metric-card"><div class="value">{ng_miss_rate:.3f}</div><div class="label">NG Miss Rate</div></div>
    <div class="metric-card"><div class="value">{unknown_recall:.3f}</div><div class="label">Unknown Recall</div></div>
    <div class="metric-card"><div class="value">{borderline_rate:.3f}</div><div class="label">Borderline Rate</div></div>
    <div class="metric-card"><div class="value">{avg_time:.1f}</div><div class="label">Avg Time (ms)</div></div>
</div>

<h2>Decision Distribution</h2>
<div class="decision-bar">
""")

    for dec in ("OK", "ACCEPTABLE_MICRO_DEFECT", "SUSPECT", "NG"):
        count = decision_counts.get(dec, 0)
        html_parts.append(f'    <span class="decision-chip chip-{dec}">{dec}: {count}</span>\n')

    html_parts.append("""</div>
""")

    if include_plots:
        html_parts.append("""<h2>Charts</h2>
<div id="chart-confusion" style="margin: 16px 0;"></div>
<div id="chart-strategy" style="margin: 16px 0;"></div>
<div id="chart-timeseries" style="margin: 16px 0;"></div>
""")

    # --- results table ---
    html_parts.append(f"""<h2>Results ({len(records)} images)</h2>
<div class="table-wrapper">
<table>
<thead><tr><th>#</th><th>Image</th><th>True Label</th><th>Decision</th><th>Reason</th><th>Strategy</th><th>Time (ms)</th></tr></thead>
<tbody>
""")

    for idx, rec in enumerate(records, 1):
        fd = rec.fusion_decision
        if fd:
            decision = fd.final_decision.value
            reason = fd.reason
            strategy = fd.strategy.value
            time_ms = f"{fd.runtime_ms:.1f}"
        else:
            decision = "N/A"
            reason = ""
            strategy = "N/A"
            time_ms = "N/A"

        html_parts.append(
            f'<tr class="row-{decision}"><td>{idx}</td>'
            f"<td>{rec.image_path}</td>"
            f"<td>{rec.true_label}</td>"
            f"<td><strong>{decision}</strong></td>"
            f"<td>{reason}</td>"
            f"<td>{strategy}</td>"
            f"<td>{time_ms}</td></tr>\n"
        )

    html_parts.append("""</tbody>
</table>
</div>

<footer>Copper Tube Defect Evaluation Tool &mdash; Auto-generated Report</footer>
</body>
</html>""")

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    output_path_obj.write_text("".join(html_parts), encoding="utf-8")
    return str(output_path_obj.resolve())
