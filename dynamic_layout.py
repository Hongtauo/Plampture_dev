# -*- coding: utf-8 -*-
"""
UI 动态布局设置模块
实现自适应布局和比例调整
保留设计器中的所有原有控件，只调整布局方式
"""

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import os
import sys

# 获取应用程序根目录（兼容exe打包）
def get_app_dir():
    """获取应用程序根目录，兼容开发环境和打包后的exe环境"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def setup_dynamic_layout(ui):
    """
    设置动态布局，实现所有控件按比例自动调整
    
    布局比例：
    - horizontalLayout: capture_widget(8) : info_widget(2)
    - verticalLayout_3: video_widget(9) : thumbnail_preview_widget(1)
    - horizontalLayout_3: IR_cam(1) : RGB_cam(1)
    - info_layout: info_groupBox(7) : ctrl_groupBox(3)
    - infoConsel_verticalLayout: user_ico_label(1) : 其他信息标签(0) : fill_label(2)
    """
    
    # ========== 1. 顶层布局设置 ==========
    _setup_central_layout(ui)
    
    # ========== 2. 图像采集区域布局 (capture_widget) ==========
    _setup_capture_widget_layout(ui)
    
    # ========== 3. 缩略图区域布局 (thumbnail_preview_widget) ==========
    _setup_thumbnail_layout(ui)
    
    # ========== 4. 信息面板布局 (info_widget) ==========
    _setup_info_widget_layout(ui)
    
    # ========== 5. 控制按钮布局 (ctrl_groupBox) ==========
    _setup_control_buttons_layout(ui)
    
    return ui


def _setup_central_layout(ui):
    """设置中央布局，让 horizontalLayoutWidget 自适应填充整个窗口"""
    # 清除固定几何尺寸
    ui.horizontalLayoutWidget.setGeometry(0, 0, 0, 0)
    
    # 创建中央布局并添加 horizontalLayoutWidget
    central_layout = QVBoxLayout(ui.centralwidget)
    # 保留边距，避免覆盖菜单栏和状态栏
    central_layout.setContentsMargins(5, 5, 5, 5)
    central_layout.setSpacing(0)
    central_layout.addWidget(ui.horizontalLayoutWidget)
    
    # 设置 capture_widget 和 info_widget 的比例为 8:2
    ui.horizontalLayout.setStretch(0, 8)  # capture_widget
    ui.horizontalLayout.setStretch(1, 2)  # info_widget
    
    # 保存布局引用
    ui.central_layout = central_layout


def _setup_capture_widget_layout(ui):
    """设置图像采集区域布局，包含视频显示和缩略图预览"""
    # 清除 verticalLayoutWidget 的固定尺寸
    ui.verticalLayoutWidget.setGeometry(0, 0, 0, 0)
    
    # 为 capture_widget 创建布局
    image_layout = QVBoxLayout(ui.capture_widget)
    image_layout.setContentsMargins(0, 0, 0, 0)
    image_layout.setSpacing(0)
    image_layout.addWidget(ui.verticalLayoutWidget)
    
    # 设置 video_widget 和 thumbnail_preview_widget 的比例为 9:1
    ui.verticalLayout_3.setStretch(0, 8)  # video_widget
    ui.verticalLayout_3.setStretch(1, 2)  # thumbnail_preview_widget
    
    # 设置视频显示区域
    _setup_video_display_layout(ui)
    
    # 保存布局引用
    ui.image_layout = image_layout


def _setup_video_display_layout(ui):
    """设置视频显示区域，包含 IR 和 RGB 两路摄像头"""
    # 清除 horizontalLayoutWidget_2 的固定尺寸
    ui.horizontalLayoutWidget_2.setGeometry(0, 0, 0, 0)
    
    # 为 video_widget 创建布局
    video_layout = QVBoxLayout(ui.video_widget)
    video_layout.setContentsMargins(0, 0, 0, 0)
    video_layout.setSpacing(0)
    video_layout.addWidget(ui.horizontalLayoutWidget_2)
    
    # 设置 IR_cam 和 RGB_cam 的比例为 1:1
    ui.horizontalLayout_3.setStretch(0, 1)  # IR_cam
    ui.horizontalLayout_3.setStretch(1, 1)  # RGB_cam
    
    # 设置摄像头显示标签样式
    for cam_label in [ui.IR_cam, ui.RGB_cam]:
        cam_label.setStyleSheet("background-color: black; border: 1px solid #333;")
        cam_label.setScaledContents(False)
        cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_label.setMinimumSize(100, 100)
    
    # 保存布局引用
    ui.video_layout = video_layout


def _setup_thumbnail_layout(ui):
    """设置缩略图预览区域布局"""
    # 清除 thumbnail_listWidget 的固定尺寸
    ui.thumbnail_listWidget.setGeometry(0, 0, 0, 0)
    
    # 为 thumbnail_preview_widget 创建布局
    thumbnail_layout = QVBoxLayout(ui.thumbnail_preview_widget)
    thumbnail_layout.setContentsMargins(5, 5, 5, 5)
    thumbnail_layout.setSpacing(0)
    thumbnail_layout.addWidget(ui.thumbnail_listWidget)
    
    # 保存布局引用
    ui.thumbnail_layout = thumbnail_layout


def _setup_info_widget_layout(ui):
    """设置信息面板布局，包含信息显示和控制按钮两个 GroupBox"""
    # 清除 GroupBox 的固定几何尺寸
    ui.info_groupBox.setGeometry(0, 0, 0, 0)
    ui.ctrl_groupBox.setGeometry(0, 0, 0, 0)
    
    # 为 info_widget 创建布局
    # 确保 info_groupBox 和 ctrl_groupBox 的父容器为 info_widget，以免被意外放到其它地方
    try:
        if ui.info_groupBox.parent() is not ui.info_widget:
            ui.info_groupBox.setParent(ui.info_widget)
    except Exception:
        pass
    try:
        if ui.ctrl_groupBox.parent() is not ui.info_widget:
            ui.ctrl_groupBox.setParent(ui.info_widget)
    except Exception:
        pass

    info_layout = QVBoxLayout(ui.info_widget)
    info_layout.setContentsMargins(10, 10, 10, 10)
    info_layout.setSpacing(6)

    # 保证 info_widget 有合理的最小宽度，以便 ap_widget 能获得可见空间
    try:
        ui.info_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        # 给 info 面板一个合理的最小宽度（可根据需要调整）
        ui.info_widget.setMinimumWidth(300)
    except Exception:
        pass

    # 设置 info_groupBox 和 ctrl_groupBox 的布局属性：info_groupBox 可伸展，ctrl_groupBox 固定高度
    try:
        ui.info_groupBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    except Exception:
        pass
    try:
        # 让 ctrl_groupBox 也可以在竖直方向伸展，由 info_layout 的 stretch 决定最终高度
        ui.ctrl_groupBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    except Exception:
        pass

    # 我们需要按顺序在 info_widget 中放置三块：
    # info_groupBox（信息面板）, ap_widget（或 per-camera 容器）, ctrl_groupBox（控制按钮）
    # 目标高度比为 5 : 2.5 : 2.5 -> 乘以2后为 10 : 5 : 5
    # 先把 info_groupBox 的内部布局设置好（不处理 ap_widget），然后把 ap_widget 插入为 info_widget 的直接子项
    _setup_info_groupbox_layout(ui)

    # 组装 info_layout: info_groupBox, ap_widget_or_container, ctrl_groupBox
    # 目标高度比例为 4 : 3 : 3
    # 1) info_groupBox
    info_layout.addWidget(ui.info_groupBox, 4)

    # 2) ap_widget 或 per-camera 容器（如果存在）
    # 目标：若存在 IR/RGB 各自的 ap_groupBox，把它们并排放在 info_widget 中；否则回退到单一 ap_widget 或占位
    try:
        # 查找已存在的摄像头 GroupBox/容器（使用精确对象名：IR_ / RGB_）
        cam_containers = {}
        for cam in ('IR', 'RGB'):
            found = None
            for cname in (f"{cam}_ap_groupBox", f"{cam}_ap_widget"):
                if hasattr(ui, cname):
                    found = getattr(ui, cname)
                    break
            cam_containers[cam] = found

        if any(cam_containers.values()):
            # 创建一个水平区域容器承载两个摄像头的 ap groupboxes
            ap_area = QWidget(ui.info_widget)
            ap_area.setObjectName('ap_area')
            ap_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            ap_h = QHBoxLayout(ap_area)
            ap_h.setContentsMargins(6, 6, 6, 6)
            ap_h.setSpacing(8)

            for cam in ('IR', 'RGB'):
                container = cam_containers.get(cam)
                if container is None:
                    # create empty container to keep alignment
                    container = QWidget(ap_area)
                    container.setObjectName(f"{cam.lower()}_ap_widget")
                else:
                    try:
                        if container.parent() is not ap_area:
                            container.setParent(ap_area)
                    except Exception:
                        pass

                # make each camera container expand vertically to fill ap_area
                container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
                try:
                    container.setMinimumHeight(0)
                except Exception:
                    pass
                ap_h.addWidget(container, 1)

                # 把 ap_area 插入 info_layout
            info_layout.addWidget(ap_area, 3)
        elif hasattr(ui, 'ap_widget'):
            try:
                if ui.ap_widget.parent() is not ui.info_widget:
                    ui.ap_widget.setParent(ui.info_widget)
            except Exception:
                pass
            # allow ap_widget to expand vertically to fill its allotted stretch
            try:
                ui.ap_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            except Exception:
                pass
            info_layout.addWidget(ui.ap_widget, 3)
        else:
            # 占位以保持比例
            placeholder = QWidget(ui.info_widget)
            placeholder.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            placeholder.setFixedHeight(0)
            info_layout.addWidget(placeholder, 3)
    except Exception:
        # 插入占位以保证后续 ctrl_groupBox 不会挤压到顶部
        placeholder = QWidget(ui.info_widget)
        placeholder.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        placeholder.setFixedHeight(0)
        info_layout.addWidget(placeholder, 3)

    # 3) ctrl_groupBox
    info_layout.addWidget(ui.ctrl_groupBox, 3)

    # 保存布局引用
    ui.info_layout = info_layout

    # 为 IR/RGB 各自的 ap groupbox 做列对齐排版（如果存在）
    try:
        _setup_per_cam_ap_layout(ui)
    except Exception:
        pass


def _setup_info_groupbox_layout(ui):
    """设置信息 GroupBox 内部布局，包含用户图标和信息标签"""
    # 清除 verticalLayoutWidget_2 的固定几何尺寸
    ui.verticalLayoutWidget_2.setGeometry(0, 0, 0, 0)
    
    # 为 info_groupBox 创建布局
    info_groupBox_layout = QVBoxLayout(ui.info_groupBox)
    info_groupBox_layout.setContentsMargins(10, 30, 10, 10)  # 上边距为标题留空间
    info_groupBox_layout.setSpacing(0)
    info_groupBox_layout.addWidget(ui.verticalLayoutWidget_2)
    
    # 设置用户图标标签
    _setup_user_icon_label(ui)
    # 设置 infoConsel_verticalLayout 中各控件的拉伸因子（不再处理 ap_widget）
    try:
        layout = ui.infoConsel_verticalLayout
        # 期望的子控件序列通常为：user_ico_label, name_label, id_label, capture_timestamp_label, fill_label
        # 给 user_ico_label 可伸展空间，其他信息为固定高度，fill_label 承担剩余空间
        count = layout.count()
        for i in range(count):
            item = layout.itemAt(i)
            w = item.widget() if item is not None else None
            if w is None:
                layout.setStretch(i, 0)
                continue
            if hasattr(ui, 'user_ico_label') and w is ui.user_ico_label:
                layout.setStretch(i, 1)
                continue
            if (hasattr(ui, 'name_label') and w is ui.name_label) or \
               (hasattr(ui, 'id_label') and w is ui.id_label) or \
               (hasattr(ui, 'capture_timestamp_label') and w is ui.capture_timestamp_label):
                layout.setStretch(i, 0)
                continue
            if hasattr(ui, 'fill_label') and w is ui.fill_label:
                layout.setStretch(i, 2)
                continue
            layout.setStretch(i, 0)
    except Exception:
        pass
    
    # 设置信息标签的尺寸策略
    ui.name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    ui.id_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    ui.capture_timestamp_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    
    # 设置填充标签
    ui.fill_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    ui.fill_label.setText("")  # 清空占位符文本

    # 如果 UI 中包含自动曝光/属性控件(ap_widget)，为其创建内部布局并适配滑块
    # 同时兼容两种布局：
    # 1) 单一 ap_widget（滑块名: bright_ctrl_horizontalSlider, contrast_ctrl_horizontalSlider, exposure_ctrl_horizontalSlider）
    # 2) 两个分组的控件（以前缀 ir_/rgb_ 命名滑块，例如 ir_bright_ctrl_horizontalSlider, rgb_exposure_ctrl_horizontalSlider）
    def _wire_slider(container, slider_attr_name, label_text):
        """把一个滑块放入 container 布局并附带数值显示与居中初始化。

        在匹配滑块时尝试多种变体（保留原始名称，同时尝试替换小写前缀为大写 `IR_`/`RGB_`），
        保证能匹配设计器中可能的命名风格。
        """
        row = QHBoxLayout()
        lbl = QLabel(label_text, container)
        lbl.setFixedWidth(60)
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        row.addWidget(lbl)

        # 构造候选名称变体
        variants = [slider_attr_name]
        # 如果包含小写前缀 ir_ 或 rgb_，同时尝试大写前缀变体
        if slider_attr_name.startswith('ir_'):
            variants.append(slider_attr_name.replace('ir_', 'IR_'))
            variants.append(slider_attr_name.replace('ir_', 'Ir_'))
        if slider_attr_name.startswith('rgb_'):
            variants.append(slider_attr_name.replace('rgb_', 'RGB_'))
            variants.append(slider_attr_name.replace('rgb_', 'Rgb_'))
        # 也尝试把前缀去掉的形式，以防使用无前缀命名
        if '_' in slider_attr_name:
            variants.append(slider_attr_name.split('_', 1)[1])

        # 查找第一个存在的 slider 对象
        slider = None
        try:
            slider = _find_slider_by_variants(ui, variants)
        except Exception:
            slider = None

        # Fallback: getattr directly
        if slider is None:
            for name in variants:
                if hasattr(ui, name):
                    slider = getattr(ui, name)
                    break

        if slider is None:
            return row

        slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # value label 显示当前数值（百分比格式），稍后设置初始居中会触发 valueChanged 更新
        try:
            value_label = QLabel(f"{slider.value()}%", container)
        except Exception:
            value_label = QLabel("", container)
        value_label.setFixedWidth(44)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(slider)
        row.addWidget(value_label)

        try:
            # 显示百分比值,更直观
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(f"{v}%"))
        except Exception:
            pass

        try:
            lo = slider.minimum()
            hi = slider.maximum()
            slider.setValue((lo + hi) // 2)
        except Exception:
            pass

        return row

    # 首先检查是否存在按摄像头分组的滑块（精确匹配大写 `IR_` 和 `RGB_` 对象名）
    per_cam_found = False
    for cam in ('IR', 'RGB'):
        if any(hasattr(ui, f"{cam}_{p}_ctrl_horizontalSlider") for p in ('bright', 'contrast', 'exposure')):
            per_cam_found = True
            break

    if per_cam_found:
        # 为每一路摄像头创建或使用已有的 GroupBox/容器（先尝试查找 groupbox，否则使用 info_groupBox 的 ap_widget 区域）
        # 尝试使用小写前缀为基础的循环，但在查找容器和滑块时同时检查大小写变体
        for prefix, title in (('ir_', 'IR'), ('rgb_', 'RGB')):
            # 找到合适的 container：优先查找以 prefix 开头的 groupbox 名称，否则创建一个 QWidget 作为容器
            # 同时尝试大小写变体，例如 ir_ / IR_
            container_name_candidates = [f"{prefix}ap_groupBox", f"{prefix}ap_widget", f"{prefix}groupBox",
                                         f"{prefix.upper()}ap_groupBox", f"{prefix.upper()}ap_widget", f"{prefix.upper()}groupBox"]
            container = None
            for cname in container_name_candidates:
                if hasattr(ui, cname):
                    container = getattr(ui, cname)
                    break
            if container is None:
                # 如果没有显式的容器，创建一个内联 QWidget 并添加到 infoConsel_verticalLayout
                container = QWidget(ui.verticalLayoutWidget_2)
                container.setObjectName(f"{prefix}ap_widget")
                ui.infoConsel_verticalLayout.addWidget(container)

            try:
                container.setGeometry(0, 0, 0, 0)
            except Exception:
                pass

            # 不在此处强制改变父容器（父容器由上层布局决定），并允许容器竖直扩展以配合外部布局
            container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

            # Do not create inner layouts here; internal per-camera layout will be handled
            # by _setup_per_cam_ap_layout which creates a QGridLayout inside the container.
            # Ensure container has reasonable size policy so grid can expand.
            try:
                container.setGeometry(0, 0, 0, 0)
            except Exception:
                pass
            container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    elif hasattr(ui, 'ap_widget'):
        try:
            # 清除 ap_widget 固定几何
            ui.ap_widget.setGeometry(0, 0, 0, 0)
        except Exception:
            pass

        # 允许 ap_widget 在竖直方向扩展以填满 info_widget 的 ap 区域
        ui.ap_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        ap_layout = QVBoxLayout(ui.ap_widget)
        ap_layout.setContentsMargins(6, 6, 6, 6)
        ap_layout.setSpacing(6)

        # 使用原有命名规则创建三行
        ap_layout.addLayout(_wire_slider(ui.ap_widget, 'bright_ctrl_horizontalSlider', '亮度'))
        ap_layout.addLayout(_wire_slider(ui.ap_widget, 'contrast_ctrl_horizontalSlider', '对比度'))
        ap_layout.addLayout(_wire_slider(ui.ap_widget, 'exposure_ctrl_horizontalSlider', '曝光'))
    else:
        # 没有任何 ap 控件，什么也不做
        pass


def _setup_user_icon_label(ui):
    """设置用户图标标签，加载并显示卡片图片"""
    old_user_ico_label = ui.user_ico_label
    
    # 创建新的标签
    new_user_ico_label = QLabel(ui.verticalLayoutWidget_2)
    new_user_ico_label.setObjectName("user_ico_label")
    new_user_ico_label.setStyleSheet("background-color: transparent;")
    new_user_ico_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    new_user_ico_label.setScaledContents(False)
    new_user_ico_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    
    # 加载卡片图片（使用兼容路径）
    icon_path = os.path.join(get_app_dir(), "icon", "card.png")
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        new_user_ico_label._original_pixmap = pixmap
        new_user_ico_label.setPixmap(pixmap.scaled(
            new_user_ico_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
    else:
        new_user_ico_label.setText("card.png not found")
        new_user_ico_label._original_pixmap = None
    
    # 添加 resizeEvent 处理图片自适应缩放
    def _label_resizeEvent(event):
        QLabel.resizeEvent(new_user_ico_label, event)
        if hasattr(new_user_ico_label, '_original_pixmap') and new_user_ico_label._original_pixmap:
            scaled = new_user_ico_label._original_pixmap.scaled(
                new_user_ico_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            new_user_ico_label.setPixmap(scaled)
    
    new_user_ico_label.resizeEvent = _label_resizeEvent
    
    # 在布局中替换原有标签
    layout_index = ui.infoConsel_verticalLayout.indexOf(old_user_ico_label)
    ui.infoConsel_verticalLayout.removeWidget(old_user_ico_label)
    old_user_ico_label.deleteLater()
    ui.infoConsel_verticalLayout.insertWidget(layout_index, new_user_ico_label)
    
    # 更新 UI 引用
    ui.user_ico_label = new_user_ico_label


def _find_slider_by_variants(ui, variants):
    """Return first existing slider attribute from variants list, or None."""
    for name in variants:
        if hasattr(ui, name):
            return getattr(ui, name)
    return None


def _setup_per_cam_ap_layout(ui):
    """为 IR / RGB 的 ap_groupBox 或 ap_widget 使用 QGridLayout 进行列对齐。

    每个 groupbox 的每一行为: Label | Slider | Value
    保证两路的列对齐通过统一 label/value 宽度与 slider 列的伸缩比。
    """
    label_width = 60
    value_width = 44
    props = [('bright', '亮度'), ('contrast', '对比度'), ('exposure', '曝光')]

    for cam in ('IR', 'RGB'):
        # possible container names
        # 使用精确对象名（IR_ / RGB_），不要做模糊小写匹配
        candidates = [f"{cam}_ap_groupBox", f"{cam}_ap_widget"]
        container = None
        for cname in candidates:
            if hasattr(ui, cname):
                container = getattr(ui, cname)
                break
        if container is None:
            # nothing to do for this camera
            continue

        # Do not forcibly change parent here; parent should be set by caller to ensure correct placement

        # Create grid layout and assign columns: 0=label,1=slider,2=value
        grid = QGridLayout(container)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        row = 0
        for prop_key, prop_label in props:
            # 使用精确对象名：例如 IR_bright_ctrl_horizontalSlider / RGB_bright_ctrl_horizontalSlider
            slider_name = f"{cam}_{prop_key}_ctrl_horizontalSlider"
            slider = getattr(ui, slider_name, None)
            if slider is None:
                # leave an empty row to preserve alignment
                label = QLabel(prop_label, container)
                label.setFixedWidth(label_width)
                grid.addWidget(label, row, 0)
                grid.addWidget(QWidget(container), row, 1)
                val = QLabel("", container)
                val.setFixedWidth(value_width)
                grid.addWidget(val, row, 2)
                row += 1
                continue

            # ensure slider is parented into container
            try:
                if slider.parent() is not container:
                    slider.setParent(container)
            except Exception:
                pass

            label = QLabel(prop_label, container)
            label.setFixedWidth(label_width)
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(label, row, 0)

            # slider column
            slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(slider, row, 1)

            # set initial value to middle so numeric label shows center
            try:
                slo = slider.minimum()
                shi = slider.maximum()
                slider.setValue((slo + shi) // 2)
            except Exception:
                pass

            # value label (百分比格式)
            try:
                val_label = QLabel(f"{slider.value()}%", container)
            except Exception:
                val_label = QLabel("", container)
            val_label.setFixedWidth(value_width)
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(val_label, row, 2)

            try:
                # 显示百分比值,更直观
                slider.valueChanged.connect(lambda v, lbl=val_label: lbl.setText(f"{v}%"))
            except Exception:
                pass

            row += 1

        # set column stretch so sliders expand and labels keep fixed
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)

        # Save reference for debugging if needed
        container._plampture_ap_grid = grid


def _setup_control_buttons_layout(ui):
    """设置控制按钮布局，包含 QR、SNAP、NEXT 三个按钮"""
    # 清除按钮的固定几何尺寸
    ui.QR_Button.setGeometry(0, 0, 0, 0)
    ui.SNAP_Button.setGeometry(0, 0, 0, 0)
    ui.NEXT_Button.setGeometry(0, 0, 0, 0)
    
    # 设置按钮的尺寸策略，允许扩展
    for button in [ui.QR_Button, ui.SNAP_Button, ui.NEXT_Button]:
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    
    # 为 ctrl_groupBox 创建垂直布局
    ctrl_layout = QVBoxLayout(ui.ctrl_groupBox)
    ctrl_layout.setContentsMargins(10, 10, 10, 10)
    ctrl_layout.setSpacing(5)
    
    # 第一行：QR_Button 和 SNAP_Button 水平排列
    first_row_layout = QHBoxLayout()
    first_row_layout.setSpacing(5)
    first_row_layout.addWidget(ui.QR_Button, 1)
    first_row_layout.addWidget(ui.SNAP_Button, 1)
    
    # 第二行：NEXT_Button 单独一行
    second_row_layout = QHBoxLayout()
    second_row_layout.addWidget(ui.NEXT_Button, 1)
    
    # 将两行添加到垂直布局，高度相等
    ctrl_layout.addLayout(first_row_layout, 1)
    ctrl_layout.addLayout(second_row_layout, 1)

