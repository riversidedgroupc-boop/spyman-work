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
    "app.version": {"zh": "v0.6.0", "en": "v0.6.0"},
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

    "nav.brand": {"zh": "表面缺陷视觉检测", "en": "Surface Defect Vision"},
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
    "model.col_active": {"zh": "在线", "en": "Active"},
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
    "production.cam_status_fmt": {"zh": "{cam}: {fps} FPS | {frames} fr | {pos} m", "en": "{cam}: {fps} FPS | {frames} fr | {pos} m"},
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
    "trace.source": {"zh": "数据源:", "en": "Source:"},
    "trace.source_samples": {"zh": "采集样本", "en": "Captured Samples"},
    "trace.source_events": {"zh": "生产缺陷事件", "en": "Production Defect Events"},
    "trace.session": {"zh": "会话:", "en": "Session:"},
    "trace.label_filter": {"zh": "标签:", "en": "Label:"},
    "trace.query": {"zh": "查询", "en": "Query"},
    "trace.col_image": {"zh": "图片名称", "en": "Image Name"},
    "trace.col_camera": {"zh": "相机", "en": "Camera"},
    "trace.col_label": {"zh": "标签", "en": "Label"},
    "trace.col_width": {"zh": "宽度", "en": "Width"},
    "trace.col_height": {"zh": "高度", "en": "Height"},
    "trace.date_from": {"zh": "从:", "en": "From:"},
    "trace.date_to": {"zh": "到:", "en": "To:"},
    "trace.stats": {"zh": "总计: {total} | 分类分布: {distribution}", "en": "Total: {total} | Distribution: {distribution}"},
    "trace.stats_events": {"zh": "总计: {total} | 缺陷类型: {distribution}", "en": "Total: {total} | Defect Types: {distribution}"},
    "trace.histogram_tip": {"zh": "位置范围: {min_p}m ~ {max_p}m | 事件数: {count}", "en": "Position: {min_p}m ~ {max_p}m | Events: {count}"},

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

    # ── V6 additions ──────────────────────────────────────────────────

    # Navigation
    "nav.log_center": {"zh": "日志中心", "en": "Log Center"},
    "nav.backup": {"zh": "备份恢复", "en": "Backup & Restore"},
    "nav.benchmark": {"zh": "压测中心", "en": "Benchmark"},
    "nav.monitor": {"zh": "性能监控", "en": "Monitor"},

    # ── V7.5 Camera Management ───────────────────────────────────────
    "camera.management": {"zh": "相机管理", "en": "Camera Mgmt"},
    "camera.scan": {"zh": "扫描设备", "en": "Scan Devices"},
    "camera.bind_connect": {"zh": "绑定并连接", "en": "Bind & Connect"},
    "camera.connect_all": {"zh": "全部连接", "en": "Connect All"},
    "camera.disconnect_all": {"zh": "全部断开", "en": "Disconnect All"},
    "camera.save_binding": {"zh": "保存绑定", "en": "Save Binding"},
    "camera.unbind": {"zh": "解绑", "en": "Unbind"},
    "camera.start_preview": {"zh": "开始预览", "en": "Start Preview"},
    "camera.stop_preview": {"zh": "停止预览", "en": "Stop Preview"},
    "camera.snapshot": {"zh": "保存快照", "en": "Save Snapshot"},
    "camera.apply_params": {"zh": "应用到选中相机", "en": "Apply to Selected"},
    "camera.save_template": {"zh": "保存模板", "en": "Save Template"},
    "camera.load_template": {"zh": "加载模板", "en": "Load Template"},
    "camera.reset_params": {"zh": "恢复默认", "en": "Reset Defaults"},

    # Camera Config (V6)
    "camera.adapter_type": {"zh": "适配器类型:", "en": "Adapter Type:"},
    "camera.connection_params": {"zh": "连接参数:", "en": "Connection Params:"},
    "camera.device_id": {"zh": "设备ID:", "en": "Device ID:"},
    "camera.exposure_us": {"zh": "曝光时间 (µs):", "en": "Exposure (µs):"},
    "camera.gain_db": {"zh": "增益 (dB):", "en": "Gain (dB):"},
    "camera.trigger_mode": {"zh": "触发模式:", "en": "Trigger Mode:"},
    "camera.trigger_continuous": {"zh": "连续采集", "en": "Continuous"},
    "camera.trigger_external": {"zh": "硬件触发", "en": "External Trigger"},
    "camera.trigger_software": {"zh": "软件触发", "en": "Software Trigger"},
    "camera.roi": {"zh": "ROI:", "en": "ROI:"},
    "camera.roi_x": {"zh": "X:", "en": "X:"},
    "camera.roi_y": {"zh": "Y:", "en": "Y:"},
    "camera.roi_w": {"zh": "W:", "en": "W:"},
    "camera.roi_h": {"zh": "H:", "en": "H:"},
    "camera.model_binding": {"zh": "绑定模型:", "en": "Model Binding:"},
    "camera.enabled": {"zh": "启用", "en": "Enabled"},
    "camera.disabled": {"zh": "禁用", "en": "Disabled"},
    "camera.config_saved": {"zh": "相机配置已保存 ({count}/{total})", "en": "Camera config saved ({count}/{total})"},
    "camera.no_configs": {"zh": "无相机配置", "en": "No camera configs"},
    "camera.config_count": {"zh": "{count} 个相机已配置", "en": "{count} camera(s) configured"},

    # Production — V6 multi-camera
    "production.camera_tabs": {"zh": "相机 {i}", "en": "Camera {i}"},
    "production.camera_count_label": {"zh": "相机数量: {count}", "en": "Camera Count: {count}"},
    "production.no_cameras": {"zh": "请先在设备配置中配置相机", "en": "Please configure cameras in Device Config"},
    "production.sampling_mode": {"zh": "采样模式:", "en": "Sampling Mode:"},
    "production.sampling_directory_watch": {"zh": "目录监听", "en": "Directory Watch"},
    "production.sampling_by_time": {"zh": "按时间", "en": "By Time"},
    "production.sampling_by_distance": {"zh": "按距离", "en": "By Distance"},
    "production.sampling_manual": {"zh": "手动触发", "en": "Manual Trigger"},
    "production.interval_seconds": {"zh": "间隔 (秒):", "en": "Interval (s):"},
    "production.distance_meters": {"zh": "距离 (米):", "en": "Distance (m):"},
    "production.manual_trigger": {"zh": "手动抓图", "en": "Manual Capture"},
    "production.encoder_position": {"zh": "当前位置: {pos:.3f} m", "en": "Position: {pos:.3f} m"},

    # Defect trace — V6 extended fields
    "defect.model_version": {"zh": "模型版本", "en": "Model Version"},
    "defect.defect_type": {"zh": "缺陷类型", "en": "Defect Type"},
    "defect.position_meter": {"zh": "位置 (m)", "en": "Position (m)"},

    # Classification labels — V6
    "label.NG_C": {"zh": "NG_C", "en": "NG_C"},
    "label.IGNORE": {"zh": "忽略", "en": "Ignore"},

    # Dataset Version (V6)
    "dataset_version.title": {"zh": "数据集版本", "en": "Dataset Versions"},
    "dataset_version.generate": {"zh": "生成数据集版本", "en": "Generate Dataset Version"},
    "dataset_version.generate_yolo": {"zh": "生成 YOLO 数据集", "en": "Generate YOLO Dataset"},
    "dataset_version.generate_anomaly": {"zh": "生成异常检测数据集", "en": "Generate Anomaly Dataset"},
    "dataset_version.history": {"zh": "版本历史", "en": "Version History"},
    "dataset_version.quality_score": {"zh": "质量评分: {score:.0f}/100", "en": "Quality Score: {score:.0f}/100"},
    "dataset_version.class_distribution": {"zh": "类别分布", "en": "Class Distribution"},
    "dataset_version.missing_bbox": {"zh": "缺失标注: {count}", "en": "Missing Labels: {count}"},
    "dataset_version.image_integrity": {"zh": "损坏图片: {count}", "en": "Corrupt Images: {count}"},
    "dataset_version.no_versions": {"zh": "暂无数据集版本", "en": "No dataset versions yet"},
    "dataset_version.delete_confirm": {"zh": "删除数据集版本「{name}」?", "en": "Delete dataset version \"{name}\"?"},
    "dataset_version.build_complete": {"zh": "数据集已生成:\n{path}\n图片: {images} 张\n质量评分: {score:.0f}/100", "en": "Dataset built:\n{path}\nImages: {images}\nQuality Score: {score:.0f}/100"},
    "dataset_version.col_version": {"zh": "版本名称", "en": "Version"},
    "dataset_version.col_source": {"zh": "类型", "en": "Type"},
    "dataset_version.col_images": {"zh": "图片数", "en": "Images"},
    "dataset_version.col_classes": {"zh": "类别", "en": "Classes"},
    "dataset_version.col_quality": {"zh": "质量评分", "en": "Quality"},
    "dataset_version.col_date": {"zh": "创建日期", "en": "Created"},

    # Log Center (V6)
    "log_center.title": {"zh": "日志中心", "en": "Log Center"},
    "log_center.tab_app": {"zh": "应用日志", "en": "App Log"},
    "log_center.tab_camera": {"zh": "相机日志", "en": "Camera Log"},
    "log_center.tab_inference": {"zh": "推理日志", "en": "Inference Log"},
    "log_center.tab_system": {"zh": "系统日志", "en": "System Log"},
    "log_center.tab_error": {"zh": "错误日志", "en": "Error Log"},
    "log_center.tab_audit": {"zh": "审计日志", "en": "Audit Log"},
    "log_center.filter_level": {"zh": "级别:", "en": "Level:"},
    "log_center.filter_search": {"zh": "搜索...", "en": "Search..."},
    "log_center.export": {"zh": "导出", "en": "Export"},
    "log_center.clear": {"zh": "清空", "en": "Clear"},
    "log_center.auto_refresh": {"zh": "自动刷新", "en": "Auto Refresh"},
    "log_center.no_logs": {"zh": "暂无日志", "en": "No logs"},

    # Backup/Restore (V6)
    "backup.title": {"zh": "备份恢复", "en": "Backup & Restore"},
    "backup.create": {"zh": "创建备份", "en": "Create Backup"},
    "backup.create_desc": {"zh": "备份数据库和配置文件", "en": "Backup database and configs"},
    "backup.include_db": {"zh": "数据库", "en": "Database"},
    "backup.include_configs": {"zh": "配置文件", "en": "Configs"},
    "backup.include_models": {"zh": "模型文件", "en": "Models"},
    "backup.list_title": {"zh": "备份历史", "en": "Backup History"},
    "backup.col_date": {"zh": "日期", "en": "Date"},
    "backup.col_name": {"zh": "名称", "en": "Name"},
    "backup.col_size": {"zh": "大小", "en": "Size"},
    "backup.col_items": {"zh": "内容", "en": "Items"},
    "backup.restore": {"zh": "恢复", "en": "Restore"},
    "backup.confirm_restore": {"zh": "恢复备份「{name}」？\n当前数据将被覆盖。", "en": "Restore backup \"{name}\"?\nCurrent data will be overwritten."},
    "backup.restored": {"zh": "备份已恢复", "en": "Backup restored"},
    "backup.deleted": {"zh": "备份已删除", "en": "Backup deleted"},
    "backup.in_progress": {"zh": "备份中...", "en": "Backing up..."},
    "backup.completed": {"zh": "备份完成: {name}", "en": "Backup completed: {name}"},
    "backup.no_backups": {"zh": "暂无备份", "en": "No backups yet"},

    # Model activation guards (V6)
    "model.active": {"zh": "在线", "en": "Active"},
    "model.inactive": {"zh": "离线", "en": "Inactive"},
    "model.activate_btn": {"zh": "设为在线模型", "en": "Set as Active"},
    "model.rollback_btn": {"zh": "回滚", "en": "Rollback"},
    "model.activate_confirm": {"zh": "将模型「{name}」设为当前在线模型？", "en": "Set model \"{name}\" as active?"},
    "model.activate_warning_other": {"zh": "当前已有在线模型「{other}」，将被替换。", "en": "Active model \"{other}\" will be replaced."},
    "model.rollback_confirm": {"zh": "回滚模型「{name}」？", "en": "Rollback model \"{name}\"?"},
    "model.activated": {"zh": "模型已上线: {name}", "en": "Model activated: {name}"},
    "model.rolled_back": {"zh": "模型已回滚: {name}", "en": "Model rolled back: {name}"},

    # Report formats (V6)
    "report.format_type": {"zh": "导出格式:", "en": "Export Format:"},
    "report.format_markdown": {"zh": "Markdown", "en": "Markdown"},
    "report.format_html": {"zh": "HTML", "en": "HTML"},
    "report.format_pdf": {"zh": "PDF", "en": "PDF"},
    "report.format_excel": {"zh": "Excel", "en": "Excel"},
    "report.format_csv": {"zh": "CSV", "en": "CSV"},
    "report.format_json": {"zh": "JSON", "en": "JSON"},
    "report.generating": {"zh": "生成中...", "en": "Generating..."},
    "report.pdf_fallback": {"zh": "fpdf2 未安装，已导出为 HTML 格式", "en": "fpdf2 not installed, exported as HTML instead"},

    # General app actions
    "app.delete_confirm": {"zh": "确认删除「{name}」?", "en": "Delete \"{name}\"?"},
    "app.select_item": {"zh": "请先选择一项", "en": "Please select an item first"},

    # Camera config dialog (Phase 1)
    "camera.dialog_title": {"zh": "相机 {i} 配置", "en": "Camera {i} Configuration"},
    "camera.basic_settings": {"zh": "基本设置", "en": "Basic Settings"},
    "camera.image_acq": {"zh": "图像采集", "en": "Image Acquisition"},
    "camera.invalid_connection_json": {"zh": "连接参数不是有效的JSON", "en": "Connection params must be valid JSON"},
    "camera.not_configured": {"zh": "未配置", "en": "Not configured"},
    "camera.configure": {"zh": "配置...", "en": "Configure..."},
    "camera.connect_failed": {"zh": "{cam}: 连接失败 — {err}", "en": "{cam}: Connect failed — {err}"},
    "camera.model_binding_placeholder": {"zh": "输入模型名称或路径", "en": "Enter model name or path"},

    # Navigation (Phase 1)
    "nav.camera_config": {"zh": "相机配置", "en": "Camera Config"},

    # Production — V6 sampling / encoder UI (Phase 1)
    "production.sampling_continuous": {"zh": "连续采集", "en": "Continuous"},
    "production.no_cameras_msg": {"zh": "没有可用的相机。请先在「相机配置」中配置至少一个相机。", "en": "No cameras available. Please configure at least one camera in Camera Config."},

    # General UI (Phase 1)
    "app.save_all": {"zh": "全部保存", "en": "Save All"},
    "app.select_spec_first": {"zh": "请先选择产品规格", "en": "Please select a product spec first"},

    # Encoder — live position and controls (Phase 1)
    "encoder.connect": {"zh": "连接", "en": "Connect"},
    "encoder.disconnect": {"zh": "断开", "en": "Disconnect"},
    "encoder.reset": {"zh": "复位", "en": "Reset"},
    "encoder.status_disconnected": {"zh": "状态: 未连接", "en": "Status: Disconnected"},
    "encoder.status_connected_simulated": {"zh": "状态: 模拟模式运行中", "en": "Status: Simulated mode running"},
    "encoder.status_connected_rs422": {"zh": "状态: RS422已连接（预留）", "en": "Status: RS422 connected (reserved)"},
    "encoder.status_fmt": {"zh": "位置: {pos:.3f} m | 速度: {speed:.1f} m/min", "en": "Pos: {pos:.3f} m | Speed: {speed:.1f} m/min"},
    "encoder.position_display": {"zh": "{pos} m", "en": "{pos} m"},
    "encoder.position": {"zh": "当前位置:", "en": "Current Position:"},
    "encoder.rs422_placeholder": {"zh": "RS422编码器功能将在后续版本中实现。当前仅支持模拟模式。", "en": "RS422 encoder will be implemented in a future version. Only simulated mode is available."},
    "encoder.ethercat_placeholder": {"zh": "EtherCAT编码器功能将在后续版本中实现。当前仅支持模拟模式。", "en": "EtherCAT encoder will be implemented in a future version. Only simulated mode is available."},

    # Navigation — Help
    "nav.help": {"zh": "帮助", "en": "Help"},

    # Help page
    "help.title": {"zh": "帮助", "en": "Help"},
    "help.overview": {"zh": "系统概览", "en": "System Overview"},
    "help.modules": {"zh": "功能模块", "en": "Feature Modules"},
    "help.sampling": {"zh": "采样模式", "en": "Sampling Modes"},
    "help.model_lifecycle": {"zh": "模型生命周期", "en": "Model Lifecycle"},
    "help.shortcuts": {"zh": "键盘快捷键", "en": "Keyboard Shortcuts"},
    "help.roadmap": {"zh": "V7 路线图", "en": "V7 Roadmap"},
    "help.toc": {"zh": "目录", "en": "Table of Contents"},

    # ── V7.5 Dataset Task Type ─────────────────────────────────────────
    "task.select_type": {"zh": "任务类型:", "en": "Task Type:"},
    "task.yolo_detection": {"zh": "YOLO 检测", "en": "YOLO Detection"},
    "task.image_classification": {"zh": "整图分类", "en": "Classification"},
    "task.anomaly_detection": {"zh": "异常检测", "en": "Anomaly Detection"},
    "task.yolo_hint": {"zh": "NG 图片需要 bbox 标注，缺少 bbox 的 NG 图片无法进入 YOLO 训练。", "en": "NG images require bbox annotation. NG images without bbox cannot be used for YOLO training."},
    "task.cls_hint": {"zh": "每张图片只需要一个整图标签，不需要 bbox 标注。", "en": "Each image only needs a single classification label, no bbox required."},
    "task.anomaly_hint": {"zh": "OK 图片用于训练，NG 图片用于验证/测试。", "en": "OK images for training, NG images for validation/testing."},
    "task.open_bbox": {"zh": "打开 bbox 标注", "en": "Open Bbox Annotation"},
    "task.check_bbox": {"zh": "检查 bbox 完整性", "en": "Check Bbox Completeness"},
    "task.generate_yolo": {"zh": "生成 YOLO 数据集", "en": "Generate YOLO Dataset"},
    "task.generate_cls": {"zh": "生成分类数据集", "en": "Generate Classification Dataset"},
    "task.generate_anomaly": {"zh": "生成异常检测数据集", "en": "Generate Anomaly Dataset"},

    # ── Bbox Annotation Page ──────────────────────────────────────────
    "bbox.page_title": {"zh": "bbox 标注", "en": "Bbox Annotation"},
    "bbox.session_label": {"zh": "采集会话:", "en": "Capture Session:"},
    "bbox.filter_all": {"zh": "全部", "en": "All"},
    "bbox.filter_no_bbox": {"zh": "无 bbox", "en": "No Bbox"},
    "bbox.filter_has_bbox": {"zh": "有 bbox", "en": "Has Bbox"},
    "bbox.filter_label": {"zh": "类别:", "en": "Class:"},
    "bbox.draw_mode": {"zh": "绘制模式", "en": "Draw Mode"},
    "bbox.save": {"zh": "保存", "en": "Save"},
    "bbox.clear_all": {"zh": "清除全部", "en": "Clear All"},
    "bbox.next_image": {"zh": "下一张 →", "en": "Next →"},
    "bbox.prev_image": {"zh": "← 上一张", "en": "← Prev"},
    "bbox.check_completeness": {"zh": "检查完整性", "en": "Check Completeness"},
    "bbox.progress": {"zh": "{current}/{total} | bbox: {bbox_count}", "en": "{current}/{total} | bbox: {bbox_count}"},
    "bbox.no_images": {"zh": "无图片", "en": "No images"},
    "bbox.auto_saved": {"zh": "已自动保存 bbox", "en": "Bbox auto-saved"},
    "bbox.validation_passed": {"zh": "✓ 校验通过 — 可以训练", "en": "✓ Validation passed — ready for training"},
    "bbox.validation_failed": {"zh": "✗ 校验失败 — {reason}", "en": "✗ Validation failed — {reason}"},
    "bbox.delete_bbox": {"zh": "删除此框", "en": "Delete Bbox"},
    "bbox.confirm_delete": {"zh": "确认删除 bbox？", "en": "Confirm delete bbox?"},

    # Navigation
    "nav.bbox_annotation": {"zh": "bbox 标注", "en": "Bbox Annotation"},

    # ── Phase B: Field Workflow ────────────────────────────────────────

    # Navigation
    "nav.field_workflow": {"zh": "现场交付流程", "en": "Field Workflow"},

    # Field workflow page
    "field_workflow.title": {"zh": "现场交付流程", "en": "Field Workflow"},
    "field_workflow.create_session": {"zh": "新建会话", "en": "New Session"},
    "field_workflow.refresh": {"zh": "刷新", "en": "Refresh"},
    "field_workflow.no_context": {
        "zh": "请先在顶部选择客户、项目和产品规格。",
        "en": "Please select a customer, project, and product spec first.",
    },
    "field_workflow.no_session": {
        "zh": "请先创建或选择一个现场会话。",
        "en": "Please create or select a field session first.",
    },
    "field_workflow.session": {"zh": "现场会话", "en": "Field Session"},
    "field_workflow.session_type": {"zh": "会话类型", "en": "Session Type"},
    "field_workflow.session_status": {"zh": "状态", "en": "Status"},
    "field_workflow.session_notes": {"zh": "备注", "en": "Notes"},
    "field_workflow.steps": {"zh": "工作流步骤", "en": "Workflow Steps"},
    "field_workflow.review_queue": {"zh": "异常复核队列", "en": "Anomaly Review Queue"},
    "field_workflow.candidate_detail": {"zh": "候选详情", "en": "Candidate Detail"},
    "field_workflow.defect_dictionary": {"zh": "缺陷字典", "en": "Defect Dictionary"},
    "field_workflow.confirm_defect": {"zh": "确认缺陷", "en": "Confirm Defect"},
    "field_workflow.mark_normal": {"zh": "标记正常", "en": "Mark Normal"},
    "field_workflow.mark_noise": {"zh": "标记噪声", "en": "Mark Noise"},
    "field_workflow.mark_texture": {"zh": "标记纹理", "en": "Mark Texture"},
    "field_workflow.mark_unknown": {"zh": "标记待定", "en": "Mark Unknown"},
    "field_workflow.reviewer": {"zh": "复核人", "en": "Reviewer"},
    "field_workflow.score": {"zh": "分数", "en": "Score"},
    "field_workflow.cluster": {"zh": "聚类", "en": "Cluster"},
    "field_workflow.image": {"zh": "图片", "en": "Image"},
    "field_workflow.assigned_defect": {"zh": "分配缺陷", "en": "Assigned Defect"},
    "field_workflow.reviewed_at": {"zh": "复核时间", "en": "Reviewed At"},
    "field_workflow.create_defect": {"zh": "新建缺陷类型", "en": "New Defect Type"},
    "field_workflow.code": {"zh": "编码", "en": "Code"},
    "field_workflow.name_zh": {"zh": "中文名", "en": "Name (ZH)"},
    "field_workflow.name_en": {"zh": "英文名", "en": "Name (EN)"},
    "field_workflow.severity": {"zh": "严重程度", "en": "Severity"},
    "field_workflow.description": {"zh": "描述", "en": "Description"},
    "field_workflow.is_ng": {"zh": "NG?", "en": "NG?"},
    "field_workflow.step_hardware": {"zh": "1. 硬件检查", "en": "1. Hardware Check"},
    "field_workflow.step_baseline": {"zh": "2. OK基准采集", "en": "2. OK Baseline Collection"},
    "field_workflow.step_exploration": {"zh": "3. 异常模式探索", "en": "3. Anomaly Exploration"},
    "field_workflow.step_review": {"zh": "4. 人工复核与缺陷字典", "en": "4. Human Review & Defect Dictionary"},
    "field_workflow.step_training": {"zh": "5. 首次YOLO训练", "en": "5. First YOLO Training"},
    "field_workflow.step_retest": {"zh": "6. 混合推理复检", "en": "6. Hybrid Production Retest"},
    "field_workflow.step_deploy": {"zh": "7. 部署打包与报告", "en": "7. Deployment & Report"},
    "field_workflow.status_blocked": {"zh": "⛔ 阻塞", "en": "⛔ Blocked"},
    "field_workflow.status_pending": {"zh": "⏳ 待执行", "en": "⏳ Pending"},
    "field_workflow.status_available": {"zh": "✅ 可用", "en": "✅ Available"},
    "field_workflow.status_active": {"zh": "🔄 进行中", "en": "🔄 Active"},
    # ── Phase C: Training Readiness ──
    "field_workflow.training_readiness": {"zh": "YOLO 首训准备", "en": "YOLO First-Training Readiness"},
    "field_workflow.training_ready": {"zh": "✅ 可训练", "en": "✅ Ready"},
    "field_workflow.training_not_ready": {"zh": "❌ 不可训练", "en": "❌ Not Ready"},
    "field_workflow.confirmed_defect_count": {"zh": "已确认缺陷", "en": "Confirmed Defects"},
    "field_workflow.defect_type_count": {"zh": "缺陷类别数", "en": "Defect Type Count"},
    "field_workflow.missing_bbox_count": {"zh": "缺标注", "en": "Missing BBox"},
    "field_workflow.skipped_unassigned": {"zh": "未分配缺陷类型", "en": "Unassigned Defect Type"},
    "field_workflow.pending_unknown_count": {"zh": "待定/未知", "en": "Pending/Unknown"},
    "field_workflow.generate_dataset": {"zh": "生成 YOLO 首训数据集", "en": "Generate YOLO First-Training Dataset"},
    "field_workflow.refresh_readiness": {"zh": "刷新训练准备状态", "en": "Refresh Training Readiness"},
    "field_workflow.dataset_generated": {"zh": "数据集已生成", "en": "Dataset Generated"},
    "field_workflow.dataset_path": {"zh": "数据集路径", "en": "Dataset Path"},
    "field_workflow.dataset_yaml": {"zh": "YAML 路径", "en": "YAML Path"},
    "field_workflow.version_label": {"zh": "版本", "en": "Version"},
    "field_workflow.no_confirmed_defect": {"zh": "没有已确认的缺陷，无法生成训练数据集。请先在复核队列中将异常标记为「确认缺陷」。", "en": "No confirmed defects. Please mark anomalies as 'Confirmed Defect' in the review queue first."},
    "field_workflow.dataset_build_failed": {"zh": "数据集生成失败", "en": "Dataset Build Failed"},

    # ── Phase E: Model Export / Acceleration ──────────────────────────────
    "export.title": {"zh": "模型导出/加速", "en": "Model Export"},
    "export.environment": {"zh": "环境信息", "en": "Environment"},
    "export.gpu": {"zh": "GPU", "en": "GPU"},
    "export.cuda": {"zh": "CUDA", "en": "CUDA"},
    "export.pytorch": {"zh": "PyTorch", "en": "PyTorch"},
    "export.ultralytics": {"zh": "Ultralytics", "en": "Ultralytics"},
    "export.tensorrt": {"zh": "TensorRT", "en": "TensorRT"},
    "export.not_available": {"zh": "不可用", "en": "Not Available"},
    "export.config": {"zh": "导出配置", "en": "Export Configuration"},
    "export.model_version": {"zh": "模型版本", "en": "Model Version"},
    "export.backend": {"zh": "推理后端", "en": "Backend"},
    "export.precision": {"zh": "精度", "en": "Precision"},
    "export.image_size": {"zh": "图像尺寸", "en": "Image Size"},
    "export.workspace_gb": {"zh": "工作空间(GB)", "en": "Workspace (GB)"},
    "export.calibration_dir": {"zh": "校准目录", "en": "Calibration Dir"},
    "export.browse": {"zh": "浏览", "en": "Browse"},
    "export.export_onnx": {"zh": "导出 ONNX", "en": "Export ONNX"},
    "export.export_tensorrt": {"zh": "导出 TensorRT FP16", "en": "Export TensorRT FP16"},
    "export.benchmark": {"zh": "基准测试", "en": "Benchmark"},
    "export.generate_package": {"zh": "生成部署包", "en": "Generate Package"},
    "export.artifacts": {"zh": "导出产物", "en": "Export Artifacts"},
    "export.col_id": {"zh": "导出ID", "en": "Export ID"},
    "export.col_backend": {"zh": "后端", "en": "Backend"},
    "export.col_precision": {"zh": "精度", "en": "Precision"},
    "export.col_status": {"zh": "状态", "en": "Status"},
    "export.col_path": {"zh": "路径", "en": "Path"},
    "export.col_error": {"zh": "错误", "en": "Error"},
    "export.col_device": {"zh": "设备", "en": "Device"},
    "export.status_created": {"zh": "已创建", "en": "Created"},
    "export.status_running": {"zh": "运行中", "en": "Running"},
    "export.status_completed": {"zh": "已完成", "en": "Completed"},
    "export.status_failed": {"zh": "失败", "en": "Failed"},
    "export.status_invalid": {"zh": "无效", "en": "Invalid"},
    "export.no_model": {"zh": "请先选择模型版本", "en": "Please select a model version"},
    "export.no_project": {"zh": "请先选择项目", "en": "Please select a project"},
    "export.tensorrt_unavailable": {"zh": "TensorRT 不可用，请安装 TensorRT", "en": "TensorRT unavailable, please install TensorRT"},
    "export.int8_needs_calibration": {"zh": "INT8 需要校准目录", "en": "INT8 requires calibration directory"},
    "export.refresh": {"zh": "刷新", "en": "Refresh"},
    "export.coming_soon": {"zh": "功能开发中，敬请期待", "en": "Coming soon"},
    "export.select_calibration_dir": {"zh": "选择校准目录", "en": "Select Calibration Directory"},
    "export.stop": {"zh": "■ 停止", "en": "■ Stop"},
    "export.browse_calibration": {"zh": "浏览...", "en": "Browse..."},

    # ── Phase D: Hybrid Retest ──────────────────────────────────────────

    # Navigation
    "nav.hybrid_retest": {"zh": "混合复检", "en": "Hybrid Retest"},

    # Hybrid retest page
    "hybrid_retest.config": {"zh": "复检配置", "en": "Retest Config"},
    "hybrid_retest.yolo_model": {"zh": "YOLO 模型:", "en": "YOLO Model:"},
    "hybrid_retest.anomaly_model": {"zh": "异常检测模型:", "en": "Anomaly Model:"},
    "hybrid_retest.no_anomaly_model": {"zh": "(无异常检测模型)", "en": "(No anomaly model)"},
    "hybrid_retest.image_dir": {"zh": "图片目录:", "en": "Image Directory:"},
    "hybrid_retest.image_dir_placeholder": {"zh": "选择待复检图片目录...", "en": "Select image directory for retest..."},
    "hybrid_retest.browse": {"zh": "选择目录", "en": "Browse"},
    "hybrid_retest.select_image_dir": {"zh": "选择待复检图片目录", "en": "Select Retest Image Directory"},
    "hybrid_retest.yolo_threshold": {"zh": "YOLO 置信度阈值:", "en": "YOLO Confidence Threshold:"},
    "hybrid_retest.anomaly_threshold": {"zh": "异常分数阈值:", "en": "Anomaly Score Threshold:"},
    "hybrid_retest.anomaly_high_threshold": {"zh": "异常高分阈值:", "en": "Anomaly High Threshold:"},
    "hybrid_retest.start": {"zh": "▶ 开始复检", "en": "▶ Start Retest"},
    "hybrid_retest.stop": {"zh": "■ 停止", "en": "■ Stop"},
    "hybrid_retest.refresh_models": {"zh": "刷新模型列表", "en": "Refresh Models"},
    "hybrid_retest.idle": {"zh": "就绪", "en": "Idle"},
    "hybrid_retest.stopping": {"zh": "正在停止...", "en": "Stopping..."},
    "hybrid_retest.complete": {"zh": "复检完成", "en": "Retest Complete"},
    "hybrid_retest.failed": {"zh": "复检失败", "en": "Retest Failed"},
    "hybrid_retest.summary": {"zh": "复检汇总", "en": "Retest Summary"},
    "hybrid_retest.total": {"zh": "总数", "en": "Total"},
    "hybrid_retest.ok": {"zh": "OK", "en": "OK"},
    "hybrid_retest.ng": {"zh": "NG", "en": "NG"},
    "hybrid_retest.suspect": {"zh": "Suspect", "en": "Suspect"},
    "hybrid_retest.unknown": {"zh": "Unknown", "en": "Unknown"},
    "hybrid_retest.needs_review": {"zh": "需复核", "en": "Needs Review"},
    "hybrid_retest.routed": {"zh": "已路由", "en": "Routed"},
    "hybrid_retest.col_image": {"zh": "图片", "en": "Image"},
    "hybrid_retest.col_decision": {"zh": "判定", "en": "Decision"},
    "hybrid_retest.col_reason": {"zh": "原因", "en": "Reason"},
    "hybrid_retest.col_yolo_count": {"zh": "YOLO检测数", "en": "YOLO Count"},
    "hybrid_retest.col_anomaly_score": {"zh": "异常分数", "en": "Anomaly Score"},
    "hybrid_retest.col_runtime": {"zh": "耗时(ms)", "en": "Runtime(ms)"},
    "hybrid_retest.col_review_id": {"zh": "复核ID", "en": "Review ID"},
    "hybrid_retest.log_placeholder": {"zh": "运行日志将显示在这里...", "en": "Run log will appear here..."},
    "hybrid_retest.select_model": {"zh": "-- 选择模型 --", "en": "-- Select Model --"},
    "hybrid_retest.no_yolo_model": {"zh": "请先选择 YOLO 模型", "en": "Please select a YOLO model first"},
    "hybrid_retest.invalid_image_dir": {"zh": "图片目录无效或不存在", "en": "Image directory is invalid or does not exist"},
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
