"""Automatic evaluation report generation.

Generates Markdown and HTML reports for customer communication,
internal review, and model iteration.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime


def build_report_context(
    experiment: dict | None = None,
    deployment_summary: dict | None = None,
    rule_summary: dict | None = None,
    position_summary: dict | None = None,
    review_summary: dict | None = None,
    project_name: str = "",
    dataset_name: str = "",
    model_names: list[str] | None = None,
) -> dict:
    """Assemble all report data into a single context dict."""
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_name": project_name,
        "dataset_name": dataset_name,
        "model_names": model_names or [],
        "experiment": experiment or {},
        "deployment_summary": deployment_summary or {},
        "rule_summary": rule_summary or {},
        "position_summary": position_summary or {},
        "review_summary": review_summary or {},
    }


def _dict_to_md_table(data: dict, indent: str = "") -> str:
    """Convert a flat dict to a Markdown table."""
    if not data:
        return f"{indent}(无数据)\n"
    lines = [f"{indent}| 指标 | 值 |", f"{indent}|------|-----|"]
    for k, v in data.items():
        if isinstance(v, float):
            lines.append(f"{indent}| {k} | {v:.4f} |")
        elif v is None:
            lines.append(f"{indent}| {k} | N/A |")
        else:
            lines.append(f"{indent}| {k} | {v} |")
    return "\n".join(lines) + "\n"


def _generate_markdown_content(context: dict) -> str:
    """Generate Markdown report content without writing to a file."""
    ctx = context
    project = ctx.get("project_name", "铜管缺陷检测")
    dataset = ctx.get("dataset_name", "未指定")
    models = ctx.get("model_names", [])
    dep = ctx.get("deployment_summary", {})
    rules = ctx.get("rule_summary", {})
    pos = ctx.get("position_summary", {})
    review = ctx.get("review_summary", {})

    lines: list[str] = []
    lines.append(f"# {project} — 模型评估报告")
    lines.append("")
    lines.append(f"**生成时间**: {ctx.get('generated_at', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Project Information
    lines.append("## 1. 项目信息")
    lines.append("")
    lines.append(f"- **项目名称**: {project}")
    lines.append(f"- **数据集**: {dataset}")
    lines.append(f"- **评估模型**: {', '.join(models) if models else '未指定'}")
    lines.append("")

    # 2. Dataset Summary
    lines.append("## 2. 数据集概要")
    lines.append("")
    lines.append(_dict_to_md_table({
        "图片总数": dep.get("num_images", "N/A"),
        "GT标注数": dep.get("num_gt", "N/A"),
        "预测总数": dep.get("num_predictions", "N/A"),
    }))
    lines.append("")

    # 3. Model Configuration
    lines.append("## 3. 模型配置")
    lines.append("")
    if models:
        for m in models:
            lines.append(f"- {m}")
    else:
        lines.append("(未指定模型)")
    lines.append("")

    # 4. Overall Metrics
    lines.append("## 4. 总体指标")
    lines.append("")
    lines.append(_dict_to_md_table({
        "True Positives": dep.get("true_positives"),
        "False Positives": dep.get("false_positives"),
        "False Negatives": dep.get("false_negatives"),
    }))
    lines.append("")

    # 5. Per-Class Metrics
    lines.append("## 5. 分类指标")
    lines.append("")
    lines.append("(参见高级评估分析模块)")
    lines.append("")

    # 6. Deployment Metrics
    lines.append("## 6. 部署评估指标")
    lines.append("")
    lines.append(_dict_to_md_table({
        "漏检率 (Miss Rate)": dep.get("miss_rate"),
        "误报率 (False Alarm Rate)": dep.get("false_alarm_rate"),
        "每米误报数 (FP/m)": dep.get("false_alarms_per_meter"),
        "人工复核图片数": dep.get("review_load_images"),
        "人工复核比例": dep.get("review_load_ratio"),
        "平均推理时间 (ms)": dep.get("avg_inference_ms"),
        "最大推理时间 (ms)": dep.get("max_inference_ms"),
    }))
    lines.append("")

    # 7. Defect Rule Summary
    lines.append("## 7. 缺陷规则判定汇总")
    lines.append("")
    by_level = rules.get("by_level", {})
    if by_level:
        lines.append(_dict_to_md_table({
            "A级-严重 (必须报警)": by_level.get("A_severe", 0),
            "B级-一般 (记录)": by_level.get("B_general", 0),
            "C级-可接受 (不报警)": by_level.get("C_acceptable", 0),
            "未知缺陷 (待审核)": by_level.get("UNKNOWN", 0),
            "低置信度 (待审核)": by_level.get("LOW_CONFIDENCE", 0),
        }))
    else:
        lines.append("(未配置缺陷规则)")
    lines.append("")

    # 8. Missed Defect Samples
    lines.append("## 8. 漏检样本")
    lines.append("")
    lines.append("(请参见误判样本池)")
    lines.append("")

    # 9. False Positive Samples
    lines.append("## 9. 误报样本")
    lines.append("")
    lines.append("(请参见误判样本池)")
    lines.append("")

    # 10. Meter Position Distribution
    lines.append("## 10. 缺陷米数分布")
    lines.append("")
    if pos:
        lines.append(_dict_to_md_table({
            "位置已知检测数": pos.get("positioned_count"),
            "位置未知检测数": pos.get("unpositioned_count"),
            "米数范围": str(pos.get("meter_range", "N/A")),
            "平均米数": pos.get("mean_meter"),
            "每米最大缺陷数": pos.get("max_count_per_meter"),
        }))
    else:
        lines.append("(未配置位置信息)")
    lines.append("")

    # 11. Manual Review Summary
    lines.append("## 11. 人工复核汇总")
    lines.append("")
    if review:
        by_label = review.get("by_label", {})
        if by_label:
            lines.append(_dict_to_md_table(by_label))
        else:
            lines.append(f"总复核记录: {review.get('total', 0)}")
    else:
        lines.append("(无人工复核记录)")
    lines.append("")

    # 12. Similar / Unknown Defect Findings
    lines.append("## 12. 相似缺陷与未知缺陷发现")
    lines.append("")
    lines.append("(请参见相似缺陷检索与未知缺陷聚类模块)")
    lines.append("")

    # 13. Model Readiness Conclusion
    lines.append("## 13. 模型上线评估结论")
    lines.append("")
    miss_rate = dep.get("miss_rate", 1.0)
    fp_per_meter = dep.get("false_alarms_per_meter")
    avg_ms = dep.get("avg_inference_ms", 0)

    conclusions: list[str] = []
    if isinstance(miss_rate, (int, float)) and miss_rate > 0.05:
        conclusions.append(f"- ⚠️ 漏检率为 {miss_rate:.1%}，超过 5% 阈值，需要进一步降低漏检。")
    else:
        conclusions.append(f"- ✅ 漏检率为 {miss_rate:.1%}，在可接受范围内。")

    if fp_per_meter is not None and fp_per_meter > 1.0:
        conclusions.append(f"- ⚠️ 每米误报数为 {fp_per_meter:.1f}，误报负载偏高，建议调优。")
    elif fp_per_meter is not None:
        conclusions.append(f"- ✅ 每米误报数为 {fp_per_meter:.1f}，在可接受范围内。")

    if isinstance(avg_ms, (int, float)) and avg_ms > 50:
        conclusions.append(f"- ⚠️ 平均推理时间 {avg_ms:.0f}ms，超过 50ms，可能需要加速。")
    else:
        conclusions.append(f"- ✅ 平均推理时间 {avg_ms:.0f}ms，满足实时性要求。")

    for c in conclusions:
        lines.append(c)
    lines.append("")

    # 14. Recommended Next Actions
    lines.append("## 14. 建议后续行动")
    lines.append("")
    lines.append("- 对误报样本进行分类分析，确定主要误报来源")
    lines.append("- 对漏检样本进行特征分析，补充训练数据")
    lines.append("- 如有未知缺陷聚类结果，评估是否需要新增缺陷类别")
    lines.append("- 定期更新人工复核记录，维护样本回流闭环")
    lines.append("")

    return "\n".join(lines)


def generate_markdown_report(context: dict, output_path: str) -> str:
    """Generate a Markdown report and write it to output_path."""
    content = _generate_markdown_content(context)

    if output_path:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    return content


def generate_html_report(context: dict, output_path: str) -> str:
    """Generate an HTML evaluation report."""
    md_content = _generate_markdown_content(context)

    # Simple HTML wrapper with basic styling
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>铜管缺陷检测评估报告</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 960px;
    margin: 40px auto;
    padding: 20px;
    line-height: 1.6;
    color: #333;
}}
h1 {{ border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }}
h2 {{ color: #1a73e8; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background-color: #f5f5f5; }}
tr:nth-child(even) {{ background-color: #fafafa; }}
</style>
</head>
<body>
{_markdown_to_html(md_content)}
<p><em>报告由铜管缺陷评测工具 Phase 3 自动生成</em></p>
</body>
</html>"""

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    return html


def _markdown_to_html(md: str) -> str:
    """Very simple Markdown to HTML converter for common patterns."""
    import re

    lines = md.split("\n")
    html_lines: list[str] = []
    in_table = False

    for line in lines:
        # Headers
        if line.startswith("## "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h1>{line[2:]}</h1>")
        # Horizontal rule
        elif line.strip() == "---":
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append("<hr>")
        # Table
        elif line.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.startswith("--") for c in cells):
                continue  # Skip separator
            tag = "th" if not html_lines or html_lines[-1] == "<table>" else "td"
            row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
        # List items
        elif line.startswith("- "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<li>{line[2:]}</li>")
        # Bold
        elif "**" in line:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            processed = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f"<p>{processed}</p>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            if line.strip():
                html_lines.append(f"<p>{line}</p>")

    if in_table:
        html_lines.append("</table>")

    return "\n".join(html_lines)
