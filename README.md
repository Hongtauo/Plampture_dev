# Plampture - 掌纹采集系统

一个基于 PySide6 的双摄像头掌纹图像采集系统,支持红外(IR)和彩色(RGB)双路实时采集、ROI 提取和数据管理。

---

## 📋 项目简介

Plampture 是一个专业的掌纹采集系统,主要功能包括:

- 🎥 **双路摄像头实时采集**: 同时采集 IR 和 RGB 图像
- 🖐️ **手部检测与 ROI 提取**: 基于 MediaPipe 的实时手部关键点检测
- 📸 **快照管理**: 支持左右手分别采集,最多 20 张快照
- 💾 **数据持久化**: 元数据驱动的版本控制系统
- 📤 **数据导出**: 按用户和手部分类导出
- 🔍 **二维码识别**: 自动识别用户身份

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows 10/11 (推荐)
- 双摄像头设备 (IR + RGB)

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python setup.py
```

---

## 📦 项目结构

```
Plampture/
├── main.py                      # 采集窗口，由 setup.py 启动
├── camera_manager.py            # 摄像头管理模块
├── capture.py                   # 快照捕获模块
├── snapshot_io.py               # 快照 I/O 模块
├── ROI.py                       # ROI 提取模块
├── plam_ROI_worker.py           # MediaPipe 手部检测 Worker
├── scan_QRcode.py               # 二维码识别模块
├── export.py                    # 数据导出模块
├── setup.py                     # 程序入口，项目管理与启动
├── dynamic_layout.py            # UI 动态布局
├── Plampture.ui                 # Qt Designer UI 文件
├── Plampture_ui.py              # UI 代码 (自动生成)
├── requirements.txt             # 项目依赖
├── check_code.bat               # 代码规范检查脚本
├── .flake8                      # flake8 配置
├── .isort.cfg                   # isort 配置
├── pyproject.toml               # black 配置
├── docs/                        # 文档目录
│   ├── 代码规范检查报告.md
│   ├── 代码规范工具使用指南.md
│   └── 代码规范改进总结.md
├── icon/                        # 图标资源
├── model/                       # 模型文件
└── workspace/                   # 工作区 (项目数据)
```

---

## 🎯 主要功能

### 1. 双路摄像头采集

- 支持 IR 和 RGB 双路摄像头同步采集
- 可调节分辨率 (最高 1920x1080)
- 可调节帧率 (5-30 fps)
- 支持手动曝光控制

### 2. 手部检测与 ROI 提取

- 基于 MediaPipe Hands 的实时手部关键点检测
- 自动提取掌心 ROI 区域
- 支持旋转对齐和尺寸归一化

### 3. 快照管理

- 支持左右手分别采集 (各 10 张)
- 实时缩略图预览
- 支持删除和重新采集
- 自动保存到本地

### 4. 数据管理

- 元数据驱动的版本控制
- 支持用户历史数据加载
- 支持数据导出和备份
- 自动清理过期删除记录

---

## 🛠️ 开发指南

### 代码规范

项目遵循 PEP 8 代码规范,使用以下工具:

- **black**: 代码格式化
- **flake8**: 代码检查
- **isort**: 导入排序

### 运行代码检查

```bash
# Windows
check_code.bat

# 或手动运行
black .
isort .
flake8
```

### 详细文档

- [代码规范检查报告](docs/代码规范检查报告.md)
- [代码规范工具使用指南](docs/代码规范工具使用指南.md)
- [代码规范改进总结](docs/代码规范改进总结.md)

---

## 📖 使用说明

### 1. 创建并打开项目

在项目根目录运行 `python setup.py`，打开项目管理窗口：

1. 点击“新建”，输入项目名称；项目 ID 自动生成，数据保存在 `workspace/` 下。
2. 在列表中选择项目，点击“打开...”或双击项目。
3. 程序自动启动对应项目的采集窗口。

### 2. 配置摄像头

在菜单栏选择 `设置 > 摄像头设置`:

1. 选择 IR 摄像头
2. 选择 RGB 摄像头
3. 调整分辨率和帧率

### 3. 采集数据

1. **扫描二维码**: 将二维码对准 RGB 摄像头
2. **拍摄快照**: 点击 SNAP 按钮采集图像
3. **保存数据**: 点击 NEXT 按钮保存并切换用户

### 4. 导出数据

在项目管理窗口中导出：

1. 选中需要导出的项目，点击“导出”。
2. 选择导出目录。
3. 数据按图像类型、用户和手部分类导出。

---

## 🔧 配置说明

### 摄像头配置

```python
global_config = {
    "ir_camera_id": 0,           # IR 摄像头 ID
    "rgb_camera_id": 1,          # RGB 摄像头 ID
    "custom_resolution": (1920, 1080),  # 分辨率
    "rate": 30,                  # 帧率
    "max_snapshots": 20          # 最大快照数
}
```

### ROI 提取配置

ROI 提取使用关键点 (0, 5, 17):

- 0: WRIST (手腕)
- 5: INDEX_MCP (食指掌指关节)
- 17: PINKY_MCP (小指掌指关节)

---

## 🐛 常见问题

### Q1: 摄像头无法打开

**解决方案**:

1. 检查摄像头是否被其他程序占用
2. 尝试更换摄像头 ID
3. 重启程序

### Q2: 无法检测到手部

**解决方案**:

1. 确保光线充足
2. 调整手部位置和角度
3. 降低检测阈值 (在代码中修改)

### Q3: 二维码识别失败

**解决方案**:

1. 确保二维码清晰可见
2. 调整二维码与摄像头的距离
3. 检查二维码格式是否正确

---

## 📝 更新日志

### v1.0.0 (2025-11-26)

**新增**:

- ✅ 双路摄像头实时采集
- ✅ 手部检测与 ROI 提取
- ✅ 快照管理和数据持久化
- ✅ 二维码识别
- ✅ 数据导出功能

**改进**:

- ✅ 修复函数名拼写错误
- ✅ 添加类型提示
- ✅ 创建代码规范配置
- ✅ 完善项目文档

---

## 🤝 贡献指南

欢迎贡献代码! 请遵循以下步骤:

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

**注意**: 提交前请运行 `check_code.bat` 确保代码规范。

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 👥 作者

- **开发者**: Hongtauo
- **AI 助手**: Antigravity (Google Deepmind)

---

## 🙏 致谢

- [PySide6](https://www.qt.io/qt-for-python) - Qt for Python
- [OpenCV](https://opencv.org/) - 计算机视觉库
- [MediaPipe](https://mediapipe.dev/) - 手部检测
- [loguru](https://github.com/Delgan/loguru) - 日志系统

---

**最后更新**: 2025-11-26
