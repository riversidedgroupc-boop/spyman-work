"""Similar defect retrieval UI.

Phase 3: Find visually similar defects from reviewed/predicted defects.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from PIL import Image

from retrieval.index import build_retrieval_index, load_retrieval_index, search_similar_defects


def render_retrieval_ui(
    defect_records: list[dict] | None = None,
    image_root: str = "data/images",
):
    """Render the similar defect retrieval interface."""
    st.header("相似缺陷检索")

    # --- Build index ---
    st.subheader("检索索引")

    col1, col2 = st.columns(2)
    with col1:
        index_path = st.text_input(
            "索引文件路径",
            value=".cache/retrieval/defect_index.pkl",
            key="retrieval_index_path",
        )

    # Try to load existing index
    index = None
    if Path(index_path).exists():
        try:
            index = load_retrieval_index(index_path)
            with col2:
                st.success(f"已加载索引: {index.get('num_indexed', 0)} 条记录")
        except Exception as e:
            with col2:
                st.warning(f"索引加载失败: {e}")

    # Build new index
    if defect_records and (index is None or st.button("重建索引", key="retrieval_rebuild")):
        with st.spinner("正在构建检索索引..."):
            try:
                index = build_retrieval_index(defect_records, image_root, index_path)
                st.success(f"索引构建完成: {index['num_indexed']} 条记录")
            except Exception as e:
                st.error(f"索引构建失败: {e}")

    if index is None:
        st.info("请提供缺陷记录并构建检索索引。")
        return

    # --- Search ---
    st.divider()
    st.subheader("相似缺陷搜索")

    col_a, col_b = st.columns(2)
    with col_a:
        query_image = st.text_input(
            "查询图片路径",
            value="",
            key="retrieval_query_img",
            help="输入图片路径，相对于 image_root",
        )
        top_k = st.number_input("返回结果数", min_value=1, max_value=50, value=10, key="retrieval_top_k")
    with col_b:
        bbox_str = st.text_input(
            "查询 BBox (x1,y1,x2,y2)",
            value="0,0,100,100",
            key="retrieval_query_bbox",
        )
        metric = st.selectbox("相似度度量", ["cosine", "euclidean"], key="retrieval_metric")

    if query_image and st.button("搜索", type="primary", key="retrieval_search"):
        try:
            bbox = [float(v.strip()) for v in bbox_str.split(",")]
            if len(bbox) != 4:
                st.error("BBox 格式错误")
            else:
                query_path = Path(image_root) / query_image
                if not query_path.exists():
                    query_path = Path(query_image)

                if query_path.exists():
                    results = search_similar_defects(
                        str(query_path), bbox, index, top_k=top_k, metric=metric
                    )

                    if results:
                        st.subheader(f"检索结果 ({len(results)})")

                        # Show query image
                        try:
                            q_img = Image.open(query_path)
                            crop = q_img.crop([int(v) for v in bbox])
                            st.image(crop, caption=f"查询: {query_image}", width=200)
                        except Exception:
                            pass

                        # Show results
                        results_per_row = 5
                        for i, result in enumerate(results):
                            if i % results_per_row == 0:
                                img_cols = st.columns(results_per_row)

                            with img_cols[i % results_per_row]:
                                result_img_name = result.get("image_name", "")
                                result_img_path = Path(image_root) / result_img_name
                                if not result_img_path.exists():
                                    result_img_path = Path(result_img_name)

                                if result_img_path.exists():
                                    try:
                                        img = Image.open(result_img_path)
                                        r_bbox = result.get("bbox", [0, 0, 100, 100])
                                        try:
                                            crop = img.crop([int(v) for v in r_bbox])
                                            st.image(crop, use_container_width=True)
                                        except Exception:
                                            st.image(img, use_container_width=True)
                                    except Exception:
                                        st.text(f"无法加载: {result_img_name}")
                                else:
                                    st.text(f"图片不存在: {result_img_name}")

                                st.caption(
                                    f"类别: {result.get('class_name', '?')}\n"
                                    f"相似度: {result.get('similarity', 0):.3f}"
                                )
                    else:
                        st.info("无相似结果")
                else:
                    st.error(f"查询图片不存在: {query_path}")
        except ValueError:
            st.error("BBox 数值解析失败")

    # --- Index info ---
    st.divider()
    st.subheader("索引信息")
    records = index.get("records", [])
    if records:
        st.text(f"已索引: {len(records)} 条记录")

        # Show class distribution in index
        class_counts: dict[str, int] = {}
        for r in records:
            cn = r.get("class_name", "unknown")
            class_counts[cn] = class_counts.get(cn, 0) + 1

        if class_counts:
            import pandas as pd
            st.dataframe(
                pd.DataFrame(
                    {"类别": list(class_counts.keys()), "数量": list(class_counts.values())}
                ).sort_values("数量", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
