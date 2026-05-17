"""Internationalization (i18n) module for CX-vision desktop app.

Usage:
    from desktop_app.i18n import tr, I18nManager

    label.setText(tr("nav.project_center"))
    # Or: label.setText(I18nManager.instance().tr("nav.project_center"))

When language changes, I18nManager emits language_changed(str) signal.
Connect to it and refresh your UI text.
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QObject, Signal

# ── Translation table ──────────────────────────────────────────────
# Keys are flat dotted strings. Each value is {"zh": ..., "en": ...}.
_STRINGS: dict[str, dict[str, str]] = {
    # App
    "app.title": {"zh": "CX-vision — 工业视觉在线检测系统", "en": "CX-vision — Industrial Vision Online Inspection System"},
    "app.version": {"zh": "v0.5.0", "en": "v0.5.0"},
    "app.not_implemented": {"zh": "待实现", "en": "Not Implemented"},
    "app.ok": {"zh": "确定", "en": "OK"},
    "app.cancel": {"zh": "取消", "en": "Cancel"},
    "app.save": {"zh": "保存", "en": "Save"},
    "app.delete": {"zh": "删除", "en": "Delete"},
    "app.edit": {"zh": "编辑", "en": "Edit"},
    "app.add": {"zh": "新建", "en": "New"},
    "app.refresh": {"zh": "刷新", "en": "Refresh"},
    "app.browse": {"zh": "选择目录", "en": "Browse"},
    "app.browse_file": {"zh": "选择文件", "en": "Browse File"},
    "app.close": {"zh": "关闭", "en": "Close"},
    "app.confirm_delete": {"zh": "确认删除", "en": "Confirm Delete"},
    "app.tip": {"zh": "提示", "en": "Info"},
    "app.error": {"zh": "错误", "en": "Error"},
    "app.warning": {"zh": "警告", "en": "Warning"},
    "app.completed": {"zh": "完成", "en": "Completed"},
    "app.validation_failed": {"zh": "验证失败", "en": "Validation Failed"},
    "app.select_first": {"zh": "请先选择一项", "en": "Please select an item first"},
    "app.select_project_first": {"zh": "请先选择项目和规格", "en": "Please select a project and spec first"},
    "app.select_project": {"zh": "请先选择项目", "en": "Please select a project first"},
    "app.select_model": {"zh": "请先选择模型", "en": "Please select a model first"},
    "app.select_session": {"zh": "请先选择采集会话", "en": "Please select a capture session first"},
    "app.not_selected": {"zh": "未选择", "en": "Not selected"},
    "app.unknown": {"zh": "未知", "en": "Unknown"},
    "app.none": {"zh": "无", "en": "None"},
    "app.all": {"zh": "全部", "en": "All"},
    "app.unsaved": {"zh": "未命名", "en": "Unnamed"},
    "app.not_configured": {"zh": "未配置", "en": "Not configured"},
    "app.offline": {"zh": "离线", "en": "Offline"},
    "app.status": {"zh": "状态", "en": "Status"},
    "app.created_at": {"zh": "创建时间", "en": "Created"},
    "app.notes": {"zh": "备注", "en": "Notes"},
    "app.name": {"zh": "名称", "en": "Name"},
    "app.type": {"zh": "类型", "en": "Type"},
    "app.path": {"zh": "路径", "en": "Path"},
    "app.config_saved": {"zh": "配置已保存", "en": "Configuration saved"},
    "app.loading": {"zh": "加载中...", "en": "Loading..."},
    "app.processing": {"zh": "处理中...", "en": "Processing..."},

    # Navigation
    "nav.project_center": {"zh": "项目中心", "en": "Project Center"},
    "nav.capture": {"zh": "现场数据", "en": "Field Data"},
    "nav.training": {"zh": "训练中心", "en": "Training Center"},
    "nav.evaluation": {"zh": "验证中心", "en": "Validation Center"},
    "nav.production": {"zh": "生产运行", "en": "Production Run"},
    "nav.device_config": {"zh": "设备配置", "en": "Device Config"},
    "nav.reports": {"zh": "报告中心", "en": "Reports"},
    "nav.settings": {"zh": "系统设置", "en": "System Settings"},

    # Status bar
    "status.current_context": {"zh": "当前客户: {customer} | 项目: {project} | 规格: {spec}", "en": "Customer: {customer} | Project: {project} | Spec: {spec}"},
    "status.no_project": {"zh": "未选择项目", "en": "No project selected"},

    # Project selector
    "selector.customer": {"zh": "客户:", "en": "Customer:"},
    "selector.project": {"zh": "项目:", "en": "Project:"},
    "selector.spec": {"zh": "规格:", "en": "Spec:"},
    "selector.select_customer": {"zh": "-- 选择客户 --", "en": "-- Select Customer --"},
    "selector.select_project": {"zh": "-- 选择项目 --", "en": "-- Select Project --"},
    "selector.select_spec": {"zh": "-- 选择规格 --", "en": "-- Select Spec --"},

    # Project center page
    "project.customers": {"zh": "客户管理", "en": "Customer Management"},
    "project.projects": {"zh": "项目管理", "en": "Project Management"},
    "project.specs": {"zh": "产品规格", "en": "Product Specifications"},
    "project.new_customer": {"zh": "+ 新建客户", "en": "+ New Customer"},
    "project.new_project": {"zh": "+ 新建项目", "en": "+ New Project"},
    "project.new_spec": {"zh": "+ 新建规格", "en": "+ New Spec"},
    "project.edit_customer": {"zh": "编辑客户", "en": "Edit Customer"},
    "project.edit_project": {"zh": "编辑项目", "en": "Edit Project"},
    "project.edit_spec": {"zh": "编辑产品规格", "en": "Edit Product Spec"},
    "project.delete_customer_confirm": {"zh": "确定要删除客户「{name}」吗？\n这会同时删除其下所有项目和规格。", "en": "Delete customer \"{name}\"?\nThis will also delete all associated projects and specs."},
    "project.delete_project_confirm": {"zh": "确定要删除项目「{name}」吗？", "en": "Delete project \"{name}\"?"},
    "project.delete_spec_confirm": {"zh": "确定要删除规格「{name}」吗？", "en": "Delete spec \"{name}\"?"},
    "project.create_customer_first": {"zh": "请先创建一个客户", "en": "Please create a customer first"},
    "project.create_project_first": {"zh": "请先创建一个项目", "en": "Please create a project first"},
    "project.col_id": {"zh": "ID", "en": "ID"},
    "project.col_name": {"zh": "名称", "en": "Name"},
    "project.col_short_name": {"zh": "简称", "en": "Short Name"},
    "project.col_industry": {"zh": "行业", "en": "Industry"},
    "project.col_contact": {"zh": "联系人", "en": "Contact"},
    "project.col_status": {"zh": "状态", "en": "Status"},
    "project.col_project_name": {"zh": "项目名称", "en": "Project Name"},
    "project.col_customer": {"zh": "客户", "en": "Customer"},
    "project.col_spec_name": {"zh": "规格名称", "en": "Spec Name"},
    "project.col_material": {"zh": "材质", "en": "Material"},
    "project.col_morphology": {"zh": "形态", "en": "Morphology"},
    "project.col_speed_range": {"zh": "速度范围", "en": "Speed Range"},
    "project.col_camera_count": {"zh": "相机数", "en": "Cameras"},
    "project.col_created": {"zh": "创建时间", "en": "Created"},

    # Customer dialog
    "customer.title_new": {"zh": "新建客户", "en": "New Customer"},
    "customer.title_edit": {"zh": "编辑客户", "en": "Edit Customer"},
    "customer.name": {"zh": "客户名称:", "en": "Customer Name:"},
    "customer.name_placeholder": {"zh": "客户全称（必填）", "en": "Full name (required)"},
    "customer.short_name": {"zh": "简称:", "en": "Short Name:"},
    "customer.short_placeholder": {"zh": "简称（必填）", "en": "Short name (required)"},
    "customer.industry": {"zh": "行业:", "en": "Industry:"},
    "customer.industry_placeholder": {"zh": "如：铜加工、汽车制造", "en": "e.g.: Copper, Automotive"},
    "customer.contact": {"zh": "联系人:", "en": "Contact:"},
    "customer.location": {"zh": "地址:", "en": "Location:"},
    "customer.name_required": {"zh": "客户名称不能为空", "en": "Customer name is required"},
    "customer.short_required": {"zh": "简称不能为空", "en": "Short name is required"},

    # Project dialog
    "proj.title_new": {"zh": "新建项目", "en": "New Project"},
    "proj.title_edit": {"zh": "编辑项目", "en": "Edit Project"},
    "proj.name": {"zh": "项目名称:", "en": "Project Name:"},
    "proj.name_placeholder": {"zh": "项目名称（必填）", "en": "Project name (required)"},
    "proj.type": {"zh": "项目类型:", "en": "Project Type:"},
    "proj.name_required": {"zh": "项目名称不能为空", "en": "Project name is required"},

    # Spec dialog
    "spec.title_new": {"zh": "新建产品规格", "en": "New Product Spec"},
    "spec.title_edit": {"zh": "编辑产品规格", "en": "Edit Product Spec"},
    "spec.name": {"zh": "规格名称:", "en": "Spec Name:"},
    "spec.name_placeholder": {"zh": "产品规格名称（必填）", "en": "Spec name (required)"},
    "spec.material": {"zh": "材质:", "en": "Material:"},
    "spec.geometry": {"zh": "形态:", "en": "Morphology:"},
    "spec.surface_type": {"zh": "表面类型:", "en": "Surface Type:"},
    "spec.min_speed": {"zh": "最低速度:", "en": "Min Speed:"},
    "spec.max_speed": {"zh": "最高速度:", "en": "Max Speed:"},
    "spec.target_speed": {"zh": "目标速度:", "en": "Target Speed:"},
    "spec.camera_count": {"zh": "相机数量:", "en": "Camera Count:"},
    "spec.name_required": {"zh": "规格名称不能为空", "en": "Spec name is required"},
    "spec.speed_range_invalid": {"zh": "最低速度不能大于最高速度", "en": "Min speed cannot exceed max speed"},
    "spec.target_speed_invalid": {"zh": "目标速度必须在最低/最高速度范围内", "en": "Target speed must be within min/max range"},

    # Capture page
    "capture.title": {"zh": "采集会话", "en": "Capture Sessions"},
    "capture.new_session": {"zh": "+ 新建采集会话", "en": "+ New Capture Session"},
    "capture.col_id": {"zh": "会话ID", "en": "Session ID"},
    "capture.col_name": {"zh": "名称", "en": "Name"},
    "capture.col_status": {"zh": "状态", "en": "Status"},
    "capture.col_cameras": {"zh": "相机数", "en": "Cameras"},
    "capture.col_target": {"zh": "目标数", "en": "Target"},
    "capture.col_captured": {"zh": "已采集", "en": "Captured"},
    "capture.start": {"zh": "▶ 开始采集", "en": "▶ Start Capture"},
    "capture.stop": {"zh": "■ 停止采集", "en": "■ Stop Capture"},
    "capture.complete_msg": {"zh": "采集完成: {count} 张", "en": "Capture complete: {count} images"},
    "capture.cancelled_msg": {"zh": "采集已取消: {count} 张", "en": "Capture cancelled: {count} images"},
    "capture.capture_error": {"zh": "采集错误", "en": "Capture Error"},
    "capture.skip_corrupt": {"zh": "跳过损坏图片: {name}", "en": "Skipping corrupt image: {name}"},
    "capture.progress_msg": {"zh": "[{cam}] {name} ({current}/{total})", "en": "[{cam}] {name} ({current}/{total})"},

    # Create session dialog
    "session.title": {"zh": "新建采集会话", "en": "New Capture Session"},
    "session.name": {"zh": "名称:", "en": "Name:"},
    "session.name_placeholder": {"zh": "会话名称", "en": "Session name"},
    "session.camera_count": {"zh": "相机数量:", "en": "Camera Count:"},
    "session.target_count": {"zh": "目标采集数:", "en": "Target Count:"},
    "session.watch_dir_label": {"zh": "相机监听目录（可选，留空则不监听）:", "en": "Camera watch directories (optional):"},
    "session.watch_dir_placeholder": {"zh": "相机{cam}监听目录路径", "en": "Camera {cam} watch directory"},
    "session.camera_label": {"zh": "相机{cam}:", "en": "Camera {cam}:"},
    "session.default_name": {"zh": "未命名会话", "en": "Unnamed Session"},

    # Classification page
    "classify.title": {"zh": "样本分类", "en": "Sample Classification"},
    "classify.session_label": {"zh": "采集会话:", "en": "Capture Session:"},
    "classify.select_session": {"zh": "-- 选择会话 --", "en": "-- Select Session --"},
    "classify.stats_title": {"zh": "分类统计", "en": "Classification Stats"},
    "classify.current_label": {"zh": "当前: {current}/{total} | 标签: {label}", "en": "Current: {current}/{total} | Label: {label}"},
    "classify.no_images": {"zh": "无图片", "en": "No images"},
    "classify.unlabeled": {"zh": "未标注", "en": "Unlabeled"},
    "classify.saved": {"zh": "已保存 {count} 条分类记录到数据库", "en": "Saved {count} classification records to database"},
    "classify.save": {"zh": "保存", "en": "Save"},
    "classify.import_folder": {"zh": "导入本地文件夹", "en": "Import Folder"},
    "classify.imported": {"zh": "已导入 {count} 张图片", "en": "Imported {count} images"},

    # Classification labels
    "label.OK": {"zh": "OK", "en": "OK"},
    "label.NG_A": {"zh": "NG_A", "en": "NG_A"},
    "label.NG_B": {"zh": "NG_B", "en": "NG_B"},
    "label.UNKNOWN": {"zh": "UNKNOWN", "en": "UNKNOWN"},
    "label.INTERFERENCE": {"zh": "INTERFERENCE", "en": "INTERFERENCE"},
    "label.UNCERTAIN": {"zh": "UNCERTAIN", "en": "UNCERTAIN"},

    # Shortcuts
    "shortcut.hints": {"zh": "1=OK 2=NG_A 3=NG_B 4=UNKNOWN 5=INTERFERENCE 6=UNCERTAIN A=上一张 D=下一张 Space=跳过 Ctrl+S=保存", "en": "1=OK 2=NG_A 3=NG_B 4=UNKNOWN 5=INTERFERENCE 6=UNCERTAIN A=Prev D=Next Space=Skip Ctrl+S=Save"},

    # Thumbnail grid
    "thumb.filter_camera": {"zh": "相机:", "en": "Camera:"},
    "thumb.filter_label": {"zh": "标签:", "en": "Label:"},
    "thumb.count": {"zh": "{count} 张", "en": "{count} images"},

    # Image viewer
    "image.load_error": {"zh": "无法加载图片", "en": "Cannot load image"},

    # Dataset page
    "dataset.title": {"zh": "样本集版本", "en": "Dataset Versions"},
    "dataset.available_sessions": {"zh": "可用的采集会话（选择一个以生成样本集）:", "en": "Available sessions (select one to generate dataset):"},
    "dataset.col_id": {"zh": "会话ID", "en": "Session ID"},
    "dataset.col_name": {"zh": "名称", "en": "Name"},
    "dataset.col_classified": {"zh": "已分类", "en": "Classified"},
    "dataset.col_distribution": {"zh": "分类分布", "en": "Distribution"},
    "dataset.generate": {"zh": "生成样本集版本", "en": "Generate Dataset Version"},
    "dataset.generated": {"zh": "样本集已生成:\n{path}\n\n版本: {version}", "en": "Dataset generated:\n{path}\n\nVersion: {version}"},

    # Training page
    "training.title": {"zh": "训练配置", "en": "Training Config"},
    "training.dataset_group": {"zh": "数据集配置", "en": "Dataset Config"},
    "training.dataset_source": {"zh": "数据源(采集会话):", "en": "Data Source (Session):"},
    "training.dataset_path": {"zh": "路径:", "en": "Path:"},
    "training.param_group": {"zh": "训练参数", "en": "Training Parameters"},
    "training.base_model": {"zh": "基础模型:", "en": "Base Model:"},
    "training.epochs": {"zh": "Epochs:", "en": "Epochs:"},
    "training.imgsz": {"zh": "Image Size:", "en": "Image Size:"},
    "training.batch": {"zh": "Batch:", "en": "Batch:"},
    "training.device": {"zh": "Device:", "en": "Device:"},
    "training.job_name": {"zh": "任务名称:", "en": "Job Name:"},
    "training.job_name_placeholder": {"zh": "训练任务名称", "en": "Training job name"},
    "training.start": {"zh": "▶ 开始训练", "en": "▶ Start Training"},
    "training.stop": {"zh": "■ 停止", "en": "■ Stop"},
    "training.loading_base": {"zh": "加载基础模型: {model}", "en": "Loading base model: {model}"},
    "training.starting": {"zh": "开始训练: epochs={epochs}, imgsz={imgsz}, batch={batch}", "en": "Starting training: epochs={epochs}, imgsz={imgsz}, batch={batch}"},
    "training.completed": {"zh": "训练完成！最佳模型: {path}", "en": "Training complete! Best model: {path}"},
    "training.failed": {"zh": "训练失败: {error}", "en": "Training failed: {error}"},
    "training.complete_label": {"zh": "训练完成", "en": "Training Complete"},
    "training.error_title": {"zh": "训练错误", "en": "Training Error"},

    # Training jobs page
    "jobs.title": {"zh": "训练任务", "en": "Training Jobs"},
    "jobs.col_id": {"zh": "任务ID", "en": "Job ID"},
    "jobs.col_name": {"zh": "名称", "en": "Name"},
    "jobs.col_model": {"zh": "模型", "en": "Model"},
    "jobs.col_dataset": {"zh": "数据集", "en": "Dataset"},
    "jobs.col_start": {"zh": "开始时间", "en": "Start Time"},
    "jobs.col_end": {"zh": "结束时间", "en": "End Time"},
    "jobs.col_best": {"zh": "最佳模型", "en": "Best Model"},
    "jobs.delete_confirm": {"zh": "删除训练任务「{id}」?", "en": "Delete training job \"{id}\"?"},

    # Model version page
    "model.title": {"zh": "模型版本", "en": "Model Versions"},
    "model.register": {"zh": "+ 注册模型", "en": "+ Register Model"},
    "model.col_id": {"zh": "模型ID", "en": "Model ID"},
    "model.col_type": {"zh": "类型", "en": "Type"},
    "model.col_base": {"zh": "基础模型", "en": "Base Model"},
    "model.col_created": {"zh": "创建时间", "en": "Created"},
    "model.status_mgmt": {"zh": "状态管理:", "en": "Status Management:"},
    "model.set_status": {"zh": "设置状态", "en": "Set Status"},
    "model.register_title": {"zh": "注册模型版本", "en": "Register Model Version"},
    "model.model_name": {"zh": "模型名称:", "en": "Model Name:"},
    "model.model_type": {"zh": "模型类型:", "en": "Model Type:"},
    "model.model_path": {"zh": "模型路径:", "en": "Model Path:"},
    "model.model_path_placeholder": {"zh": "模型文件路径 (.pt / .onnx)", "en": "Model file path (.pt / .onnx)"},
    "model.base_model": {"zh": "基础模型:", "en": "Base Model:"},
    "model.base_placeholder": {"zh": "如 yolov8n.pt", "en": "e.g. yolov8n.pt"},
    "model.delete_confirm": {"zh": "删除模型「{id}」?", "en": "Delete model \"{id}\"?"},

    # Inference page
    "inference.title": {"zh": "模型推理", "en": "Model Inference"},
    "inference.model": {"zh": "模型:", "en": "Model:"},
    "inference.image_dir": {"zh": "图片目录:", "en": "Image Dir:"},
    "inference.select_dir": {"zh": "选择目录", "en": "Select Directory"},
    "inference.run": {"zh": "▶ 运行推理", "en": "▶ Run Inference"},
    "inference.browse": {"zh": "浏览:", "en": "Browse:"},
    "inference.prev": {"zh": "< 上一张", "en": "< Previous"},
    "inference.next": {"zh": "下一张 >", "en": "Next >"},
    "inference.position": {"zh": "{current} / {total}", "en": "{current} / {total}"},
    "inference.col_class": {"zh": "类别", "en": "Class"},
    "inference.col_conf": {"zh": "置信度", "en": "Confidence"},
    "inference.col_bbox": {"zh": "检测框", "en": "BBox"},
    "inference.col_area": {"zh": "面积", "en": "Area"},
    "inference.model_path_empty": {"zh": "模型路径为空", "en": "Model path is empty"},
    "inference.inference_error": {"zh": "推理错误", "en": "Inference Error"},
    "inference.failed": {"zh": "推理失败 [{path}]: {error}", "en": "Inference failed [{path}]: {error}"},
    "inference.unsupported_model": {"zh": "不支持的模型类型: {type}", "en": "Unsupported model type: {type}"},
    "inference.select_image_dir_first": {"zh": "请先选择图片目录", "en": "Please select an image directory first"},

    # Defect overlay
    "defect.show_boxes": {"zh": "显示检测框", "en": "Show Detection Boxes"},
    "defect.detection_count": {"zh": "检测数: {count}", "en": "Detections: {count}"},

    # Evaluation page
    "eval.title": {"zh": "评估报告", "en": "Evaluation Report"},
    "eval.model": {"zh": "模型:", "en": "Model:"},
    "eval.image_dir": {"zh": "图片目录:", "en": "Image Dir:"},
    "eval.label_dir": {"zh": "标签目录:", "en": "Label Dir:"},
    "eval.select_images": {"zh": "选择图片", "en": "Select Images"},
    "eval.select_labels": {"zh": "选择标签", "en": "Select Labels"},
    "eval.run": {"zh": "▶ 运行评估", "en": "▶ Run Evaluation"},
    "eval.map50": {"zh": "mAP@0.5: {value}", "en": "mAP@0.5: {value}"},
    "eval.map50_95": {"zh": "mAP@0.5:0.95: {value}", "en": "mAP@0.5:0.95: {value}"},
    "eval.map50_na": {"zh": "mAP@0.5: —", "en": "mAP@0.5: —"},
    "eval.need_gt": {"zh": "mAP@0.5: — (需要 ground truth 标注)", "en": "mAP@0.5: — (needs ground truth labels)"},
    "eval.eval_error": {"zh": "评估出错: {error}", "en": "Evaluation error: {error}"},
    "eval.completed": {"zh": "评估完成: {images} 张图片 | GT 标注: {gt_images} 张 | 预测框: {boxes}", "en": "Evaluation complete: {images} images | GT: {gt_images} | Predictions: {boxes}"},
    "eval.waiting": {"zh": "评估结果将显示在这里", "en": "Evaluation results will appear here"},
    "eval.col_class": {"zh": "类别", "en": "Class"},
    "eval.col_ap50": {"zh": "AP@0.5", "en": "AP@0.5"},
    "eval.col_ap50_95": {"zh": "AP@0.5:0.95", "en": "AP@0.5:0.95"},
    "eval.confusion_matrix": {"zh": "混淆矩阵将在评估后显示", "en": "Confusion matrix will appear after evaluation"},
    "eval.select_label_dir_first": {"zh": "请选择标签目录", "en": "Please select a label directory"},
    "eval.error_title": {"zh": "评估错误", "en": "Evaluation Error"},

    # Model comparison page
    "compare.title": {"zh": "模型对比", "en": "Model Comparison"},
    "compare.hint": {"zh": "模型版本列表（选择行 → 添加到对比）:", "en": "Model list (select row → add to comparison):"},
    "compare.add": {"zh": "+ 添加到对比表", "en": "+ Add to Comparison"},
    "compare.clear": {"zh": "清空对比表", "en": "Clear Comparison"},
    "compare.compared": {"zh": "对比表:", "en": "Comparison:"},
    "compare.col_metrics": {"zh": "指标", "en": "Metrics"},

    # Production run page
    "production.title": {"zh": "生产运行", "en": "Production Run"},
    "production.model": {"zh": "模型:", "en": "Model:"},
    "production.watch_dir": {"zh": "监听目录:", "en": "Watch Dir:"},
    "production.start": {"zh": "▶ 开始检测", "en": "▶ Start Detection"},
    "production.stop": {"zh": "■ 停止", "en": "■ Stop"},
    "production.live_view": {"zh": "实时画面", "en": "Live View"},
    "production.cam_status": {"zh": "相机状态", "en": "Camera Status"},
    "production.cam_offline": {"zh": "相机{i}: 离线", "en": "Camera {i}: Offline"},
    "production.cam_status_fmt": {"zh": "{cam}: {fps} FPS | {frames} frames", "en": "{cam}: {fps} FPS | {frames} frames"},
    "production.recent_ng": {"zh": "最近 NG 图像", "en": "Recent NG Images"},
    "production.no_ng": {"zh": "无 NG", "en": "No NG"},
    "production.defect_events": {"zh": "缺陷事件", "en": "Defect Events"},
    "production.col_time": {"zh": "时间", "en": "Time"},
    "production.col_camera": {"zh": "相机", "en": "Camera"},
    "production.col_dets": {"zh": "检测数", "en": "Detections"},
    "production.col_ng": {"zh": "状态", "en": "Status"},
    "production.ng": {"zh": "NG", "en": "NG"},
    "production.model_load_failed": {"zh": "加载模型失败", "en": "Model Load Failed"},
    "production.select_watch_dir": {"zh": "请选择监听目录", "en": "Please select a watch directory"},

    # Device config page
    "device.title": {"zh": "设备总览", "en": "Device Overview"},
    "device.registered_adapters": {"zh": "已注册的相机适配器:", "en": "Registered Camera Adapters:"},
    "device.col_adapter": {"zh": "适配器名称", "en": "Adapter Name"},
    "device.col_type": {"zh": "类型", "en": "Type"},
    "device.col_status": {"zh": "状态", "en": "Status"},
    "device.col_devices": {"zh": "可用设备", "en": "Available Devices"},
    "device.adapter_status": {"zh": "适配器状态", "en": "Adapter Status"},
    "device.no_devices": {"zh": "无设备", "en": "No devices"},
    "device.ready": {"zh": "就绪 ({count} 设备)", "en": "Ready ({count} devices)"},
    "device.sdk_missing": {"zh": "SDK 未安装", "en": "SDK not installed"},
    "device.status_error": {"zh": "错误", "en": "Error"},
    "device.status_text": {"zh": "FolderWatcherCameraAdapter: 可用（目录监听模拟相机）\nHikvisionMVSAdapter: 需安装海康 MVS SDK\nBaslerPylonAdapter: 需安装 pypylon", "en": "FolderWatcherCameraAdapter: Ready (directory watch)\nHikvisionMVSAdapter: Requires MVS SDK\nBaslerPylonAdapter: Requires pypylon"},

    # Camera config page
    "camera.title": {"zh": "相机配置", "en": "Camera Configuration"},
    "camera.group": {"zh": "相机 {i}", "en": "Camera {i}"},
    "camera.adapter": {"zh": "适配器:", "en": "Adapter:"},
    "camera.watch_dir": {"zh": "监听目录:", "en": "Watch Dir:"},
    "camera.watch_dir_placeholder": {"zh": "相机{i} 监听目录", "en": "Camera {i} watch directory"},
    "camera.folder_watcher": {"zh": "目录监听", "en": "Folder Watcher"},
    "camera.hikvision_stub": {"zh": "海康 MVS (未安装)", "en": "Hikvision MVS (not installed)"},
    "camera.basler_stub": {"zh": "Basler Pylon (未安装)", "en": "Basler Pylon (not installed)"},

    # PLC config page
    "plc.title": {"zh": "PLC配置", "en": "PLC Configuration"},
    "plc.group": {"zh": "PLC 通讯配置", "en": "PLC Communication Config"},
    "plc.method": {"zh": "通讯方式:", "en": "Method:"},
    "plc.host": {"zh": "主机地址:", "en": "Host:"},
    "plc.port": {"zh": "端口:", "en": "Port:"},
    "plc.not_connected": {"zh": "未连接", "en": "Not connected"},
    "plc.test": {"zh": "测试连接", "en": "Test Connection"},
    "plc.connected": {"zh": "连接成功", "en": "Connected"},
    "plc.connect_failed": {"zh": "连接失败", "en": "Connection failed"},
    "plc.not_supported": {"zh": "{method}: 暂不支持自动测试", "en": "{method}: Auto-test not supported yet"},

    # Encoder config page
    "encoder.title": {"zh": "编码器配置", "en": "Encoder Configuration"},
    "encoder.group": {"zh": "编码器配置", "en": "Encoder Configuration"},
    "encoder.type": {"zh": "编码器类型:", "en": "Encoder Type:"},
    "encoder.simulated": {"zh": "模拟 (内部时钟)", "en": "Simulated (Internal Clock)"},
    "encoder.rs422": {"zh": "RS422 编码器 (预留)", "en": "RS422 Encoder (Reserved)"},
    "encoder.ethercat": {"zh": "EtherCAT (预留)", "en": "EtherCAT (Reserved)"},
    "encoder.resolution": {"zh": "分辨率:", "en": "Resolution:"},
    "encoder.ppm": {"zh": "脉冲/米", "en": "pulses/m"},
    "encoder.line_speed": {"zh": "线速度:", "en": "Line Speed:"},
    "encoder.m_min": {"zh": "m/min", "en": "m/min"},
    "encoder.status": {"zh": "状态: 模拟模式运行中", "en": "Status: Simulated mode running"},

    # Defect trace page
    "trace.title": {"zh": "缺陷追溯", "en": "Defect Trace"},
    "trace.session": {"zh": "会话:", "en": "Session:"},
    "trace.label_filter": {"zh": "标签:", "en": "Label:"},
    "trace.query": {"zh": "查询", "en": "Query"},
    "trace.col_image": {"zh": "图片名称", "en": "Image Name"},
    "trace.col_camera": {"zh": "相机", "en": "Camera"},
    "trace.col_label": {"zh": "标签", "en": "Label"},
    "trace.col_width": {"zh": "宽度", "en": "Width"},
    "trace.col_height": {"zh": "高度", "en": "Height"},
    "trace.stats": {"zh": "总计: {total} | 分类分布: {distribution}", "en": "Total: {total} | Distribution: {distribution}"},

    # Report page
    "report.title": {"zh": "报告中心", "en": "Report Center"},
    "report.type": {"zh": "报告类型:", "en": "Report Type:"},
    "report.project": {"zh": "项目报告", "en": "Project Report"},
    "report.batch": {"zh": "批次报告", "en": "Batch Report"},
    "report.system": {"zh": "系统报告", "en": "System Report"},
    "report.generate": {"zh": "生成报告", "en": "Generate Report"},
    "report.saved_to": {"zh": "报告已保存到:\n{path}", "en": "Report saved to:\n{path}"},
    "report.generated_to": {"zh": "报告已生成: {path}", "en": "Report generated: {path}"},
    "report.error_title": {"zh": "报告生成错误", "en": "Report Generation Error"},

    # System settings page
    "settings.title": {"zh": "系统设置", "en": "System Settings"},
    "settings.paths_group": {"zh": "目录配置", "en": "Directory Configuration"},
    "settings.data_dir": {"zh": "数据目录:", "en": "Data Directory:"},
    "settings.model_dir": {"zh": "模型目录:", "en": "Model Directory:"},
    "settings.log_dir": {"zh": "日志目录:", "en": "Log Directory:"},
    "settings.db_path": {"zh": "数据库:", "en": "Database:"},
    "settings.health_group": {"zh": "系统健康", "en": "System Health"},
    "settings.disk": {"zh": "磁盘:", "en": "Disk:"},
    "settings.uptime": {"zh": "运行时间:", "en": "Uptime:"},
    "settings.cpu": {"zh": "CPU:", "en": "CPU:"},
    "settings.memory": {"zh": "内存:", "en": "Memory:"},
    "settings.version_group": {"zh": "软件版本", "en": "Software Version"},
    "settings.version_app": {"zh": "应用:", "en": "Application:"},
    "settings.version_num": {"zh": "版本:", "en": "Version:"},
    "settings.version_phase": {"zh": "阶段:", "en": "Phase:"},
    "settings.version_phase_value": {"zh": "Phase 5 — 本地桌面版", "en": "Phase 5 — Desktop Edition"},
    "settings.disk_fmt": {"zh": "剩余 {free:.1f} / {total:.1f} GB ({pct}%)", "en": "{free:.1f} / {total:.1f} GB free ({pct}%)"},
    "settings.uptime_fmt": {"zh": "{h}h {m}m {s}s", "en": "{h}h {m}m {s}s"},
    "settings.cpu_na": {"zh": "N/A", "en": "N/A"},

    # Language switch
    "settings.language_group": {"zh": "语言 / Language", "en": "Language / 语言"},
    "settings.language_label": {"zh": "界面语言:", "en": "Language:"},
    "settings.language_zh": {"zh": "中文", "en": "中文"},
    "settings.language_en": {"zh": "English", "en": "English"},

    # Log viewer
    "log.clear": {"zh": "清空", "en": "Clear"},
    "log.save": {"zh": "保存日志", "en": "Save Log"},
    "log.auto_scroll_on": {"zh": "自动滚动: ON", "en": "Auto-scroll: ON"},
    "log.auto_scroll_off": {"zh": "自动滚动: OFF", "en": "Auto-scroll: OFF"},
    "log.save_title": {"zh": "保存日志", "en": "Save Log"},
    "log.save_filter": {"zh": "文本文件 (*.txt);;所有文件 (*)", "en": "Text Files (*.txt);;All Files (*)"},

    # Report worker
    "worker.report_project_title": {"zh": "# 项目检测报告", "en": "# Project Inspection Report"},
    "worker.report_batch_title": {"zh": "# 批次检测报告", "en": "# Batch Inspection Report"},
    "worker.report_system_title": {"zh": "# 系统运行报告", "en": "# System Status Report"},
    "worker.report_generated_time": {"zh": "生成时间", "en": "Generated"},
    "worker.report_project_section": {"zh": "## 项目概览", "en": "## Project Overview"},
    "worker.report_model_section": {"zh": "## 模型信息", "en": "## Model Info"},
    "worker.report_sample_section": {"zh": "## 样本统计", "en": "## Sample Statistics"},
    "worker.report_batch_section": {"zh": "## 批次信息", "en": "## Batch Info"},
    "worker.report_defect_section": {"zh": "## 缺陷分布", "en": "## Defect Distribution"},
    "worker.report_system_section": {"zh": "## 系统状态", "en": "## System Status"},
    "worker.report_footer": {"zh": "报告由 CX-vision {version} 自动生成", "en": "Report auto-generated by CX-vision {version}"},
    "worker.report_material": {"zh": "材质", "en": "Material"},
    "worker.report_morphology": {"zh": "形态", "en": "Morphology"},
    "worker.report_line_speed": {"zh": "线速度", "en": "Line Speed"},
    "worker.report_camera_count": {"zh": "相机数量", "en": "Camera Count"},
    "worker.report_total_samples": {"zh": "总样本数", "en": "Total Samples"},
    "worker.report_batch_id": {"zh": "批次号", "en": "Batch ID"},
    "worker.report_start_time": {"zh": "开始时间", "en": "Start Time"},
    "worker.report_end_time": {"zh": "结束时间", "en": "End Time"},
    "worker.report_total_inspected": {"zh": "检测总数", "en": "Total Inspected"},
    "worker.report_ng_count": {"zh": "NG 数量", "en": "NG Count"},
    "worker.report_ng_rate": {"zh": "NG 率", "en": "NG Rate"},
    "worker.report_uptime": {"zh": "运行时间", "en": "Uptime"},
    "worker.report_disk_usage": {"zh": "磁盘使用", "en": "Disk Usage"},
    "worker.report_disk_free": {"zh": "磁盘剩余", "en": "Disk Free"},
    "worker.report_platform": {"zh": "平台", "en": "Platform"},
    "worker.report_model_name": {"zh": "模型版本", "en": "Model Version"},
    "worker.report_model_path": {"zh": "模型路径", "en": "Model Path"},
}

# ── I18n Manager ───────────────────────────────────────────────────

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "language.json",
)


# ── Live language switching registry ─────────────────────────────────

_BINDINGS: list[dict] = []


def bind(widget, key: str, *, setter: str = "setText", **fmt_kwargs):
    """Set translated text on widget AND register for live language switching.

    When language changes, all bind() calls are automatically re-applied.

    Usage:
        bind(label, "app.title")
        bind(button, "app.save")
        bind(group, "training.param_group", setter="setTitle")
        bind(window, "app.title", setter="setWindowTitle")
    """
    text = I18nManager._lookup(key, I18nManager._current_lang(), **fmt_kwargs)
    getattr(widget, setter)(text)
    _BINDINGS.append({"widget": widget, "key": key, "setter": setter, "fmt_kwargs": fmt_kwargs})


def _refresh_all_bindings(lang: str) -> None:
    for b in _BINDINGS:
        text = I18nManager._lookup(b["key"], lang, **b["fmt_kwargs"])
        getattr(b["widget"], b["setter"])(text)


class I18nManager(QObject):
    """Singleton managing current language and translation lookup."""

    language_changed = Signal(str)

    _instance: I18nManager | None = None
    SUPPORTED = {"zh", "en"}
    _lang = "zh"

    def __init__(self) -> None:
        if I18nManager._instance is not None:
            raise RuntimeError("Use I18nManager.instance()")
        super().__init__()
        I18nManager._instance = self
        self._load_preference()
        self.language_changed.connect(_refresh_all_bindings)

    @classmethod
    def _current_lang(cls) -> str:
        return cls._lang

    @classmethod
    def _lookup(cls, key: str, lang: str, **fmt_kwargs) -> str:
        entry = _STRINGS.get(key, {})
        text = entry.get(lang, entry.get("zh", key))
        if fmt_kwargs:
            text = text.format(**fmt_kwargs)
        return text

    @classmethod
    def instance(cls) -> I18nManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def language(self) -> str:
        return self._lang

    def set_language(self, lang: str) -> None:
        if lang not in self.SUPPORTED:
            return
        if lang != self._lang:
            self._lang = lang
            self._save_preference()
            self.language_changed.emit(lang)

    def tr(self, key: str, **kwargs) -> str:
        """Look up translation by key. Falls back to key if not found."""
        return self._lookup(key, self._lang, **kwargs)

    def _load_preference(self) -> None:
        try:
            if os.path.exists(_CONFIG_PATH):
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    lang = data.get("language", "zh")
                    if lang in self.SUPPORTED:
                        self._lang = lang
        except Exception:
            self._lang = "zh"

    def _save_preference(self) -> None:
        try:
            os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"language": self._lang}, f)
        except Exception:
            pass


# ── Module-level shortcut ──────────────────────────────────────────

def tr(key: str, **kwargs) -> str:
    """Shortcut: tr('key') returns translated string in current language."""
    return I18nManager.instance().tr(key, **kwargs)
