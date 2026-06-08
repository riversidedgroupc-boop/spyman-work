@echo off
echo ============================================
echo  CX-vision V6 Windows Build Script
echo ============================================

set PROJECT_ROOT=%~dp0..
cd /d %PROJECT_ROOT%

echo.
echo [1/3] Cleaning previous build...
if exist dist\CX-vision rmdir /s /q dist\CX-vision
if exist build rmdir /s /q build

echo.
echo [2/3] Running PyInstaller...
.venv\Scripts\python.exe -m PyInstaller ^
    --name CX-vision ^
    --windowed ^
    --onedir ^
    --add-data "config;config" ^
    --add-data "data;data" ^
    --add-data "configs;configs" ^
    --add-data "models;models" ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import qt_material ^
    --hidden-import ultralytics ^
    --hidden-import cv2 ^
    --hidden-import numpy ^
    --hidden-import PIL ^
    --hidden-import torch ^
    --hidden-import openpyxl ^
    --hidden-import markdown ^
    --hidden-import core.camera_config ^
    --hidden-import core.dataset_version ^
    --hidden-import core.dataset_quality ^
    --hidden-import core.log_manager ^
    --hidden-import core.config_backup ^
    --hidden-import core.sampling_controller ^
    --hidden-import runtime.encoder_reader ^
    --hidden-import runtime.acquisition_pipeline ^
    --hidden-import runtime.inference_pipeline ^
    --hidden-import runtime.frame_buffer ^
    --hidden-import runtime.health_monitor ^
    --hidden-import camera_adapters ^
    --hidden-import camera_adapters.base ^
    --hidden-import camera_adapters.folder_watcher ^
    --hidden-import camera_adapters.hikvision_mvs ^
    --hidden-import camera_adapters.basler_pylon ^
    --hidden-import trainers ^
    --hidden-import trainers.base ^
    --hidden-import trainers.yolo_trainer ^
    --hidden-import trainers.patchcore_trainer ^
    --hidden-import trainers.hybrid_trainer ^
    --hidden-import model_runners.yolo_runner ^
    --hidden-import desktop_app.pages ^
    --hidden-import desktop_app.dialogs ^
    --hidden-import desktop_app.workers ^
    --hidden-import desktop_app.widgets ^
    --exclude-module tkinter ^
    --exclude-module jupyter ^
    --exclude-module streamlit ^
    --clean ^
    main.py

if %ERRORLEVEL% NEQ 0 (
    echo BUILD FAILED!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [3/3] Creating distribution directory...
mkdir dist\CX-vision 2>nul
mkdir dist\CX-vision\config 2>nul
mkdir dist\CX-vision\data 2>nul
mkdir dist\CX-vision\models 2>nul
mkdir dist\CX-vision\project_data 2>nul
mkdir dist\CX-vision\logs 2>nul

echo.
echo ============================================
echo  Build Complete!
echo  Output: dist\CX-vision\CX-vision.exe
echo ============================================
pause
