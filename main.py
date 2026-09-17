# -*- coding: utf-8 -*-
import sys
import os
import subprocess
import multiprocessing
import numpy as np
import argparse
import json
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QInputDialog, QMessageBox, 
                                QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                                QPushButton, QGroupBox)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QThread, Signal, QObject
from Plampture_ui import Ui_MainWindow
from dynamic_layout import setup_dynamic_layout
from camera_manager import CameraManager
from scan_QRcode import scan_qrcode
from capture import SnapshotManager
import snapshot_io
import time
from loguru import logger
import platform
import cv2
import queue
import re
from PySide6.QtGui import QShortcut, QKeySequence

# pygrabber 仅在 Windows 平台可用
if platform.system() == 'Windows':
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        logger.warning("pygrabber 未安装，Windows 平台摄像头名称检测功能受限")

# 获取应用程序根目录（兼容exe打包）
def get_app_dir():
    """获取应用程序根目录，兼容开发环境和打包后的exe环境"""
    if getattr(sys, 'frozen', False):
        # 打包为exe后，使用exe所在目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境，使用脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

# 全局项目配置
global_project_config = {
    "project_id": None,
    "project_name": None,
    "project_dir": None
}

# ROI 配置
USE_CIRCUMSCRIBED_ROI = False  # 是否使用外接矩形 ROI (True: 外接, False: 内接)

# 全局图标路径（使用函数后调用）
def get_info_icon_path():
    return os.path.join(get_app_dir(), "icon", "info.ico")

INFO_ICON_PATH = None  # 延迟初始化

def get_message_box_icon():
    """ 获取消息框图标"""
    icon_path = get_info_icon_path()
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    return QIcon()

def show_input_dialog_with_icon(parent, title, label, items=None, current_index=0, editable=False, 
                                  input_mode='item', value=0, min_value=0, max_value=100, step=1):
    """
    显示带图标的输入对话框
    
    Args:
        parent: 父窗口
        title: 对话框标题
        label: 提示标签
        items: 选项列表（item模式）
        current_index: 当前选项索引（item模式）
        editable: 是否可编辑（item模式）
        input_mode: 'item' 或 'int'
        value: 默认值（int模式）
        min_value: 最小值（int模式）
        max_value: 最大值（int模式）
        step: 步长（int模式）
    
    Returns:
        (result, ok)
    """
    if input_mode == 'item':
        # 创建并显示选项对话框
        dialog = QInputDialog(parent)
        dialog.setWindowIcon(get_message_box_icon())
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setComboBoxItems(items)
        dialog.setTextValue(items[current_index])
        dialog.setComboBoxEditable(editable)
        
        ok = dialog.exec()
        result = dialog.textValue()
        return result, ok
    
    elif input_mode == 'int':
        # 创建并显示整数输入对话框
        dialog = QInputDialog(parent)
        dialog.setWindowIcon(get_message_box_icon())
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setIntValue(value)
        dialog.setIntMinimum(min_value)
        dialog.setIntMaximum(max_value)
        dialog.setIntStep(step)
        
        ok = dialog.exec()
        result = dialog.intValue()
        return result, ok
    
    return None, False

# 全局字典
global_user_info = {
    "user_id": None,
    "user_name": None,
    "capture_timestamp": None
}

global_config = {
    "ir_camera_id": 0,
    "rgb_camera_id": 1,
    "default_resolution": (1920, 1080),
    "custom_resolution": (1920, 1080),
    "rate": 30,
    "max_snapshots": 40
}

# 预设的分辨率选项
resolution_options = [
    "324x240",
    "352x288",
    "640x480",
    "800x600",
    "1280x720",
    "1920x1080", #最高
]

# 预设的帧率选项
rate_options = [
    5,
    10,
    20,
    30,
]

class StatusBarHandler(QObject):
    """自定义日志处理器，将日志输出到状态栏"""
    # 定义信号，用于线程安全地更新状态栏
    log_signal = Signal(str)
    
    def __init__(self, statusbar):
        super().__init__()
        self.statusbar = statusbar
        self.log_signal.connect(self._update_statusbar)
    
    def _update_statusbar(self, message):
        """更新状态栏显示（在主线程中执行）"""
        self.statusbar.showMessage(message)
    
    def write(self, message):
        """loguru 调用的写入方法"""
        # 移除 ANSI 颜色码和多余的换行符
        clean_message = re.sub(r'\x1b\[[0-9;]+m', '', message.strip())
        if clean_message:
            self.log_signal.emit(clean_message)


class QRCodeScannerThread(QThread):
    """二维码扫描线程"""
    # 定义信号，用于传递扫描结果
    qrcode_detected = Signal(str)  # 扫描到二维码时发出信号
    
    def __init__(self, camera_manager):
        super().__init__()
        self.camera_manager = camera_manager
        self.running = True
        self.scanning_enabled = True  # 控制是否进行扫描
        
    def run(self):
        """线程运行函数，持续扫描二维码"""
        logger.info("二维码扫描线程已启动")
        
        while self.running:
            try:
                # 检查是否启用扫描
                if not self.scanning_enabled:
                    # 挂起状态，休眠后继续检查
                    self.msleep(100)
                    continue
                
                # 优先使用 CameraManager 提供的非破坏性缓存 latest_rgb_frame（copy 读取）
                frame = None
                try:
                    if hasattr(self.camera_manager, 'latest_rgb_frame') and self.camera_manager.latest_rgb_frame is not None:
                        # copy 一份，避免修改共享内存或被其他线程/进程覆盖
                        frame = self.camera_manager.latest_rgb_frame.copy()
                    else:
                        # 回退到读取队列（非阻塞），保持兼容性
                        if not self.camera_manager.rgb_queue.empty():
                            frame_data = self.camera_manager.rgb_queue.get_nowait()
                            dtype = np.dtype(frame_data['dtype'])
                            frame = np.frombuffer(
                                frame_data['bytes'],
                                dtype=dtype
                            ).reshape(frame_data['shape']).copy()
                except Exception as _e:
                    # 如果是队列空导致的 Race，Quietly ignore; 其它异常记录堆栈
                    try:
                        from queue import Empty as _Empty
                        if isinstance(_e, _Empty):
                            # 正常的竞争情况，忽略
                            pass
                        else:
                            logger.exception("读取用于扫码的帧时出错")
                    except Exception:
                        logger.exception("读取用于扫码的帧时出错")

                if frame is not None:
                    # 调用二维码扫描函数（使用复制的帧数据）
                    qr_result = scan_qrcode(frame)
                    if qr_result:
                        logger.info(f"扫描到二维码: {qr_result}")
                        self.qrcode_detected.emit(qr_result)
                else:
                    # 没有可用帧时稍微休眠，避免CPU占用过高
                    self.msleep(50)  # 休眠50毫秒
                    
            except Exception as e:
                logger.error(f"二维码扫描异常: {e}", exc_info=True)
                self.msleep(100)
        
        logger.info("二维码扫描线程已停止")
    
    def pause_scanning(self):
        """挂起扫描（线程继续运行，但不进行识别）"""
        self.scanning_enabled = False
        logger.info("二维码扫描已挂起")
    
    def resume_scanning(self):
        """恢复扫描"""
        self.scanning_enabled = True
        logger.info("二维码扫描已恢复")
    
    def is_scanning(self):
        """检查当前是否正在扫描"""
        return self.scanning_enabled
    
    def stop(self):
        """停止线程"""
        self.running = False
        self.wait()  # 等待线程结束
        logger.info("二维码扫描线程已完全停止")


def handle_qrcode_detected(qr_data, ui):
    """
    处理扫描到的二维码数据
    
    Args:
        qr_data: 二维码内容字符串
        ui: UI对象,用于更新界面
    """
    # 检查是否有未保存的快照
    if hasattr(ui, 'snapshot_manager') and global_user_info.get("user_id"):
        unsaved_count = sum(1 for s in ui.snapshot_manager.snapshots if not s.is_saved)
        if unsaved_count > 0:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("警告")
            msg_box.setText(f"当前用户还有 {unsaved_count} 张未保存的快照！\n\n扫描新用户会丢失这些数据，是否继续？")
            msg_box.setInformativeText("建议点击 NEXT 按钮保存后再扫描新用户。")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)
            reply = msg_box.exec()
            
            if reply == QMessageBox.No:
                logger.info("用户取消扫描新二维码，保留未保存的快照")
                # 恢复二维码扫描
                if hasattr(ui, 'qr_scanner_thread'):
                    ui.qr_scanner_thread.resume_scanning()
                return
    
    global_user_info["user_id"] = qr_data
    logger.info(f"识别到的二维码内容: {qr_data}")
    
    # 更新 id_label 显示
    ui.id_label.setText(f"身份ID: {qr_data}")
    
    # 检查并加载用户的历史快照
    if hasattr(ui, 'snapshot_manager') and global_project_config.get("project_dir"):
        user_snapshots_dir = os.path.join(
            global_project_config["project_dir"], 
            "snapshots", 
            qr_data
        )
        
        if os.path.exists(user_snapshots_dir):
            logger.info(f"发现用户 {qr_data} 的历史数据，正在加载...")
            success = ui.snapshot_manager.load_user_snapshots(qr_data)
            if success:
                logger.info(f"用户 {qr_data} 的历史快照已加载")
        else:
            logger.info(f"用户 {qr_data} 是新用户，无历史数据")
    
    # 扫描到内容后自动暂停扫描
    if hasattr(ui, 'qr_scanner_thread'):
        ui.qr_scanner_thread.pause_scanning()
        logger.info("扫描到二维码后自动暂停扫描")


def update_snap_button_text(ui):
    """
    更新 SNAP 按钮的文本显示
    
    Args:
        ui: UI对象
    """
    if hasattr(ui, 'snapshot_manager'):
        count = ui.snapshot_manager.get_snapshot_count()
        max_count = ui.snapshot_manager.max_snapshots
        half = max_count // 2
        if count < half:
            hand_text = "左手"
        elif count < max_count:
            hand_text = "右手"
        else:
            hand_text = "已满"
        # 在按钮上显示当前采集手部
        ui.SNAP_Button.setText(f"拍摄\n({count}/{max_count})\n({hand_text})")
    else:
        ui.SNAP_Button.setText("拍摄\n(0/10)")


def on_snapshot_count_changed(current_count, max_count, ui):
    """
    当快照数量变化时的槽函数
    
    Args:
        current_count: 当前快照数量
        max_count: 最大快照数量
        ui: UI对象
    """
    half = max_count // 2
    if current_count < half:
        hand_text = "左手"
    elif current_count < max_count:
        hand_text = "右手"
    else:
        hand_text = "已满"
    ui.SNAP_Button.setText(f"拍摄\n({current_count}/{max_count})\n({hand_text})")
    logger.debug(f"SNAP_Button 已更新: {current_count}/{max_count}")


def save_camera_settings(ui):
    """保存当前摄像头设置到 workspace_logs.json"""
    try:
        # 尝试获取滑块值，如果滑块不存在则使用默认值或跳过
        settings = {}
        
        # IR Camera
        if hasattr(ui, 'IR_bright_ctrl_horizontalSlider'):
            settings['ir_brightness'] = ui.IR_bright_ctrl_horizontalSlider.value()
        if hasattr(ui, 'IR_contrast_ctrl_horizontalSlider'):
            settings['ir_contrast'] = ui.IR_contrast_ctrl_horizontalSlider.value()
        if hasattr(ui, 'IR_exposure_ctrl_horizontalSlider'):
            settings['ir_exposure'] = ui.IR_exposure_ctrl_horizontalSlider.value()
            
        # RGB Camera
        if hasattr(ui, 'RGB_bright_ctrl_horizontalSlider'):
            settings['rgb_brightness'] = ui.RGB_bright_ctrl_horizontalSlider.value()
        if hasattr(ui, 'RGB_contrast_ctrl_horizontalSlider'):
            settings['rgb_contrast'] = ui.RGB_contrast_ctrl_horizontalSlider.value()
        if hasattr(ui, 'RGB_exposure_ctrl_horizontalSlider'):
            settings['rgb_exposure'] = ui.RGB_exposure_ctrl_horizontalSlider.value()
            
        settings['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_path = os.path.join(get_app_dir(), "workspace", "workspace_logs.json")
        
        data = {}
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        
        # 保存到 camera_settings 字段
        data['camera_settings'] = settings
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        logger.info(f"摄像头设置已保存: {settings}")
    except Exception as e:
        logger.error(f"保存摄像头设置失败: {e}")

def load_camera_settings(ui):
    """从 workspace_logs.json 加载摄像头设置并应用"""
    try:
        log_path = os.path.join(get_app_dir(), "workspace", "workspace_logs.json")
        if not os.path.exists(log_path):
            return
            
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        settings = data.get('camera_settings')
        if not settings:
            return
            
        logger.info(f"正在加载摄像头设置: {settings}")
        
        # 应用设置
        # IR Camera
        if 'ir_brightness' in settings and hasattr(ui, 'IR_bright_ctrl_horizontalSlider'):
            ui.IR_bright_ctrl_horizontalSlider.setValue(settings['ir_brightness'])
        if 'ir_contrast' in settings and hasattr(ui, 'IR_contrast_ctrl_horizontalSlider'):
            ui.IR_contrast_ctrl_horizontalSlider.setValue(settings['ir_contrast'])
        if 'ir_exposure' in settings and hasattr(ui, 'IR_exposure_ctrl_horizontalSlider'):
            ui.IR_exposure_ctrl_horizontalSlider.setValue(settings['ir_exposure'])
            
        # RGB Camera
        if 'rgb_brightness' in settings and hasattr(ui, 'RGB_bright_ctrl_horizontalSlider'):
            ui.RGB_bright_ctrl_horizontalSlider.setValue(settings['rgb_brightness'])
        if 'rgb_contrast' in settings and hasattr(ui, 'RGB_contrast_ctrl_horizontalSlider'):
            ui.RGB_contrast_ctrl_horizontalSlider.setValue(settings['rgb_contrast'])
        if 'rgb_exposure' in settings and hasattr(ui, 'RGB_exposure_ctrl_horizontalSlider'):
            ui.RGB_exposure_ctrl_horizontalSlider.setValue(settings['rgb_exposure'])
            
        logger.info("摄像头设置已加载并应用")
        
    except Exception as e:
        logger.error(f"加载摄像头设置失败: {e}")

def handle_window_close(event, qr_scanner_thread, camera_manager, snapshot_manager, ui=None):
    """
    处理窗口关闭事件
    
    Args:
        event: 关闭事件对象
        qr_scanner_thread: 二维码扫描线程
        camera_manager: 摄像头管理器
        snapshot_manager: 快照管理器
    """
    logger.info("=== 开始关闭应用程序 ===")
    
    # 保存摄像头设置
    if ui:
        save_camera_settings(ui)
        
    logger.info("正在停止二维码扫描线程...")
    qr_scanner_thread.stop()  # 先停止扫描线程
    logger.info("正在停止摄像头管理器...")
    camera_manager.stop()  # 再停止摄像头
    
    # 清理旧的删除记录（保留3天内的）
    logger.info("正在清理旧的删除记录...")
    try:
        cleaned_count = snapshot_io.cleanup_old_deleted_records(
            snapshot_manager.project_dir,
            days_to_keep=3
        )
        if cleaned_count > 0:
            logger.info(f"已清理 {cleaned_count} 条超过3天的删除记录")
    except Exception as e:
        logger.error(f"清理删除记录时出错: {e}")
    
    logger.info("=== 应用程序已关闭 ===")
    
    # 通知setup.py重新显示窗口（通过创建信号文件）
    logger.info("正在通知项目设置窗口...")
    try:
        workspace_dir = os.path.join(get_app_dir(), "workspace")
        signal_file = os.path.join(workspace_dir, ".show_setup_signal")
        
        # 创建信号文件
        with open(signal_file, 'w') as f:
            f.write(str(datetime.now()))
        
        logger.info("已发送显示窗口信号")
    except Exception as e:
        logger.error(f"发送显示窗口信号失败: {e}")
    
    event.accept()


def handle_qr_button_clicked(ui):
    """
    处理 QR 按钮点击事件
    
    Args:
        ui: UI对象
    """
    logger.info(">>> QR按钮被点击")
    
    # 检查是否有未保存的快照
    if hasattr(ui, 'snapshot_manager') and global_user_info.get("user_id"):
        unsaved_count = sum(1 for s in ui.snapshot_manager.snapshots if not s.is_saved)
        if unsaved_count > 0:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("警告")
            msg_box.setText(f"当前用户还有 {unsaved_count} 张未保存的快照！\n\n点击 QR 按钮会丢失这些数据，是否继续？")
            msg_box.setInformativeText("建议点击 NEXT 按钮保存后再重新扫描。")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)
            reply = msg_box.exec()
            
            if reply == QMessageBox.No:
                logger.info("用户取消QR按钮操作，保留未保存的快照")
                return
    
    # 清空 global_user_info
    global_user_info["user_id"] = None
    global_user_info["user_name"] = None
    global_user_info["capture_timestamp"] = None
    logger.debug(f"全局数据已清空: {global_user_info}")
    
    # 清空 id_label 显示
    ui.id_label.setText("身份ID:  ")
    logger.debug("ID标签已重置")
    
    # 清空 capture_timestamp_label 显示
    ui.capture_timestamp_label.setText("拍摄时间: ")
    logger.debug("拍摄时间标签已重置")
    
    # 清空快照管理器和缩略图列表（会自动触发信号更新SNAP_Button）
    if hasattr(ui, 'snapshot_manager'):
        ui.snapshot_manager.clear_snapshots()
        logger.info("快照管理器已清空")
    
    # 恢复二维码扫描
    if hasattr(ui, 'qr_scanner_thread'):
        ui.qr_scanner_thread.resume_scanning()
        logger.info("二维码扫描已恢复，等待扫描...")
    else:
        logger.warning("未找到二维码扫描线程引用")


def handle_next_button_clicked(ui):
    """
    处理 NEXT 按钮点击事件
    
    Args:
        ui: UI对象
    """
    logger.info(">>> NEXT按钮被点击")
    
    # 保存当前用户的快照
    if hasattr(ui, 'snapshot_manager') and global_user_info.get("user_id"):
        user_id = global_user_info["user_id"]
        success, count = ui.snapshot_manager.save_user_snapshots(user_id)
        if success and count > 0:
            logger.info(f"用户 {user_id} 的 {count} 张快照已保存")
            # 显示提示
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setWindowTitle("保存成功")
            msg_box.setText(f"已保存 {count} 张快照到本地")
            msg_box.exec()
        elif count == 0:
            logger.info(f"用户 {user_id} 没有快照需要保存")
    
    # 清空 global_user_info
    global_user_info["user_id"] = None
    global_user_info["user_name"] = None
    global_user_info["capture_timestamp"] = None
    logger.debug(f"全局数据已清空: {global_user_info}")
    
    # 清空 id_label 显示
    ui.id_label.setText("身份ID:  ")
    logger.debug("ID标签已重置为初始提示")
    
    # 清空 capture_timestamp_label 显示
    ui.capture_timestamp_label.setText("拍摄时间: ")
    logger.debug("拍摄时间标签已重置")
    
    # 清空快照管理器和缩略图列表（会自动触发信号更新SNAP_Button）
    if hasattr(ui, 'snapshot_manager'):
        ui.snapshot_manager.clear_snapshots()
        logger.info("快照管理器已清空")
    
    # 恢复二维码扫描
    if hasattr(ui, 'qr_scanner_thread'):
        ui.qr_scanner_thread.resume_scanning()
        logger.info("二维码扫描已恢复，等待扫描...")
    else:
        logger.warning("未找到二维码扫描线程引用")


def handle_snap_button_clicked(ui):
    """
    处理 SNAP 按钮点击事件 - 捕获当前画面
    
    Args:
        ui: UI对象
    """
    logger.info(">>> SNAP按钮被点击")
    
    # 检查是否有用户ID（必须先扫描二维码）
    user_id = global_user_info.get("user_id", None)
    if not user_id:
        logger.warning("未扫描二维码，提示用户")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("提示")
        msg_box.setText("请先扫描二维码再进行拍照")
        msg_box.exec()
        return
    
    # 检查是否有摄像头管理器
    if not hasattr(ui, 'camera_manager'):
        logger.warning("未找到摄像头管理器引用")
        return
    
    # 检查是否有快照管理器
    if not hasattr(ui, 'snapshot_manager'):
        logger.error("未找到快照管理器引用")
        return
    
    # 捕获当前画面
    try:
        ir_frame, rgb_frame, detection_result = ui.camera_manager.capture_snapshot()
    except Exception as e:
        logger.error(f"捕获画面失败: {e}")
        return
    
    # 验证是否成功捕获（至少要有一个画面）
    if ir_frame is None and rgb_frame is None:
        logger.error("捕获画面失败：两个摄像头都没有数据")
        return
    
    # 验证是否同时捕获到两个画面
    if ir_frame is None or rgb_frame is None:
        logger.warning(f"画面捕获不完整 - IR: {'有' if ir_frame is not None else '无'}, RGB: {'有' if rgb_frame is not None else '无'}")
        return  # 必须同时有两个画面才能保存
    
    # 检查是否检测到手部（可选：提示用户）
    has_detection = False
    if detection_result:
        ir_det = detection_result.get('ir_detection', {})
        rgb_det = detection_result.get('rgb_detection', {})
        ir_hands = ir_det.get('hands', [])
        rgb_hands = rgb_det.get('hands', [])
        has_detection = len(ir_hands) > 0 or len(rgb_hands) > 0
    
    if not has_detection:
        logger.warning("未检测到手部，将保存全图而非 ROI")
        # 可选：弹出提示框询问是否继续
        # msg_box = QMessageBox()
        # msg_box.setWindowIcon(get_message_box_icon())
        # msg_box.setIcon(QMessageBox.Warning)
        # msg_box.setWindowTitle("提示")
        # msg_box.setText("未检测到手部，是否继续拍照？\n（将保存全图而非 ROI）")
        # msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        # if msg_box.exec() != QMessageBox.StandardButton.Yes:
        #     return
    
    # 使用快照管理器捕获快照（带锁与恢复机制）
    snapshot = None

    # 计算当前应采集的手（前半数左手，后半数右手）
    try:
        current_count = ui.snapshot_manager.get_snapshot_count()
        max_count = ui.snapshot_manager.max_snapshots
        half = max_count // 2
        hand = 'left' if current_count < half else 'right'
    except Exception:
        hand = None

    # 在捕获前暂停二维码扫描并禁用按钮，防止并发操作
    if hasattr(ui, 'qr_scanner_thread'):
        try:
            ui.qr_scanner_thread.pause_scanning()
        except Exception:
            pass

    try:
        try:
            ui.SNAP_Button.setEnabled(False)
        except Exception:
            pass

        snapshot = ui.snapshot_manager.capture_snapshot(
            ir_frame=ir_frame,
            rgb_frame=rgb_frame,
            user_id=user_id,
            hand=hand,
            detection_result=detection_result
        )
    except Exception as e:
        logger.error(f"快照捕获异常: {e}")
        snapshot = None
    finally:
        # 恢复按钮与二维码扫描状态
        try:
            ui.SNAP_Button.setEnabled(True)
        except Exception:
            pass
        if hasattr(ui, 'qr_scanner_thread'):
            try:
                ui.qr_scanner_thread.resume_scanning()
            except Exception:
                pass

    # 处理捕获结果（在恢复之后）
    if snapshot:
        logger.info(f"快照已捕获 (用户ID: {user_id}, hand={snapshot.hand})")
        # 快照捕获成功后会自动触发信号更新SNAP_Button

        # 更新 capture_timestamp_label
        # 格式化时间戳为更易读的格式：YYYY-MM-DD HH:MM:SS.fff
        timestamp_str = snapshot.timestamp
        if len(timestamp_str) >= 21:  # YYYYMMDD_HHMMSS_fff
            formatted_time = f"{timestamp_str[0:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]} {timestamp_str[9:11]}:{timestamp_str[11:13]}:{timestamp_str[13:15]}.{timestamp_str[16:19]}"
        else:  # YYYYMMDD_HHMMSS
            formatted_time = f"{timestamp_str[0:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]} {timestamp_str[9:11]}:{timestamp_str[11:13]}:{timestamp_str[13:15]}"

        ui.capture_timestamp_label.setText(f"拍摄时间: {formatted_time}")
        logger.debug(f"拍摄时间已更新: {formatted_time}")
    else:
        logger.warning("快照捕获失败")



def handle_action_resolution_triggered(ui):
    """
    处理 分辨率设置 菜单点击事件
    
    Args:
        ui: UI对象
    """
    logger.info(">>> 分辨率设置 菜单被点击")
    

    
    # 当前分辨率
    current_res = global_config["custom_resolution"]
    current_res_str = f"{current_res[0]}x{current_res[1]}"
    
    # 查找当前分辨率在列表中的索引
    try:
        current_index = resolution_options.index(current_res_str)
    except ValueError:
        current_index = len(resolution_options) - 1  # 默认选择"自定义..."
    
    # 弹出选择对话框
    selected_option, ok = show_input_dialog_with_icon(
        None,
        "分辨率设置",
        f"当前分辨率: {current_res_str}\n请选择新的分辨率:",
        items=resolution_options,
        current_index=current_index,
        editable=False,
        input_mode='item'
    )
    
    if not ok:
        logger.info("用户取消了分辨率设置")
        return
    
    logger.info(f"用户选择的分辨率选项: {selected_option}")
    
    # 解析选择的分辨率
    new_resolution = None
    

    # 解析预设分辨率
    parts = selected_option.split('x')
    new_resolution = (int(parts[0]), int(parts[1]))
    logger.info(f"解析预设分辨率: {new_resolution}")

    # 检查是否与当前分辨率相同
    if new_resolution == current_res:
        logger.info("新分辨率与当前分辨率相同，无需更改")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText(f"当前已经是 {current_res_str} 分辨率")
        msg_box.exec()
        return
    
    # 更新全局配置
    global_config["custom_resolution"] = new_resolution
    logger.info(f"全局配置已更新: {global_config}")
    
    # 提示用户需要重启摄像头
    msg_box = QMessageBox()
    msg_box.setWindowIcon(get_message_box_icon())
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle("应用更改")
    msg_box.setText(f"分辨率已设置为 {new_resolution[0]}x{new_resolution[1]}\n\n需要重启摄像头以应用更改，是否立即重启？")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    reply = msg_box.exec()
    
    if reply == QMessageBox.StandardButton.Yes:
        logger.info("用户选择立即重启摄像头")
        
        # 停止当前摄像头和二维码扫描
        if hasattr(ui, 'camera_manager'):
            logger.info("正在停止当前摄像头...")
            ui.camera_manager.stop()
            
            # 停止二维码扫描线程
            if hasattr(ui, 'qr_scanner_thread'):
                logger.info("正在停止二维码扫描线程...")
                ui.qr_scanner_thread.stop()
            
            # 等待一下确保完全停止
            time.sleep(0.5)
            
            # 重新创建摄像头管理器
            logger.info(f"正在以新分辨率 {new_resolution} 重启摄像头...")
            ui.camera_manager = CameraManager(
                ir_label=ui.IR_cam,
                rgb_label=ui.RGB_cam,
                ir_camera_id=global_config["ir_camera_id"],
                rgb_camera_id=global_config["rgb_camera_id"],
                resolution=new_resolution,
                rate=global_config["rate"]
            )
            ui.camera_manager.start()
            logger.info("摄像头已重启")
            
            # 重新创建二维码扫描线程(指向新的camera_manager)
            logger.info("正在重新创建二维码扫描线程...")
            ui.qr_scanner_thread = QRCodeScannerThread(ui.camera_manager)
            ui.qr_scanner_thread.qrcode_detected.connect(lambda qr_data: handle_qrcode_detected(qr_data, ui))
            ui.qr_scanner_thread.start()
            logger.info("二维码扫描线程已重新启动")
            
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("成功")
            msg_box.setText(f"摄像头已成功切换到 {new_resolution[0]}x{new_resolution[1]} 分辨率")
            msg_box.exec()
        else:
            logger.warning("未找到摄像头管理器引用")
    else:
        logger.info("用户选择稍后重启摄像头")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText("分辨率设置已保存，将在下次启动时生效")
        msg_box.exec()


def handle_action_rate_triggered(ui):
    """
    处理 帧率设置 菜单点击事件
    
    Args:
        ui: UI对象
    """
    logger.info(">>> 帧率设置 菜单被点击")
    
    # 当前帧率
    current_rate = global_config["rate"]
    
    # 将帧率选项转换为字符串列表
    rate_options_str = [f"{rate} fps" for rate in rate_options]
    
    # 查找当前帧率在列表中的索引
    try:
        current_index = rate_options.index(current_rate)
    except ValueError:
        current_index = 0  # 默认选择第一个
    
    # 弹出选择对话框
    selected_option, ok = show_input_dialog_with_icon(
        None,
        "帧率设置",
        f"当前帧率: {current_rate} fps\n请选择新的帧率:",
        items=rate_options_str,
        current_index=current_index,
        editable=False,
        input_mode='item'
    )
    
    if not ok:
        logger.info("用户取消了帧率设置")
        return
    
    logger.info(f"用户选择的帧率选项: {selected_option}")
    
    # 解析选择的帧率（移除 " fps" 后缀）
    new_rate = int(selected_option.replace(" fps", ""))
    logger.info(f"解析帧率: {new_rate}")
    
    # 检查是否与当前帧率相同
    if new_rate == current_rate:
        logger.info("新帧率与当前帧率相同，无需更改")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText(f"当前已经是 {current_rate} fps")
        msg_box.exec()
        return
    
    # 更新全局配置
    global_config["rate"] = new_rate
    logger.info(f"全局配置已更新: {global_config}")
    
    # 提示用户需要重启摄像头
    msg_box = QMessageBox()
    msg_box.setWindowIcon(get_message_box_icon())
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle("应用更改")
    msg_box.setText(f"帧率已设置为 {new_rate} fps\n\n需要重启摄像头以应用更改，是否立即重启？")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    reply = msg_box.exec()
    
    if reply == QMessageBox.StandardButton.Yes:
        logger.info("用户选择立即重启摄像头")
        
        # 停止当前摄像头和二维码扫描
        if hasattr(ui, 'camera_manager'):
            logger.info("正在停止当前摄像头...")
            ui.camera_manager.stop()
            
            # 停止二维码扫描线程
            if hasattr(ui, 'qr_scanner_thread'):
                logger.info("正在停止二维码扫描线程...")
                ui.qr_scanner_thread.stop()
            
            # 等待一下确保完全停止
            time.sleep(0.5)
            
            # 重新创建摄像头管理器
            logger.info(f"正在以新帧率 {new_rate} fps 重启摄像头...")
            ui.camera_manager = CameraManager(
                ir_label=ui.IR_cam,
                rgb_label=ui.RGB_cam,
                ir_camera_id=global_config["ir_camera_id"],
                rgb_camera_id=global_config["rgb_camera_id"],
                resolution=global_config["custom_resolution"],
                rate=new_rate
            )
            ui.camera_manager.start()
            logger.info("摄像头已重启")
            
            # 重新创建二维码扫描线程(指向新的camera_manager)
            logger.info("正在重新创建二维码扫描线程...")
            ui.qr_scanner_thread = QRCodeScannerThread(ui.camera_manager)
            ui.qr_scanner_thread.qrcode_detected.connect(lambda qr_data: handle_qrcode_detected(qr_data, ui))
            ui.qr_scanner_thread.start()
            logger.info("二维码扫描线程已重新启动")
            
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("成功")
            msg_box.setText(f"摄像头已成功切换到 {new_rate} fps 帧率")
            msg_box.exec()
        else:
            logger.warning("未找到摄像头管理器引用")
    else:
        logger.info("用户选择稍后重启摄像头")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText("帧率设置已保存，将在下次启动时生效")
        msg_box.exec()


def handle_action_max_snapshots_triggered(ui):
    """
    处理 最大快照数量设置 菜单点击事件
    
    Args:
        ui: UI对象
    """
    logger.info(">>> 最大快照数量设置 菜单被点击")
    
    # 当前最大快照数量
    current_max = global_config["max_snapshots"]
    
    # 弹出输入对话框
    new_max, ok = show_input_dialog_with_icon(
        None,
        "最大快照数量设置",
        f"当前最大快照数量: {current_max}\n请输入新的最大快照数量:",
        input_mode='int',
        value=current_max,
        min_value=5,
        max_value=50,
        step=1
    )
    
    if not ok:
        logger.info("用户取消了最大快照数量设置")
        return
    
    logger.info(f"用户输入的最大快照数量: {new_max}")
    # 校验：必须为2的倍数（偶数）
    if isinstance(new_max, int) and new_max % 2 != 0:
        logger.warning("用户输入的最大快照数量不是偶数")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("无效输入")
        msg_box.setText("最大快照数量必须是2的倍数（偶数），请重新输入。")
        msg_box.exec()
        return
    
    # 检查是否与当前值相同
    if new_max == current_max:
        logger.info("新的最大快照数量与当前值相同，无需更改")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText(f"当前已经是 {current_max} 张")
        msg_box.exec()
        return
    
    # 更新全局配置
    global_config["max_snapshots"] = new_max
    logger.info(f"全局配置已更新: max_snapshots = {new_max}")
    
    # 更新 SnapshotManager 的 max_snapshots 属性
    if hasattr(ui, 'snapshot_manager'):
        old_max = ui.snapshot_manager.max_snapshots
        ui.snapshot_manager.max_snapshots = new_max
        logger.info(f"SnapshotManager 的 max_snapshots 已从 {old_max} 更新为 {new_max}")
        
        # 触发信号更新 SNAP_Button 显示
        current_count = ui.snapshot_manager.get_snapshot_count()
        ui.snapshot_manager.snapshot_count_changed.emit(current_count, new_max)
        logger.debug(f"已发出信号更新 SNAP_Button: {current_count}/{new_max}")
        
        # 检查当前快照数量是否超过新的最大值
        if current_count > new_max:
            logger.warning(f"当前快照数量 ({current_count}) 超过新的最大值 ({new_max})，将移除多余的快照")
            removed_count = 0
            # 从头部移除多余的快照，使用 remove_snapshot 方法确保正确处理删除逻辑
            while len(ui.snapshot_manager.snapshots) > new_max:
                # 使用 remove_snapshot(0) 而不是直接 pop，这样会正确处理已保存快照的删除
                ui.snapshot_manager.remove_snapshot(0)
                removed_count += 1
                logger.debug(f"已移除第 {removed_count} 张溢出快照")
            
            # 注意：remove_snapshot 已经调用了 update_thumbnail_display 和 emit 信号
            # 所以这里不需要再次调用
            
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("提示")
            msg_box.setText(f"最大快照数量已更新为 {new_max}\n已移除 {removed_count} 张多余的快照")
            msg_box.exec()
        else:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("成功")
            msg_box.setText(f"最大快照数量已更新为 {new_max}")
            msg_box.exec()
    else:
        logger.warning("未找到 SnapshotManager 引用，设置将在下次启动时生效")



def get_camera_names_windows():
    """
    获取Windows平台摄像头名称
    
    Returns:
        字典: {摄像头ID: 摄像头名称}
    """
    camera_names = {}
    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        device_list = graph.get_input_devices()
        for idx, name in enumerate(device_list):
            camera_names[idx] = name
        logger.debug(f"通过pygrabber获取到摄像头名称: {camera_names}")
    except ImportError:
        logger.debug("pygrabber未安装(Windows平台可选)")
    except Exception as e:
        logger.debug(f"获取Windows摄像头名称失败: {e}")
    return camera_names


def get_camera_names_linux():
    """
    获取Linux平台摄像头名称
    
    Returns:
        字典: {摄像头ID: 摄像头名称}
    """
    camera_names = {}
    try:
        import subprocess
        # 使用 v4l2-ctl 命令列出视频设备
        result = subprocess.run(
            ['v4l2-ctl', '--list-devices'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            current_name = None
            for line in lines:
                line = line.strip()
                if line and not line.startswith('/dev/video'):
                    # 设备名称行
                    current_name = line.rstrip(':')
                elif line.startswith('/dev/video'):
                    # 设备路径行
                    device_num = int(line.split('/dev/video')[1].split(':')[0])
                    if current_name:
                        camera_names[device_num] = current_name
            logger.debug(f"通过v4l2-ctl获取到摄像头名称: {camera_names}")
    except FileNotFoundError:
        logger.debug("v4l2-ctl未安装(Linux平台可选)")
    except Exception as e:
        logger.debug(f"获取Linux摄像头名称失败: {e}")
    return camera_names


def get_camera_names_macos():
    """
    获取macOS平台摄像头名称
    
    Returns:
        字典: {摄像头ID: 摄像头名称}
    """
    camera_names = {}
    try:
        import subprocess
        # 使用 system_profiler 命令获取摄像头信息
        result = subprocess.run(
            ['system_profiler', 'SPCameraDataType'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # 解析输出获取摄像头名称
            lines = result.stdout.strip().split('\n')
            camera_idx = 0
            for line in lines:
                line = line.strip()
                if 'Model ID' in line or line.endswith('Camera:'):
                    # 提取摄像头名称
                    name = line.split(':')[0].strip()
                    if name:
                        camera_names[camera_idx] = name
                        camera_idx += 1
            logger.debug(f"通过system_profiler获取到摄像头名称: {camera_names}")
    except FileNotFoundError:
        logger.debug("system_profiler未找到(macOS平台)")
    except Exception as e:
        logger.debug(f"获取macOS摄像头名称失败: {e}")
    return camera_names


def get_available_cameras(max_test=10):
    """
    检测系统中可用的摄像头及其名称(跨平台支持)
    
    注意: 此函数仅获取摄像头名称列表,不会打开摄像头设备
          (避免与正在运行的摄像头进程冲突)
    
    Args:
        max_test: 最多检测的摄像头数量(仅Linux/macOS使用)
        
    Returns:
        字典列表,每项包含 {'id': int, 'name': str}
    """
    
    available_cameras = []
    
    logger.info("正在扫描系统摄像头...")
    
    # 检测操作系统
    system = platform.system()
    logger.info(f"检测到操作系统: {system}")
    
    if system == 'Windows':
        # 获取摄像头名称（不打开设备）
        camera_names = get_camera_names_windows()
        
        if not camera_names:
            logger.warning("未检测到摄像头")
            return available_cameras
        
        logger.info(f"检测到的摄像头: {camera_names}")
        
        # 直接返回列表,不进行打开测试
        for idx, name in camera_names.items():
            camera_info = {
                'id': idx,
                'name': name
            }
            available_cameras.append(camera_info)
            logger.debug(f"摄像头 ID {idx}: {name}")
    
    elif system == 'Linux':
        # Linux: 使用v4l2工具获取摄像头名称
        camera_names = get_camera_names_linux()
        
        if not camera_names:
            logger.warning("未检测到摄像头")
            return available_cameras
        
        logger.info(f"检测到的摄像头: {camera_names}")
        
        for idx, name in camera_names.items():
            camera_info = {
                'id': idx,
                'name': name
            }
            available_cameras.append(camera_info)
            logger.debug(f"摄像头 ID {idx}: {name}")
                    
    elif system == 'Darwin':  # macOS
        # macOS: 使用system_profiler获取摄像头名称
        camera_names = get_camera_names_macos()
        
        if not camera_names:
            logger.warning("未检测到摄像头")
            return available_cameras
        
        logger.info(f"检测到的摄像头: {camera_names}")
        
        for idx, name in camera_names.items():
            camera_info = {
                'id': idx,
                'name': name
            }
            available_cameras.append(camera_info)
            logger.debug(f"摄像头 ID {idx}: {name}")
    else:
        logger.warning(f"未知操作系统: {system}")
    
    logger.info(f"共检测到 {len(available_cameras)} 个摄像头")
    return available_cameras


class CameraSelectionDialog(QDialog):
    """摄像头选择对话框"""
    
    def __init__(self, available_cameras, current_ir_id, current_rgb_id, parent=None):
        super().__init__(parent)
        self.available_cameras = available_cameras
        self.current_ir_id = current_ir_id
        self.current_rgb_id = current_rgb_id
        self.selected_ir_id = None
        self.selected_rgb_id = None
        
        # 设置窗口图标
        self.setWindowIcon(get_message_box_icon())
        
        self.init_ui()
    
    def init_ui(self):
        """初始化对话框UI"""
        self.setWindowTitle("摄像头配置")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # 重要提示信息
        warning_label = QLabel(
            "重要提示：请务必确保摄像头类型与选择框对应！\n"
            "• IR框内必须选择红外摄像头\n"
            "• RGB框内必须选择彩色摄像头\n"
            "否则会导致二维码扫描等功能无法正常工作！"
        )
        warning_label.setStyleSheet(
            "background-color: #fff3cd; "
            "border: 2px solid #ffc107; "
            "border-radius: 5px; "
            "padding: 10px; "
            "color: #856404; "
            "font-weight: bold; "
            "margin-bottom: 15px;"
        )
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        # IR 摄像头选择
        ir_group = QGroupBox("IR 红外摄像头（左预览框）")
        ir_layout = QVBoxLayout()
        
        # 添加说明文字
        ir_tip = QLabel("请选择红外(IR)摄像头（左预览框）")
        ir_layout.addWidget(ir_tip)
        
        ir_label = QLabel(f"当前: ID {self.current_ir_id}")
        ir_layout.addWidget(ir_label)
        
        self.ir_combo = QComboBox()
        for cam in self.available_cameras:
            display_text = f"ID {cam['id']}: {cam['name']}"
            self.ir_combo.addItem(display_text, cam['id'])
            if cam['id'] == self.current_ir_id:
                self.ir_combo.setCurrentIndex(self.ir_combo.count() - 1)
        ir_layout.addWidget(self.ir_combo)
        
        ir_group.setLayout(ir_layout)
        layout.addWidget(ir_group)
        
        # RGB 摄像头选择
        rgb_group = QGroupBox("RGB 彩色摄像头")
        rgb_layout = QVBoxLayout()
        
        # 添加说明文字
        rgb_tip = QLabel("请选择彩色(RGB)摄像头")
        rgb_layout.addWidget(rgb_tip)
        
        rgb_label = QLabel(f"当前: ID {self.current_rgb_id}")
        rgb_layout.addWidget(rgb_label)
        
        self.rgb_combo = QComboBox()
        for cam in self.available_cameras:
            display_text = f"ID {cam['id']}: {cam['name']}"
            self.rgb_combo.addItem(display_text, cam['id'])
            if cam['id'] == self.current_rgb_id:
                self.rgb_combo.setCurrentIndex(self.rgb_combo.count() - 1)
        rgb_layout.addWidget(self.rgb_combo)
        
        rgb_group.setLayout(rgb_layout)
        layout.addWidget(rgb_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept_selection)
        ok_button.setDefault(True)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def accept_selection(self):
        """确认选择"""
        self.selected_ir_id = self.ir_combo.currentData()
        self.selected_rgb_id = self.rgb_combo.currentData()
        
        # 检查是否选择了相同的摄像头
        if self.selected_ir_id == self.selected_rgb_id:
            QMessageBox.warning(
                self,
                "选择错误",
                "IR摄像头和RGB摄像头不能选择同一个设备!\n请重新选择。"
            )
            return
        
        # 获取选择的摄像头名称
        selected_ir_name = self.ir_combo.currentText()
        selected_rgb_name = self.rgb_combo.currentText()
        
        # 再次确认提醒
        reply = QMessageBox.question(
            self,
            "确认摄像头选择",
            f"请确认您的选择：\n\n"
            f"IR 红外摄像头: {selected_ir_name}\n"
            f"RGB 彩色摄像头: {selected_rgb_name}\n\n"
            f"请确保摄像头类型与名称匹配，否则可能导致功能异常！\n\n"
            f"确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()
        # 如果选择No，则留在对话框让用户重新选择
    
    def get_selected_cameras(self):
        """获取选择的摄像头ID"""
        return self.selected_ir_id, self.selected_rgb_id


def handle_action_camera_triggered(ui):
    """
    处理 摄像头设置 菜单点击事件
    
    Args:
        ui: UI对象
    """
    logger.info(">>> 摄像头设置 菜单被点击")
    
    # 检测可用摄像头(只读取名称,不打开设备)
    available_cameras = get_available_cameras()
    
    if len(available_cameras) < 2:
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("错误")
        msg_box.setText(f"系统检测到 {len(available_cameras)} 个摄像头，至少需要2个摄像头才能使用本系统")
        msg_box.exec()
        logger.warning(f"可用摄像头不足: {len(available_cameras)}")
        return
    
    # 当前配置
    current_ir_id = global_config["ir_camera_id"]
    current_rgb_id = global_config["rgb_camera_id"]
    
    # 显示摄像头选择对话框
    dialog = CameraSelectionDialog(available_cameras, current_ir_id, current_rgb_id)
    
    if dialog.exec() != QDialog.DialogCode.Accepted:
        logger.info("用户取消了摄像头设置")
        return
    
    # 获取用户选择
    new_ir_id, new_rgb_id = dialog.get_selected_cameras()
    logger.info(f"用户选择: IR摄像头ID={new_ir_id}, RGB摄像头ID={new_rgb_id}")
    
    # 检查是否与当前配置相同
    if new_ir_id == current_ir_id and new_rgb_id == current_rgb_id:
        logger.info("新摄像头配置与当前配置相同，无需更改")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText(f"当前已经是 IR=ID {current_ir_id}, RGB=ID {current_rgb_id}")
        msg_box.exec()
        return
    
    # 更新全局配置
    global_config["ir_camera_id"] = new_ir_id
    global_config["rgb_camera_id"] = new_rgb_id
    logger.info(f"全局配置已更新: IR=ID {new_ir_id}, RGB=ID {new_rgb_id}")
    
    # 提示用户需要重启摄像头
    msg_box = QMessageBox()
    msg_box.setWindowIcon(get_message_box_icon())
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle("应用更改")
    msg_box.setText(f"摄像头已设置为:\nIR摄像头: ID {new_ir_id}\nRGB摄像头: ID {new_rgb_id}\n\n需要重启摄像头以应用更改，是否立即重启？")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    reply = msg_box.exec()
    
    if reply == QMessageBox.StandardButton.Yes:
        logger.info("用户选择立即重启摄像头")
        
        # 停止当前摄像头和二维码扫描
        if hasattr(ui, 'camera_manager'):
            logger.info("正在停止当前摄像头...")
            ui.camera_manager.stop()
            
            # 停止二维码扫描线程
            if hasattr(ui, 'qr_scanner_thread'):
                logger.info("正在停止二维码扫描线程...")
                ui.qr_scanner_thread.stop()
            
            # 等待一下确保完全停止
            time.sleep(0.5)
            
            # 重新创建摄像头管理器
            logger.info(f"正在以新摄像头配置重启: IR=ID {new_ir_id}, RGB=ID {new_rgb_id}")
            ui.camera_manager = CameraManager(
                ir_label=ui.IR_cam,
                rgb_label=ui.RGB_cam,
                ir_camera_id=new_ir_id,
                rgb_camera_id=new_rgb_id,
                resolution=global_config["custom_resolution"],
                rate=global_config["rate"]
            )
            ui.camera_manager.start()
            logger.info("摄像头已重启")
            
            # 重新创建二维码扫描线程(指向新的camera_manager)
            logger.info("正在重新创建二维码扫描线程...")
            ui.qr_scanner_thread = QRCodeScannerThread(ui.camera_manager)
            ui.qr_scanner_thread.qrcode_detected.connect(lambda qr_data: handle_qrcode_detected(qr_data, ui))
            ui.qr_scanner_thread.start()
            logger.info("二维码扫描线程已重新启动")
            
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("成功")
            msg_box.setText(f"摄像头已成功切换:\nIR摄像头: ID {new_ir_id}\nRGB摄像头: ID {new_rgb_id}")
            msg_box.exec()
        else:
            logger.warning("未找到摄像头管理器引用")
    else:
        logger.info("用户选择稍后重启摄像头")
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText("摄像头设置已保存，将在下次启动时生效")
        msg_box.exec()


def main():
    """主函数入口"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Plampture 双目视觉掌纹掌静脉采集系统')
    parser.add_argument('--project-id', type=str, help='项目ID')
    args = parser.parse_args()
    
    # 获取应用程序目录（兼容exe）
    app_dir = get_app_dir()
    
    # 初始化项目配置
    if args.project_id:
        project_id = args.project_id
        workspace_dir = os.path.join(app_dir, "workspace")
        project_dir = os.path.join(workspace_dir, project_id)
        
        # 验证项目目录
        if not os.path.exists(project_dir):
            logger.error(f"项目目录不存在: {project_dir}")
            print(f"错误: 项目目录不存在: {project_dir}")
            
            # 如果是exe环境，显示错误对话框
            if getattr(sys, 'frozen', False):
                app = QApplication(sys.argv)
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setWindowTitle("错误")
                msg_box.setText(f"项目目录不存在:\n{project_dir}\n\n请通过 setup.exe 启动项目。")
                msg_box.exec()
            
            sys.exit(1)
        
        # 读取项目配置
        project_conf_file = os.path.join(project_dir, f"{project_id}_conf.json")
        try:
            with open(project_conf_file, 'r', encoding='utf-8') as f:
                project_conf = json.load(f)
            
            global_project_config["project_id"] = project_conf["id"]
            global_project_config["project_name"] = project_conf["name"]
            global_project_config["project_dir"] = project_dir
            
            logger.info(f"已加载项目: {project_conf['name']} (ID: {project_id})")
            logger.info(f"项目目录: {project_dir}")
            
        except Exception as e:
            logger.error(f"读取项目配置失败: {e}")
            print(f"错误: 读取项目配置失败: {e}")
            
            # 如果是exe环境，显示错误对话框
            if getattr(sys, 'frozen', False):
                app = QApplication(sys.argv)
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setWindowTitle("错误")
                msg_box.setText(f"读取项目配置失败:\n{e}\n\n请通过 setup.exe 启动项目。")
                msg_box.exec()
            
            sys.exit(1)
    else:
        # 没有指定项目ID
        logger.warning("未指定项目ID")
        
        # 如果是exe环境，提示用户通过setup启动
        if getattr(sys, 'frozen', False):
            app = QApplication(sys.argv)
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("请通过 setup.exe 选择项目后启动。\n\n不支持直接双击 main.exe 运行。")
            msg_box.exec()
            sys.exit(0)
        
        # 开发环境使用默认配置
        logger.info("开发环境: 使用默认配置")
        global_project_config["project_id"] = "default"
        global_project_config["project_name"] = "测试环境"
        global_project_config["project_dir"] = app_dir
    
    logger.info("=" * 60)
    logger.info("=== Plampture 双目视觉采集系统启动 ===")
    logger.info(f"=== 当前项目: {global_project_config['project_name']} ===")
    logger.info("=" * 60)
    
    # 创建应用程序
    logger.info("正在创建Qt应用程序...")
    app = QApplication(sys.argv)
    
    # 创建主窗口
    logger.info("正在创建主窗口...")
    MainWindow = QMainWindow()
    
    # 设置 UI
    logger.info("正在初始化UI界面...")
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    
    # 应用动态布局设置
    logger.info("正在应用动态布局设置...")
    ui = setup_dynamic_layout(ui)
    
    # 设置窗口标题和图标
    window_title = f"Plampture - {global_project_config['project_name']}"
    MainWindow.setWindowTitle(window_title)
    logger.info(f"窗口标题已设置: {window_title}")
    
    # 设置窗口图标
    icon_path = os.path.join("icon", "Plampture.ico")
    if os.path.exists(icon_path):
        MainWindow.setWindowIcon(QIcon(icon_path))
        logger.info(f"窗口图标已加载: {icon_path}")
    else:
        logger.warning(f"图标文件未找到: {icon_path}")
    
    # 设置菜单图标
    setting_icon_path = os.path.join("icon", "setting.ico")
    if os.path.exists(setting_icon_path):
        ui.menusetting.setIcon(QIcon(setting_icon_path))
        logger.info(f"设置菜单图标已加载: {setting_icon_path}")
    else:
        logger.warning(f"设置菜单图标文件未找到: {setting_icon_path}")
    
    # 配置状态栏日志处理器
    statusbar_handler = StatusBarHandler(ui.statusbar)
    logger.add(
        statusbar_handler.write,
        format="{time:HH:mm:ss} | {level} | {message}",
        level="INFO",
        colorize=False
    )
    logger.info("状态栏日志处理器已配置")
    
    # 创建摄像头管理器（多进程版本）
    # 参数：IR摄像头ID=1, RGB摄像头ID=0
    logger.info("正在创建摄像头管理器...")
    logger.info(f"摄像头配置: IR相机ID={global_config['ir_camera_id']}, RGB相机ID={global_config['rgb_camera_id']}")
    camera_manager = CameraManager(
        ir_label=ui.IR_cam,
        rgb_label=ui.RGB_cam,
        ir_camera_id=global_config["ir_camera_id"],
        rgb_camera_id=global_config["rgb_camera_id"],
        resolution=global_config["custom_resolution"],
        rate=global_config["rate"],
        use_circumscribed_roi=USE_CIRCUMSCRIBED_ROI
    )
    
    # 启动摄像头
    logger.info("正在启动双摄像头...")
    camera_manager.start()
    logger.info("摄像头管理器已启动")
    
    # 保存摄像头管理器引用
    ui.camera_manager = camera_manager
    logger.debug("摄像头管理器引用已保存到UI对象")

    # --------------------------------------------------
    # 配置滑块以使用统一的 0-100 百分比范围
    # 在映射函数中将百分比转换为摄像头实际范围
    # --------------------------------------------------
    try:
        # 统一使用 0-100 百分比范围,用户友好且跨平台一致
        # 映射函数会根据平台将百分比转换为实际的摄像头参数值
        bc_min, bc_max = 0, 100  # brightness/contrast 百分比
        exposure_min, exposure_max = 0, 100  # exposure 百分比


        def _set_range_and_center(slider, lo, hi):
            try:
                slider.setMinimum(int(lo))
                slider.setMaximum(int(hi))
                slider.setValue((int(lo) + int(hi)) // 2)
            except Exception:
                pass

        # 全局滑块
        try:
            if hasattr(ui, 'bright_ctrl_horizontalSlider'):
                _set_range_and_center(ui.bright_ctrl_horizontalSlider, bc_min, bc_max)
            if hasattr(ui, 'contrast_ctrl_horizontalSlider'):
                _set_range_and_center(ui.contrast_ctrl_horizontalSlider, bc_min, bc_max)
            if hasattr(ui, 'exposure_ctrl_horizontalSlider'):
                _set_range_and_center(ui.exposure_ctrl_horizontalSlider, exposure_min, exposure_max)
        except Exception:
            pass

        # per-camera 滑块（ir_ / rgb_ 前缀变体）
        for prefix in ('ir_', 'rgb_', 'IR_', 'RGB_'):
            try:
                # brightness
                name = f"{prefix}bright_ctrl_horizontalSlider"
                if hasattr(ui, name):
                    _set_range_and_center(getattr(ui, name), bc_min, bc_max)
                # contrast
                name = f"{prefix}contrast_ctrl_horizontalSlider"
                if hasattr(ui, name):
                    _set_range_and_center(getattr(ui, name), bc_min, bc_max)
                # exposure
                name = f"{prefix}exposure_ctrl_horizontalSlider"
                if hasattr(ui, name):
                    _set_range_and_center(getattr(ui, name), exposure_min, exposure_max)
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"初始化滑块范围失败: {e}")

    # 绑定亮度/对比度滑块到摄像头属性（同时应用到 IR 和 RGB）
    try:
        # 使用去抖（debounce）定时器，避免频繁发送大量命令导致 IPC 或摄像头阻塞
        from PySide6.QtCore import QTimer

        def _map_value_for_prop(prop, uival):
            """把 UI 0..100 的值映射到摄像头属性的合理区间。
            
            注意：不同摄像头的参数范围不同:
            - 亮度: 通常 0-64 (某些摄像头)
            - 对比度: 通常 0-100
            - 曝光: 根据平台映射
            """
            import platform as _plat
            system = _plat.system()
            try:
                v = int(uival)
            except Exception:
                v = 0
            
            # brightness: 映射到 0-64 (实测有效范围)
            if prop == cv2.CAP_PROP_BRIGHTNESS:
                return int(round(v * 64.0 / 100.0))  # 0-100% -> 0-64
            
            # contrast: 大多数驱动使用 0-100,直接返回
            if prop == cv2.CAP_PROP_CONTRAST:
                return v  # 直接使用 0-100,不映射
            
            # exposure: 根据平台映射到不同范围
            if prop == cv2.CAP_PROP_EXPOSURE:
                if system == 'Linux':
                    # map 0..100 -> 1..1000 (exposure_absolute typical)
                    return int(round(1 + v * 999.0 / 100.0))
                elif system == 'Windows':
                    # Windows Media Foundation often uses negative logs; map 0..100 -> -13..-1
                    return int(round(-13 + v * 12.0 / 100.0))
                else:
                    # macOS / unknown: use a moderate positive range
                    return int(round(1 + v * 499.0 / 100.0))
            
            # default fallback: return raw value
            return v

        # Brightness debounce
        if hasattr(ui, 'bright_ctrl_horizontalSlider'):
            ui._bright_timer = QTimer(MainWindow)
            ui._bright_timer.setSingleShot(True)
            ui._bright_timer.setInterval(120)
            def _apply_brightness():
                try:
                        uival = ui.bright_ctrl_horizontalSlider.value()
                        mapped = int(uival)
                        logger.debug(f"Applying global brightness -> ui={uival} use_raw={mapped} camera_manager_exists={hasattr(ui, 'camera_manager')}")
                        ui.camera_manager.set_camera_property('both', cv2.CAP_PROP_BRIGHTNESS, mapped)
                except Exception as e:
                    logger.debug(f"设置亮度失败: {e}")
            ui._bright_timer.timeout.connect(_apply_brightness)
            ui.bright_ctrl_horizontalSlider.valueChanged.connect(lambda v: ui._bright_timer.start())
            # apply initial centered value
            try:
                ui._bright_timer.start()
            except Exception:
                pass

        # Contrast debounce
        if hasattr(ui, 'contrast_ctrl_horizontalSlider'):
            ui._contrast_timer = QTimer(MainWindow)
            ui._contrast_timer.setSingleShot(True)
            ui._contrast_timer.setInterval(120)
            def _apply_contrast():
                try:
                    uival = ui.contrast_ctrl_horizontalSlider.value()
                    mapped = int(uival)
                    logger.debug(f"Applying global contrast -> ui={uival} use_raw={mapped} camera_manager_exists={hasattr(ui, 'camera_manager')}")
                    ui.camera_manager.set_camera_property('both', cv2.CAP_PROP_CONTRAST, mapped)
                except Exception as e:
                    logger.debug(f"设置对比度失败: {e}")
            ui._contrast_timer.timeout.connect(_apply_contrast)
            ui.contrast_ctrl_horizontalSlider.valueChanged.connect(lambda v: ui._contrast_timer.start())
            try:
                ui._contrast_timer.start()
            except Exception:
                pass
        # 曝光滑块绑定：先尝试关闭自动曝光，再设置曝光值
        if hasattr(ui, 'exposure_ctrl_horizontalSlider'):
            ui._exposure_timer = QTimer(MainWindow)
            ui._exposure_timer.setSingleShot(True)
            ui._exposure_timer.setInterval(160)
            def _apply_exposure():
                try:
                    uival = ui.exposure_ctrl_horizontalSlider.value()
                    mapped = int(uival)
                    # use CameraManager.set_manual_exposure which sends a safe sequence to child process
                    logger.debug(f"Applying global exposure -> ui={uival} use_raw={mapped} camera_manager_exists={hasattr(ui, 'camera_manager')}")
                    ui.camera_manager.set_manual_exposure('both', mapped)
                except Exception as e:
                    logger.debug(f"设置曝光失败: {e}")
            ui._exposure_timer.timeout.connect(_apply_exposure)
            ui.exposure_ctrl_horizontalSlider.valueChanged.connect(lambda v: ui._exposure_timer.start())
            try:
                ui._exposure_timer.start()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"绑定亮度/对比度滑块失败: {e}")
    
    # ======== 为 IR / RGB 单独滑块绑定控制（如果存在） ========
    try:
        from PySide6.QtCore import QTimer

        # Helper to create debounce timer and wire slider
        def _bind_camera_slider(prefix, prop_const, is_exposure=False, interval=120):
            # Do not access prop_const.__name__ (prop_const is an int constant).
            # Instead, build candidate slider names from explicit base names below.
            # We'll try common names.
            possible_names = []
            # support prefix variants (lowercase, UPPERCASE, Capitalized)
            prefix_variants = [prefix, prefix.upper(), prefix.capitalize()]
            if is_exposure:
                base_names = ["exposure_ctrl_horizontalSlider", "exposure_ctrl_slider"]
            else:
                if prop_const == cv2.CAP_PROP_BRIGHTNESS:
                    base_names = ["bright_ctrl_horizontalSlider", "brightness_ctrl_horizontalSlider"]
                elif prop_const == cv2.CAP_PROP_CONTRAST:
                    base_names = ["contrast_ctrl_horizontalSlider"]
                else:
                    base_names = []
            # combine prefix variants with base names
            for pfx in prefix_variants:
                for b in base_names:
                    possible_names.append(f"{pfx}{b}")

            slider = None
            for name in possible_names:
                if hasattr(ui, name):
                    slider = getattr(ui, name)
                    break
            if slider is None:
                return

            timer_attr = f"_{prefix}timer_{prop_const}" if not is_exposure else f"_{prefix}timer_exposure"
            try:
                timer = QTimer(MainWindow)
                timer.setSingleShot(True)
                timer.setInterval(interval)
                def _on_timeout():
                    try:
                        uival = slider.value()  # UI 值: 0-100 百分比
                        
                        # 将 UI 百分比值映射到摄像头实际范围
                        if is_exposure:
                            # 复用全局映射函数处理曝光
                            mapped = _map_value_for_prop(cv2.CAP_PROP_EXPOSURE, uival)
                        else:
                            # brightness/contrast: 复用全局映射函数
                            mapped = _map_value_for_prop(prop_const, uival)
                        
                        which = prefix[:-1] if prefix.endswith('_') else prefix
                        logger.debug(f"Per-cam apply -> which={which} prop={prop_const} ui={uival}% mapped={mapped} slider_obj={getattr(slider, 'objectName', lambda: None)()} camera_manager_exists={hasattr(ui, 'camera_manager')}")
                        
                        if is_exposure:
                            ui.camera_manager.set_manual_exposure(which, mapped)
                        else:
                            ui.camera_manager.set_camera_property(which, prop_const, mapped)
                    except Exception as e:
                        logger.debug(f"设置 {prefix} {prop_const} 失败: {e}")
                timer.timeout.connect(_on_timeout)
                setattr(ui, timer_attr, timer)
                # Wire slider to start timer on change
                try:
                    slider.valueChanged.connect(lambda v, t=getattr(ui, timer_attr): t.start())
                except Exception:
                    pass
                # Start once to apply initial centered value
                try:
                    getattr(ui, timer_attr).start()
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"创建 {prefix} 定时器失败: {e}")

        # Bind IR sliders
        if True:
            _bind_camera_slider('ir_', cv2.CAP_PROP_BRIGHTNESS, is_exposure=False, interval=120)
            _bind_camera_slider('ir_', cv2.CAP_PROP_CONTRAST, is_exposure=False, interval=120)
            _bind_camera_slider('ir_', cv2.CAP_PROP_EXPOSURE, is_exposure=True, interval=160)

        # Bind RGB sliders
        if True:
            _bind_camera_slider('rgb_', cv2.CAP_PROP_BRIGHTNESS, is_exposure=False, interval=120)
            _bind_camera_slider('rgb_', cv2.CAP_PROP_CONTRAST, is_exposure=False, interval=120)
            _bind_camera_slider('rgb_', cv2.CAP_PROP_EXPOSURE, is_exposure=True, interval=160)
    except Exception as e:
        logger.warning(f"绑定 per-camera 滑块失败: {e}")

    # 加载并应用上次保存的摄像头设置
    load_camera_settings(ui)
    
    # 创建快照管理器
    logger.info("正在创建快照管理器...")
    snapshot_manager = SnapshotManager(
        max_snapshots=global_config["max_snapshots"],
        thumbnail_list_widget=ui.thumbnail_listWidget,
        project_dir=global_project_config.get("project_dir")
    )
    ui.snapshot_manager = snapshot_manager
    logger.info(f"快照管理器已创建 (最大快照数: {global_config['max_snapshots']})")
    
    # 连接快照数量变化信号到 SNAP_Button 更新槽函数
    snapshot_manager.snapshot_count_changed.connect(lambda count, max_count: on_snapshot_count_changed(count, max_count, ui))
    logger.debug("快照数量变化信号已连接到SNAP_Button更新槽")
    
    # 创建并启动二维码扫描线程
    logger.info("正在创建二维码扫描线程...")
    qr_scanner_thread = QRCodeScannerThread(camera_manager)
    
    # 连接二维码检测信号到处理函数 (使用 lambda 传递 ui 参数)
    qr_scanner_thread.qrcode_detected.connect(lambda qr_data: handle_qrcode_detected(qr_data, ui))
    logger.debug("二维码检测信号已连接到处理函数")
    
    # 启动扫描线程
    qr_scanner_thread.start()
    logger.info("二维码扫描线程已启动")
    
    # 保存线程引用
    ui.qr_scanner_thread = qr_scanner_thread
    logger.debug("二维码扫描线程引用已保存到UI对象")
    
    # 连接按钮点击事件
    logger.info("正在绑定按钮事件...")
    ui.QR_Button.clicked.connect(lambda: handle_qr_button_clicked(ui))
    ui.SNAP_Button.clicked.connect(lambda: handle_snap_button_clicked(ui))
    ui.NEXT_Button.clicked.connect(lambda: handle_next_button_clicked(ui))
    logger.info("按钮事件绑定完成: QR_Button, SNAP_Button, NEXT_Button")

    # 添加快捷键 Ctrl+S 触发 SNAP_Button

    shortcut_snap = QShortcut(QKeySequence("Ctrl+S"), MainWindow)
    shortcut_snap.activated.connect(lambda: ui.SNAP_Button.click())
    logger.info("已绑定 Ctrl+S 快捷键到 SNAP_Button")
    
    # 初始化 SNAP_Button 显示
    update_snap_button_text(ui)
    logger.debug("SNAP_Button 显示已初始化")
    
    # 连接菜单动作事件
    logger.info("正在绑定菜单事件...")
    ui.action_resolution.triggered.connect(lambda: handle_action_resolution_triggered(ui))
    ui.action_rate.triggered.connect(lambda: handle_action_rate_triggered(ui))
    ui.action_camera.triggered.connect(lambda: handle_action_camera_triggered(ui))
    ui.action_max_snapshots.triggered.connect(lambda: handle_action_max_snapshots_triggered(ui))
    logger.info("菜单事件绑定完成: action_resolution, action_rate, action_camera, action_max_snapshots")
    
    # 初始化 id_label 显示
    ui.id_label.setText("身份ID: 未检测到二维码")
    logger.debug("ID标签已初始化为初始提示")
    
    # 初始化 capture_timestamp_label 显示
    ui.capture_timestamp_label.setText("拍摄时间: ")
    logger.debug("拍摄时间标签已初始化")
    
    # 设置窗口关闭事件处理
    # 设置窗口关闭事件处理
    MainWindow.closeEvent = lambda event: handle_window_close(event, qr_scanner_thread, camera_manager, snapshot_manager, ui)
    logger.debug("窗口关闭事件处理已设置")
    
    # 窗口最大化显示
    logger.info("正在显示主窗口（最大化）...")
    MainWindow.showMaximized()
    
    logger.info("=" * 60)
    logger.info("=== 系统初始化完成，进入运行状态 ===")
    logger.info("=" * 60)
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    # Windows 平台需要设置启动方法
    logger.info("设置多进程启动方法为 'spawn'")
    multiprocessing.set_start_method('spawn', force=True)
    multiprocessing.freeze_support()
    logger.info("多进程支持已启用")
    
    try:
        main()
    except Exception as e:
        logger.exception(f"程序运行出现异常: {e}")
        sys.exit(1)
