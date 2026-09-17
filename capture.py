# -*- coding: utf-8 -*-
"""
快照捕获模块
管理IR和RGB图像的捕获、内存存储和缩略图显示
"""

import os
import sys
import cv2
import numpy as np
import threading
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QLabel, QVBoxLayout, QWidget, QDialog, QHBoxLayout, QScrollArea, QMenu
from PySide6.QtGui import QImage, QPixmap, QAction, QIcon
from PySide6.QtCore import Qt, QSize, QObject, Signal
from loguru import logger

# 导入快照I/O模块
import snapshot_io

# 获取应用程序根目录（兼容exe打包）
def get_app_dir():
    """获取应用程序根目录，兼容开发环境和打包后的exe环境"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

# 全局图标路径
INFO_ICON_PATH = os.path.join(get_app_dir(), "icon", "info.ico")

def get_dialog_icon():
    """获取对话框图标"""
    if os.path.exists(INFO_ICON_PATH):
        return QIcon(INFO_ICON_PATH)
    return QIcon()


@dataclass
class Snapshot:
    """快照数据类"""
    timestamp: str  # 时间戳 YYYYMMDD_HHMMSS
    ir_frame: np.ndarray  # IR图像帧
    rgb_frame: np.ndarray  # RGB图像帧
    snapshot_id: Optional[str] = None  # 快照唯一ID（UUID）
    user_id: Optional[str] = None  # 用户ID（可选）
    is_saved: bool = False  # 是否已保存到磁盘（用于区分历史加载的快照）
    ir_file_path: Optional[str] = None  # IR图像的磁盘文件路径（已保存的快照）
    rgb_file_path: Optional[str] = None  # RGB图像的磁盘文件路径（已保存的快照）
    hand: Optional[str] = None  # 手部标识: 'left' 或 'right' 或 None
    detection_result: Optional[dict] = None  # MediaPipe 检测结果（包含 ROI 信息）
    
    def get_datetime(self):
        """返回时间戳的datetime对象"""
        # 支持带毫秒的时间戳格式 YYYYMMDD_HHMMSS_fff
        if len(self.timestamp) > 15:  # 包含毫秒
            return datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S_%f")
        else:  # 旧格式，不含毫秒
            return datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S")
    
    def __repr__(self):
        return f"Snapshot(id={self.snapshot_id}, timestamp={self.timestamp}, user_id={self.user_id})"


class SnapshotManager(QObject):
    """快照管理器"""
    
    # 定义信号：当快照数量变化时发出
    snapshot_count_changed = Signal(int, int)  # (current_count, max_count)
    
    def __init__(self, max_snapshots: int = 10, thumbnail_list_widget: Optional[QListWidget] = None, project_dir: Optional[str] = None):
        """
        初始化快照管理器
        
        Args:
            max_snapshots: 最大快照数量
            thumbnail_list_widget: 用于显示缩略图的QListWidget
            project_dir: 项目目录路径
        """
        super().__init__()  # 初始化 QObject
        self.max_snapshots = max_snapshots
        self.thumbnail_list_widget = thumbnail_list_widget
        self.snapshots: List[Snapshot] = []  # 快照存储列表
        self.project_dir = project_dir  # 项目目录
        self.current_user_id = None  # 当前用户ID
        self.user_snapshot_counter = {}  # 用户快照计数器 {user_id: next_index}
        self.snapshots_to_delete = []  # 需要从磁盘删除的快照文件路径列表
        # 保护快照列表的锁，防止并发访问（例如UI线程与保存线程）
        self._lock = threading.Lock()
        
        # 配置缩略图列表
        if self.thumbnail_list_widget:
            self.setup_thumbnail_list()
        
        # 加载快照日志
        if self.project_dir:
            self.user_snapshot_counter = snapshot_io.load_snapshot_logs(self.project_dir)
        
        logger.info(f"快照管理器初始化完成，最大快照数量: {max_snapshots}")

    @property
    def max_snapshots(self) -> int:
        """返回最大快照数量（始终为正整数且为偶数）"""
        return getattr(self, "_max_snapshots", 0)

    @max_snapshots.setter
    def max_snapshots(self, value: int):
        """设置最大快照数量，必须为正整数且为2的倍数（偶数）

        Raises:
            ValueError: 当 value 不是正整数或不是2的倍数时抛出
        """
        try:
            v = int(value)
        except Exception:
            raise ValueError("max_snapshots 必须为整数")
        if v <= 0:
            raise ValueError("max_snapshots 必须为正整数")
        if v % 2 != 0:
            raise ValueError("max_snapshots 必须为2的倍数（偶数）")
        self._max_snapshots = v
        logger.debug(f"max_snapshots 设置为 {v}")
    
    def setup_thumbnail_list(self):
        """配置缩略图列表控件"""
        # 使用列表模式，配置为横向显示
        self.thumbnail_list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.thumbnail_list_widget.setFlow(QListWidget.Flow.LeftToRight)  # 横向流动
        self.thumbnail_list_widget.setWrapping(False)  # 不换行，横向滚动
        self.thumbnail_list_widget.setMovement(QListWidget.Movement.Static)  # 禁止拖动
        
        # 设置间距
        self.thumbnail_list_widget.setSpacing(10)
        self.thumbnail_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        
        # 关键：设置统一的网格大小，避免错位
        self.thumbnail_list_widget.setUniformItemSizes(True)
        
        # 设置样式 - 移除边框和背景
        self.thumbnail_list_widget.setStyleSheet("""
            QListWidget::item {
                background-color: transparent;
                border: none;
            }
            QListWidget::item:selected {
                background-color: transparent;
                border: none;
            }
            QListWidget::item:hover {
                background-color: transparent;
            }
        """)
        
        # 连接双击事件
        self.thumbnail_list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # 启用右键菜单
        self.thumbnail_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbnail_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        # 连接键盘按键事件（Delete键删除）
        self.thumbnail_list_widget.keyPressEvent = self.handle_key_press
        
        logger.debug("缩略图列表控件已配置")
    
    def capture_snapshot(self, ir_frame: Optional[np.ndarray], rgb_frame: Optional[np.ndarray], 
                        user_id: Optional[str] = None, hand: Optional[str] = None, 
                        detection_result: Optional[dict] = None) -> Optional[Snapshot]:
        """
        捕获快照
        
        Args:
            ir_frame: IR图像帧
            rgb_frame: RGB图像帧
            user_id: 用户ID（可选）
            hand: 手部标识（可选）
            detection_result: MediaPipe 检测结果（可选）
        
        Returns:
            Snapshot对象，如果捕获失败返回None
        """
        # 验证至少有一个图像帧
        if ir_frame is None and rgb_frame is None:
            logger.error("捕获失败：IR和RGB图像帧都为空")
            return None
        
        # 生成时间戳（包含毫秒，避免重复）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]  # YYYYMMDD_HHMMSS_fff (精确到毫秒)
        
        # 生成唯一的快照ID（使用UUID4）
        import uuid
        snapshot_id = str(uuid.uuid4())
        
        # 如果已达到最大快照数量，则不再覆盖，直接忽略新快照
        with self._lock:
            if len(self.snapshots) >= self.max_snapshots:
                logger.warning(f"达到最大快照数量 ({self.max_snapshots})，忽略新快照")
                return None

        # 复制图像帧（避免原始数据被修改）
        ir_copy = ir_frame.copy() if ir_frame is not None else None
        rgb_copy = rgb_frame.copy() if rgb_frame is not None else None
        
        # 创建快照对象
        snapshot = Snapshot(
            timestamp=timestamp,
            ir_frame=ir_copy,
            rgb_frame=rgb_copy,
            snapshot_id=snapshot_id,
            user_id=user_id,
            hand=hand,
            detection_result=detection_result
        )
        
        # 添加到列表（受锁保护以保证线程安全）
        with self._lock:
            self.snapshots.append(snapshot)
            logger.info(f"快照已捕获: {snapshot}")
        
        # 更新缩略图显示（复制快照列表以避免并发修改）
        if self.thumbnail_list_widget:
            with self._lock:
                snapshots_copy = list(self.snapshots)
            # 使用副本更新UI
            # 这里把副本传入 update_thumbnail_display 通过临时替换属性来避免大量改动
            orig_list = self.thumbnail_list_widget
            # 为简单起见，直接调用 update_thumbnail_display()（它会读取 self.snapshots），
            # 但我们已确保不会在此刻并发修改 self.snapshots（capture 时锁已释放）
            self.update_thumbnail_display()

        # 发出信号通知快照数量变化
        with self._lock:
            current_len = len(self.snapshots)
        self.snapshot_count_changed.emit(current_len, self.max_snapshots)
        
        return snapshot
    
    def update_thumbnail_display(self):
        """更新缩略图显示"""
        if not self.thumbnail_list_widget:
            return
        # 复制快照列表以避免在UI线程迭代时被修改
        with self._lock:
            snapshots_copy = list(self.snapshots)

        # 清理现有 item 对应的 widget，确保释放 QPixmap 等 Qt 资源
        try:
            existing_count = self.thumbnail_list_widget.count()
            for i in range(existing_count - 1, -1, -1):
                try:
                    itm = self.thumbnail_list_widget.item(i)
                    if itm is None:
                        continue
                    w = self.thumbnail_list_widget.itemWidget(itm)
                    if w is not None:
                        self.thumbnail_list_widget.removeItemWidget(itm)
                        w.deleteLater()
                except Exception:
                    continue
        except Exception:
            pass

        # 清空现有列表项
        self.thumbnail_list_widget.clear()

        # 为每个快照创建缩略图
        for idx, snapshot in enumerate(snapshots_copy):
            thumbnail_widget = self.create_thumbnail_widget(snapshot, idx)
            
            # 创建列表项
            item = QListWidgetItem(self.thumbnail_list_widget)
            
            # 先添加 item
            self.thumbnail_list_widget.addItem(item)
            # 绑定 widget 到 item
            self.thumbnail_list_widget.setItemWidget(item, thumbnail_widget)
            
            # 强制widget处理布局
            thumbnail_widget.adjustSize()
            
            # 设置item的尺寸提示，确保与widget完全一致
            item.setSizeHint(thumbnail_widget.size())
            
            # 存储快照ID到 item 的数据中（更稳健，避免索引在并发修改时失配）
            item.setData(Qt.UserRole, snapshot.snapshot_id)
        
        logger.debug(f"缩略图显示已更新，共 {len(snapshots_copy)} 个快照")
    
    def create_thumbnail_widget(self, snapshot: Snapshot, index: int) -> QWidget:
        """
        创建缩略图widget
        
        Args:
            snapshot: 快照对象
            index: 快照索引
        
        Returns:
            包含IR和RGB缩略图的QWidget
        """
        # 获取列表控件的可用高度
        list_height = self.thumbnail_list_widget.height()
        # 减去边距、间距和滚动条高度，计算实际可用高度
        available_height = list_height - 40  # 预留40像素用于边距和滚动条
        
        # 为标题、标签和用户信息预留空间
        title_height = 25
        label_height = 20  # IR和RGB标签各约10px
        user_info_height = 20 if snapshot.user_id else 0
        reserved_height = title_height + label_height * 2 + user_info_height + 30  # 30px额外边距
        
        # 计算每个图片可用的高度（两张图片）
        image_total_height = available_height - reserved_height
        single_image_height = max(50, image_total_height // 2)  # 每张图片的高度，最小50px
        
        # 根据图片高度计算宽度，但要确保至少能显示完整的时间戳和用户ID
        # 时间戳格式：YYYYMMDD_HHMMSS (15字符)
        # 考虑字体大小10px，每个字符约6-7px，15个字符约105px
        # 加上"#1 - "前缀，总共需要约150px
        min_width_for_text = 150  # 确保文字能完整显示
        calculated_width = int(single_image_height * 1.33)  # 使用4:3比例
        image_width = max(min_width_for_text, calculated_width)  # 取两者中的较大值
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 创建标题标签
        title_label = QLabel(f"#{index + 1} - {snapshot.timestamp}")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        layout.addWidget(title_label)
        
        # 创建IR缩略图
        if snapshot.ir_frame is not None:
            ir_label = QLabel("IR")
            ir_label.setAlignment(Qt.AlignCenter)
            ir_label.setStyleSheet("font-size: 12px; color: #666;")
            layout.addWidget(ir_label)
            
            # 直接从 detection_result 裁剪 ROI 或从文件加载
            ir_thumbnail = self.create_thumbnail_from_snapshot(snapshot, 'ir', size=(image_width, single_image_height))
            ir_image_label = QLabel()
            ir_image_label.setPixmap(ir_thumbnail)
            ir_image_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(ir_image_label)
        
        # 创建RGB缩略图
        if snapshot.rgb_frame is not None:
            rgb_label = QLabel("RGB")
            rgb_label.setAlignment(Qt.AlignCenter)
            rgb_label.setStyleSheet("font-size: 12px; color: #666;")
            layout.addWidget(rgb_label)
            
            # 优先使用已保存的 ROI 图像文件（如果存在）
            rgb_thumbnail = self.create_thumbnail_from_snapshot(snapshot, 'rgb', size=(image_width, single_image_height))
            rgb_image_label = QLabel()
            rgb_image_label.setPixmap(rgb_thumbnail)
            rgb_image_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(rgb_image_label)
        
        # 添加用户ID
        if snapshot.user_id:
            user_label = QLabel(f"ID: {snapshot.user_id}")
            user_label.setAlignment(Qt.AlignCenter)
            user_label.setStyleSheet("font-size: 12px; color: #999;")
            layout.addWidget(user_label)

        # 添加手部信息
        if snapshot.hand:
            hand_text = "左手" if snapshot.hand == 'left' else ("右手" if snapshot.hand == 'right' else snapshot.hand)
            hand_label = QLabel(f"手部: {hand_text}")
            hand_label.setAlignment(Qt.AlignCenter)
            hand_label.setStyleSheet("font-size: 12px; color: #999;")
            layout.addWidget(hand_label)
        
        widget.setLayout(layout)
        
        # 设置widget的固定宽度，让高度根据内容自动计算
        widget.setFixedWidth(image_width + 20)
        
        return widget

    def _find_index_by_snapshot_id(self, snapshot_id: str) -> int | None:
        """
        根据 snapshot_id 查找当前快照列表中的索引，找不到返回 None。
        """
        with self._lock:
            for i, s in enumerate(self.snapshots):
                if s.snapshot_id == snapshot_id:
                    return i
        return None
    
    def create_thumbnail_from_snapshot(self, snapshot: Snapshot, img_type: str, size: Tuple[int, int] = (180, 100)) -> QPixmap:
        """
        从快照创建缩略图，优先顺序：
        1. 从磁盘文件加载（已保存的 ROI）
        2. 从 detection_result 实时裁剪 ROI
        3. 使用内存中的原始帧
        
        Args:
            snapshot: 快照对象
            img_type: 'ir' 或 'rgb'
            size: 缩略图尺寸 (width, height)
        
        Returns:
            QPixmap 缩略图
        """
        file_path = snapshot.ir_file_path if img_type == 'ir' else snapshot.rgb_file_path
        frame = snapshot.ir_frame if img_type == 'ir' else snapshot.rgb_frame
        
        # 优先尝试从磁盘文件加载（ROI 图像）
        if file_path and os.path.exists(file_path):
            try:
                disk_frame = cv2.imread(file_path)
                if disk_frame is not None:
                    logger.debug(f"从磁盘加载 {img_type.upper()} ROI 图像: {file_path}")
                    return self.create_thumbnail_image(disk_frame, size)
            except Exception as e:
                logger.warning(f"从磁盘加载 {img_type.upper()} 图像失败: {e}")
        
        # 尝试从 detection_result 实时裁剪 ROI
        if hasattr(snapshot, 'detection_result') and snapshot.detection_result and frame is not None:
            roi_frame = self._extract_roi_from_detection(frame, snapshot.detection_result, img_type)
            if roi_frame is not None:
                logger.debug(f"从 detection_result 实时裁剪 {img_type.upper()} ROI")
                return self.create_thumbnail_image(roi_frame, size)
        
        # 回退：使用内存中的原始帧
        if frame is not None:
            return self.create_thumbnail_image(frame, size)
        
        # 最后回退：返回空白图像
        return QPixmap(size[0], size[1])
    
    def _extract_roi_from_detection(self, frame: np.ndarray, detection_result: dict, img_type: str) -> Optional[np.ndarray]:
        """
        从 detection_result 中提取 ROI 区域并裁剪图像
        
        Args:
            frame: 原始图像帧 (BGR)
            detection_result: MediaPipe 检测结果
            img_type: 'ir' 或 'rgb'
        
        Returns:
            裁剪后的 ROI 图像 (BGR) 或 None
        """
        try:
            
            # 获取对应类型的检测结果
            detection_key = 'ir_detection' if img_type == 'ir' else 'rgb_detection'
            detection = detection_result.get(detection_key, {})
            hands = detection.get('hands', [])
            
            if not hands:
                return None
            
            # 选择面积最大的手
            best_hand = None
            best_area = 0.0
            
            for hand in hands:
                roi_corners = hand.get('roi_corners')
                if not roi_corners or len(roi_corners) != 4:
                    continue
                
                pts = np.array(roi_corners, dtype=np.float32)
                area = cv2.contourArea(pts)
                if area > best_area:
                    best_area = area
                    best_hand = hand
            
            if not best_hand:
                return None
            
            roi_corners = best_hand.get('roi_corners')
            if not roi_corners or len(roi_corners) != 4:
                return None
            
            # 执行 ROI 裁剪（不保存到文件）
            # crop_and_save_roi 需要 RGB 输入
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 使用透视变换裁剪（与保存时相同的逻辑）
            pts1 = np.array([[float(x), float(y)] for (x, y) in roi_corners], dtype=np.float32)
            side = float(np.linalg.norm(pts1[1] - pts1[0]))
            
            if side <= 1.0:
                return None
            
            # 目标映射：保证 top edge（水平方向）映射到输出图像的顶部 (9 在左, 13 在右)
            pts2 = np.array([[0.0, 0.0], [side - 1.0, 0.0], 
                             [side - 1.0, side - 1.0], [0.0, side - 1.0]], dtype=np.float32)

            M = cv2.getPerspectiveTransform(pts1, pts2)
            dst = cv2.warpPerspective(frame_rgb, M, (int(round(side)), int(round(side))), 
                                     flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            
            # 转换回 BGR
            dst_bgr = cv2.cvtColor(dst, cv2.COLOR_RGB2BGR)
            return dst_bgr
            
        except Exception as e:
            logger.warning(f"从 detection_result 提取 ROI 失败: {e}")
            return None
    
    def create_thumbnail_image(self, frame: np.ndarray, size: Tuple[int, int] = (180, 100)) -> QPixmap:
        """
        创建缩略图
        
        Args:
            frame: 原始图像帧
            size: 缩略图尺寸 (width, height)
        
        Returns:
            QPixmap缩略图
        """
        # 将BGR转换为RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            # 灰度图像转RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        
        # 获取原始尺寸
        h, w = rgb_frame.shape[:2]
        
        # 计算缩放比例（保持宽高比）
        target_w, target_h = size
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # 调整大小
        resized = cv2.resize(rgb_frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 转换为QImage
        h, w, ch = resized.shape
        bytes_per_line = ch * w
        q_image = QImage(resized.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # 转换为QPixmap
        pixmap = QPixmap.fromImage(q_image)
        
        return pixmap
    
    def get_snapshot(self, index: int) -> Optional[Snapshot]:
        """
        获取指定索引的快照
        
        Args:
            index: 快照索引
        
        Returns:
            Snapshot对象，如果索引无效返回None
        """
        with self._lock:
            if 0 <= index < len(self.snapshots):
                return self.snapshots[index]
        return None
    
    def get_all_snapshots(self) -> List[Snapshot]:
        """
        获取所有快照
        
        Returns:
            快照列表
        """
        with self._lock:
            return list(self.snapshots)
    
    def clear_snapshots(self):
        """清空所有快照"""
        with self._lock:
            self.snapshots.clear()
            self.snapshots_to_delete.clear()  # 清空删除列表

        if self.thumbnail_list_widget:
            self.thumbnail_list_widget.clear()

        logger.info("所有快照已清空")

        # 发出信号通知快照数量变化
        self.snapshot_count_changed.emit(0, self.max_snapshots)
    
    def remove_snapshot(self, index: int) -> bool:
        """
        移除指定索引的快照（立即删除文件和更新元数据）
        
        Args:
            index: 快照索引
        
        Returns:
            是否成功移除
        """
        # 第一步：在锁内只做数据操作，不做任何 UI 操作
        removed = None
        snapshot_id_to_remove = None
        files_to_delete = []
        
        with self._lock:
            if 0 <= index < len(self.snapshots):
                removed = self.snapshots.pop(index)
                snapshot_id_to_remove = removed.snapshot_id
                logger.info(f"已移除快照: {removed.timestamp}")
                
                # 收集要删除的文件路径
                if removed.is_saved:
                    if removed.ir_file_path:
                        files_to_delete.append(removed.ir_file_path)
                        logger.debug(f"准备删除 IR 文件: {removed.ir_file_path}")
                    if removed.rgb_file_path:
                        files_to_delete.append(removed.rgb_file_path)
                        logger.debug(f"准备删除 RGB 文件: {removed.rgb_file_path}")
            else:
                return False
        
        # 第二步：释放锁后，在主线程执行所有 UI 操作
        if self.thumbnail_list_widget and snapshot_id_to_remove:
            try:
                logger.debug(f"尝试从 QListWidget 中移除项 snapshot_id={snapshot_id_to_remove}")
                found = False
                count = self.thumbnail_list_widget.count()
                for i in range(count):
                    try:
                        it = self.thumbnail_list_widget.item(i)
                        if it is None:
                            continue
                        data = it.data(Qt.UserRole)
                        if data == snapshot_id_to_remove:
                            # 先获取并移除关联的 widget
                            try:
                                w = self.thumbnail_list_widget.itemWidget(it)
                                if w is not None:
                                    self.thumbnail_list_widget.removeItemWidget(it)
                                    w.deleteLater()
                            except Exception:
                                pass
                            # 取出并删除 item
                            item = self.thumbnail_list_widget.takeItem(i)
                            try:
                                del item
                            except Exception:
                                pass
                            found = True
                            logger.debug(f"已从 QListWidget 中移除项 index={i} snapshot_id={snapshot_id_to_remove}")
                            break
                    except Exception:
                        continue
                
                if not found:
                    # 作为回退，若未找到对应 item 则重建全部缩略图（较慢）
                    logger.debug(f"未在 QListWidget 中找到 snapshot_id={snapshot_id_to_remove}，回退到重建全部缩略图")
                    try:
                        self.update_thumbnail_display()
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"从 QListWidget 中移除项时出错: {e}")
        
        # 第三步：发出信号通知快照数量变化
        with self._lock:
            current_len = len(self.snapshots)
        self.snapshot_count_changed.emit(current_len, self.max_snapshots)
        
        # 第四步：异步删除文件与更新元数据，避免阻塞 UI 线程
        if files_to_delete:
            def _delete_async(files):
                try:
                    deleted_count = snapshot_io.delete_snapshot_files(files)
                    logger.info(f"后台已删除 {deleted_count} 个快照文件并更新元数据")
                except Exception as e:
                    logger.error(f"后台删除快照文件失败: {e}")
            
            t = threading.Thread(target=_delete_async, args=(files_to_delete,), daemon=True)
            t.start()
        
        return True
    
    def get_snapshot_count(self) -> int:
        """获取当前快照数量"""
        with self._lock:
            return len(self.snapshots)
    
    def is_full(self) -> bool:
        """检查是否已达到最大快照数量"""
        with self._lock:
            return len(self.snapshots) >= self.max_snapshots
    
    def save_snapshots(self, save_dir: str, user_id: Optional[str] = None) -> List[str]:
        """
        保存所有快照到指定目录（预留接口）
        
        Args:
            save_dir: 保存目录
            user_id: 用户ID（可选，用于组织文件结构）
        
        Returns:
            已保存文件的路径列表
        """
        import os
        
        saved_files = []
        
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        with self._lock:
            snapshots_copy = list(self.snapshots)

        for snapshot in snapshots_copy:
            # 使用快照的时间戳作为文件名
            timestamp = snapshot.timestamp
            
            # 保存IR图像
            if snapshot.ir_frame is not None:
                ir_filename = f"IR_{timestamp}.bmp"
                ir_path = os.path.join(save_dir, ir_filename)
                # BMP is lossless; use default cv2.imwrite which will write BMP when extension is .bmp
                cv2.imwrite(ir_path, snapshot.ir_frame)
                saved_files.append(ir_path)
                logger.debug(f"IR图像已保存: {ir_path}")
            
            # 保存RGB图像
            if snapshot.rgb_frame is not None:
                rgb_filename = f"RGB_{timestamp}.bmp"
                rgb_path = os.path.join(save_dir, rgb_filename)
                cv2.imwrite(rgb_path, snapshot.rgb_frame)
                saved_files.append(rgb_path)
                logger.debug(f"RGB图像已保存: {rgb_path}")
        
        logger.info(f"已保存 {len(saved_files)} 个文件到 {save_dir}")
        return saved_files
    
    def save_single_snapshot(self, index: int, save_dir: str) -> List[str]:
        """
        保存单个快照（预留接口）
        
        Args:
            index: 快照索引
            save_dir: 保存目录
        
        Returns:
            已保存文件的路径列表
        """
        import os
        
        snapshot = self.get_snapshot(index)
        if snapshot is None:
            logger.error(f"快照索引无效: {index}")
            return []
        
        saved_files = []
        
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        timestamp = snapshot.timestamp
        
        # 保存IR图像
        if snapshot.ir_frame is not None:
            ir_filename = f"IR_{timestamp}.bmp"
            ir_path = os.path.join(save_dir, ir_filename)
            cv2.imwrite(ir_path, snapshot.ir_frame)
            saved_files.append(ir_path)
        
        # 保存RGB图像
        if snapshot.rgb_frame is not None:
            rgb_filename = f"RGB_{timestamp}.bmp"
            rgb_path = os.path.join(save_dir, rgb_filename)
            cv2.imwrite(rgb_path, snapshot.rgb_frame)
            saved_files.append(rgb_path)
        
        logger.info(f"快照 #{index + 1} 已保存到 {save_dir}")
        return saved_files
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """
        处理列表项双击事件，显示原图预览
        
        Args:
            item: 被双击的列表项
        """
        # 获取快照 id 并转换为当前索引
        snapshot_id = item.data(Qt.UserRole)
        index = self._find_index_by_snapshot_id(snapshot_id)
        snapshot = self.get_snapshot(index) if index is not None else None
        
        if snapshot:
            logger.info(f"双击预览快照 #{index + 1}")
            self.show_preview_dialog(snapshot, index)
    
    def show_context_menu(self, position):
        """
        显示右键菜单
        
        Args:
            position: 鼠标位置
        """
        # 获取点击位置的item
        item = self.thumbnail_list_widget.itemAt(position)
        
        if item is None:
            return
        
        # 获取快照 id 并转换为当前索引
        snapshot_id = item.data(Qt.UserRole)
        index = self._find_index_by_snapshot_id(snapshot_id)
        snapshot = self.get_snapshot(index) if index is not None else None
        
        if snapshot is None:
            return
        
        # 创建右键菜单
        menu = QMenu(self.thumbnail_list_widget)
        
        # 添加预览动作
        preview_action = QAction("预览原图", self.thumbnail_list_widget)
        preview_action.triggered.connect(lambda: self.show_preview_dialog(snapshot, index))
        menu.addAction(preview_action)
        
        # 添加分隔符
        menu.addSeparator()
        
        # 添加删除动作
        delete_action = QAction("删除快照", self.thumbnail_list_widget)
        delete_action.triggered.connect(lambda: self.delete_snapshot_with_confirmation(index))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(self.thumbnail_list_widget.mapToGlobal(position))
    
    def delete_snapshot_with_confirmation(self, index: int):
        """
        删除快照（直接删除，不需要确认）
        
        Args:
            index: 快照索引
        """
        snapshot = self.get_snapshot(index)
        if snapshot is None:
            return
        
        # 直接执行删除
        success = self.remove_snapshot(index)
        if success:
            logger.info(f"用户删除了快照 #{index + 1} - {snapshot.timestamp}")
        else:
            logger.error(f"删除快照失败: 索引 {index}")
    
    def handle_key_press(self, event):
        """
        处理键盘按键事件
        
        Args:
            event: 键盘事件
        """
        from PySide6.QtCore import Qt as QtKey
        
        # 检查是否按下Delete键
        if event.key() == QtKey.Key.Key_Delete:
            # 获取当前选中的item
            current_item = self.thumbnail_list_widget.currentItem()
            
            if current_item is not None:
                # 获取快照 id 并转换为当前索引
                snapshot_id = current_item.data(Qt.UserRole)
                index = self._find_index_by_snapshot_id(snapshot_id)
                if index is not None:
                    # 删除快照
                    self.delete_snapshot_with_confirmation(index)
        else:
            # 调用原始的keyPressEvent
            QListWidget.keyPressEvent(self.thumbnail_list_widget, event)
    
    def show_preview_dialog(self, snapshot: Snapshot, index: int):
        """
        显示原图预览对话框
        
        Args:
            snapshot: 要预览的快照
            index: 快照索引
        """
        # 创建对话框
        dialog = QDialog()
        dialog.setWindowTitle(f"快照预览 #{index + 1} - {snapshot.timestamp}")
        dialog.setWindowIcon(get_dialog_icon())
        
        # 设置窗口大小为1600x900，并固定不可调整
        dialog.setFixedSize(1920, 1080)
        
        # 创建主布局
        main_layout = QVBoxLayout(dialog)
        
        # 创建标题
        title_label = QLabel(f"快照 #{index + 1} - {snapshot.timestamp}")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 创建水平布局容纳IR和RGB图像
        images_layout = QHBoxLayout()
        
        # 计算可用空间（对话框宽度减去边距，除以2）
        available_width = (1920 - 60) // 2  # 减去边距，平均分配给两张图
        available_height = 1080 - 120  # 减去标题、用户信息等的高度
        
        # 显示IR图像
        if snapshot.ir_frame is not None:
            ir_container = QVBoxLayout()
            
            ir_title = QLabel("IR 图像")
            ir_title.setStyleSheet("font-size: 12px; font-weight: bold;")
            ir_title.setAlignment(Qt.AlignCenter)
            ir_container.addWidget(ir_title)
            
            # 创建图像标签
            ir_label = QLabel()
            ir_pixmap = self.numpy_to_pixmap_scaled(snapshot.ir_frame, available_width, available_height)
            ir_label.setPixmap(ir_pixmap)
            ir_label.setAlignment(Qt.AlignCenter)
            
            ir_container.addWidget(ir_label)
            images_layout.addLayout(ir_container)
        
        # 显示RGB图像
        if snapshot.rgb_frame is not None:
            rgb_container = QVBoxLayout()
            
            rgb_title = QLabel("RGB 图像")
            rgb_title.setStyleSheet("font-size: 12px; font-weight: bold;")
            rgb_title.setAlignment(Qt.AlignCenter)
            rgb_container.addWidget(rgb_title)
            
            # 创建图像标签
            rgb_label = QLabel()
            rgb_pixmap = self.numpy_to_pixmap_scaled(snapshot.rgb_frame, available_width, available_height)
            rgb_label.setPixmap(rgb_pixmap)
            rgb_label.setAlignment(Qt.AlignCenter)
            
            rgb_container.addWidget(rgb_label)
            images_layout.addLayout(rgb_container)
        
        main_layout.addLayout(images_layout)
        
        # 添加用户信息（如果有）
        if snapshot.user_id:
            user_info = QLabel(f"用户ID: {snapshot.user_id}")
            user_info.setStyleSheet("font-size: 12px; padding: 10px;")
            user_info.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(user_info)
        
        dialog.setLayout(main_layout)
        
        # 显示对话框
        dialog.exec()
    
    def numpy_to_pixmap(self, frame: np.ndarray) -> QPixmap:
        """
        将numpy数组转换为QPixmap（原图，不缩放）
        
        Args:
            frame: numpy数组图像
        
        Returns:
            QPixmap对象
        """
        # 将BGR转换为RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            # 灰度图像转RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        
        # 获取图像尺寸
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        # 转换为QImage
        q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # 转换为QPixmap
        pixmap = QPixmap.fromImage(q_image)
        
        return pixmap
    
    def numpy_to_pixmap_scaled(self, frame: np.ndarray, max_width: int, max_height: int) -> QPixmap:
        """
        将numpy数组转换为QPixmap，缩放以适应指定尺寸，保持原始比例
        
        Args:
            frame: numpy数组图像
            max_width: 最大宽度
            max_height: 最大高度
        
        Returns:
            缩放后的QPixmap对象
        """
        # 将BGR转换为RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            # 灰度图像转RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        
        # 获取原始图像尺寸
        orig_h, orig_w = rgb_frame.shape[:2]
        
        # 计算缩放比例（保持宽高比）
        scale_w = max_width / orig_w
        scale_h = max_height / orig_h
        scale = min(scale_w, scale_h)  # 使用较小的缩放比例以确保完全适应
        
        # 计算新尺寸
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # 缩放图像
        resized = cv2.resize(rgb_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # 获取缩放后的图像尺寸
        h, w, ch = resized.shape
        bytes_per_line = ch * w
        
        # 转换为QImage
        q_image = QImage(resized.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # 转换为QPixmap
        pixmap = QPixmap.fromImage(q_image)
        
        return pixmap
    
    def save_user_snapshots(self, user_id: str) -> Tuple[bool, int]:
        """
        保存当前用户的所有快照到磁盘
        
        Args:
            user_id: 用户ID
        
        Returns:
            (是否成功, 保存的数量)
        """
        # 注意：删除操作已在 remove_snapshot() 中立即执行，这里只保存新快照
        
        # 保存新快照
        success, count = snapshot_io.save_user_snapshots(
            self.project_dir,
            user_id,
            self.snapshots,
            self.user_snapshot_counter
        )
        
        if success:
            self.current_user_id = user_id
            # 保存成功后重新更新缩略图显示，以便从磁盘加载 ROI 图像
            logger.info("快照保存成功，刷新缩略图显示以加载 ROI 图像")
            self.update_thumbnail_display()
        
        return success, count
    
    def load_user_snapshots(self, user_id: str) -> bool:
        """
        加载指定用户的历史快照
        
        Args:
            user_id: 用户ID
        
        Returns:
            是否成功加载
        """
        # 获取用户的历史快照文件（现在返回 snapshot_id）
        snapshot_files, total_count = snapshot_io.load_user_snapshots(
            self.project_dir,
            user_id
        )
        
        if not snapshot_files:
            logger.info(f"用户 {user_id} 没有历史快照可加载")
            self.current_user_id = user_id
            return True
        
        # 清空当前快照
        self.clear_snapshots()
        
        # 加载快照到内存（限制数量）
        load_count = 0
        new_snapshots = []
        for ir_path, rgb_path, timestamp, snapshot_id, hand in snapshot_files[-self.max_snapshots:]:
            # 读取图像
            ir_frame = None
            rgb_frame = None
            
            if ir_path and os.path.exists(ir_path):
                ir_frame = cv2.imread(ir_path, cv2.IMREAD_UNCHANGED)
            
            if rgb_path and os.path.exists(rgb_path):
                rgb_frame = cv2.imread(rgb_path, cv2.IMREAD_UNCHANGED)
            
            # 至少有一个图像才创建快照
            if ir_frame is not None or rgb_frame is not None:
                # 使用元数据中的时间戳，如果没有则使用文件修改时间
                if not timestamp:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    if ir_path and os.path.exists(ir_path):
                        file_time = datetime.fromtimestamp(os.path.getmtime(ir_path))
                        timestamp = file_time.strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    elif rgb_path and os.path.exists(rgb_path):
                        file_time = datetime.fromtimestamp(os.path.getmtime(rgb_path))
                        timestamp = file_time.strftime("%Y%m%d_%H%M%S_%f")[:-3]
                
                snapshot = Snapshot(
                    timestamp=timestamp,
                    ir_frame=ir_frame,
                    rgb_frame=rgb_frame,
                    snapshot_id=snapshot_id,  # 使用加载的 snapshot_id
                    user_id=user_id,
                    is_saved=True,  # 从磁盘加载的快照标记为已保存
                    ir_file_path=ir_path,  # 记录文件路径
                    rgb_file_path=rgb_path,  # 记录文件路径
                    hand=hand
                )
                new_snapshots.append(snapshot)
                load_count += 1
        # 将新快照添加到内存（受锁保护）并更新UI
        with self._lock:
            self.snapshots.extend(new_snapshots)
            current_len = len(self.snapshots)

        # 更新UI
        self.update_thumbnail_display()

        # 发出信号更新计数
        self.snapshot_count_changed.emit(current_len, self.max_snapshots)

        # 设置当前用户ID
        self.current_user_id = user_id
        
        # user_snapshot_counter 不再使用索引，仅用于兼容性
        self.user_snapshot_counter[user_id] = total_count
        logger.info(f"已加载用户 {user_id} 的 {load_count} 张历史快照（共 {total_count} 张）")
        
        return True


