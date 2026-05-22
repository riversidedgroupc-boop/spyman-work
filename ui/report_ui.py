"""Report generation UI.

Phase 3: Generate Markdown/HTML evaluation reports.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.report import build_report_context, generate_markdown_report, generate_html_report


def render_report_ui(
    deployment_summary: dict | None = None,
    rule_summary: dict | None = None,
    position_summary: dict | None = None,
    review_summary: dict | None = None,
    model_names: list[str] | None = None,
):
    """Render the report generation interface."""
    st.header("评估报告生成")

    col1, col2 = st.columns(2)

    with col1:
        report_title = st.text_input(
            "报告标题",
            value="铜管表面缺陷模型评估报告",
            key="report_title",
        )
        project_name = st.text_input(
            "项目名称",
            value="铜管缺陷检测",
            key="report_project",
        )
        dataset_name = st.text_input(
            "数据集名称",
            value="copper_tube_inspection",
            key="report_dataset",
        )

        include_missed = st.checkbox("包含漏检样本", value=True, key="report_missed")
        include_fp = st.checkbox("包含误报样本", value=True, key="report_fp")
        include_position_chart = st.checkbox("包含米数分布图", value=True, key="report_position")

    with col2:
        st.subheader("包含的模型")
        if model_names:
            for m in model_names:
                st.text(f"✓ {m}")
        else:
            st.text("(未指定模型)")

        st.divider()
        st.subheader("报告格式")
        gen_md = st.button("生成 Markdown 报告", use_container_width=True, key="report_gen_md")
        gen_html = st.button("生成 HTML 报告", use_container_width=True, key="report_gen_html")

    # --- Build context ---
    context = build_report_context(
        deployment_summary=deployment_summary,
        rule_summary=rule_summary,
        position_summary=position_summary,
        review_summary=review_summary,
        project_name=project_name,
        dataset_name=dataset_name,
        model_names=model_names,
    )

    # --- Generate Markdown ---
    if gen_md:
        output_dir = Path("outputs/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"report_{timestamp}.md"

        try:
            content = generate_markdown_report(context, str(output_path))
            st.success(f"Markdown 报告已生成: {output_path}")

            # Preview
            with st.expander("预览 Markdown 报告"):
                st.markdown(content[:5000])
                if len(content) > 5000:
                    st.caption("... (内容截断)")

            # Download
            st.download_button(
                "下载 Markdown 报告",
                content,
                file_name=output_path.name,
                mime="text/markdown",
            )
        except Exception as e:
            st.error(f"Markdown 报告生成失败: {e}")

    # --- Generate HTML ---
    if gen_html:
        output_dir = Path("outputs/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"report_{timestamp}.html"

        try:
            content = generate_html_report(context, str(output_path))
            st.success(f"HTML 报告已生成: {output_path}")

            # Download
            st.download_button(
                "下载 HTML 报告",
                content,
                file_name=output_path.name,
                mime="text/html",
            )
        except Exception as e:
            st.error(f"HTML 报告生成失败: {e}")

    # --- Report preview ---
    st.divider()
    st.subheader("报告内容预览")

    st.markdown("""
    **报告包含以下章节:**

    1. 项目信息
    2. 数据集概要
    3. 模型配置
    4. 总体指标
    5. 分类指标
    6. 部署评估指标
    7. 缺陷规则判定汇总
    8. 漏检样本
    9. 误报样本
    10. 缺陷米数分布
    11. 人工复核汇总
    12. 相似缺陷与未知缺陷发现
    13. 模型上线评估结论
    14. 建议后续行动
    """)
