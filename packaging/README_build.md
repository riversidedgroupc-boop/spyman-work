# CX-vision 打包说明

## 环境要求

- Windows 10/11
- Python 3.12+
- PyInstaller >= 6.0

## 打包步骤

1. 安装 PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. 运行构建脚本:
   ```bash
   cd packaging
   build_windows.bat
   ```

3. 输出:
   ```
   dist/CX-vision/
     CX-vision.exe
     config/
     data/
     models/
     project_data/
     logs/
   ```

## 注意事项

- 不要把大型训练数据集打进 exe
- 模型文件放在 `models/` 目录
- 日志写入 `logs/` 目录
- 配置写入 `config/` 目录
- 客户数据在 `project_data/` 目录

## 交付清单

- [ ] CX-vision.exe 可正常启动
- [ ] 项目中心页面可用
- [ ] 采集/分类功能正常
- [ ] 训练/评估功能正常
- [ ] 生产运行页面正常
- [ ] 报告可生成
