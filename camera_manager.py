# -*- coding: utf-8 -*-
"""
摄像头管理模块
使用 OpenCV 获取双路摄像头信号并显示在 QLabel 上
使用 multiprocessing 在独立进程中采集图像
"""

import cv2
import numpy as np
import threading
from multiprocessing import Process, Queue, Event
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from loguru import logger

# 可选：导入 ROI Worker
try:
    from plam_ROI_worker import PalmROIWorker
    HAS_ROI_WORKER = True
except Exception:
    PalmROIWorker = None
    HAS_ROI_WORKER = False


def camera_capture_process(camera_id, frame_queue, stop_event, width=1920, height=1080, rate=30, control_queue=None):
    """
    独立进程中运行的摄像头捕获函数
    
    Args:
        camera_id: 摄像头设备ID
        frame_queue: 用于传递图像帧的队列
        stop_event: 停止信号事件
        width: 图像宽度
        height: 图像高度
        rate: 帧率，单位fps
    """
    import sys
    import platform
    import time
    sys.stdout = sys.__stdout__  # 确保 print 输出可见
    
    # 根据操作系统选择合适的后端
    system = platform.system()
    
    camera = None
    backend_name = "未知"
    
    # Windows 平台尝试多个后端
    if system == 'Windows':
        # 尝试1: 不指定后端（自动选择）
        camera = cv2.VideoCapture(camera_id)
        backend_name = "AUTO"
        
        if not camera.isOpened():
            # 尝试2: MSMF (Media Foundation - Windows 推荐)
            camera.release()
            time.sleep(0.2)
            camera = cv2.VideoCapture(camera_id, cv2.CAP_MSMF)
            backend_name = "MSMF"
            
        if not camera.isOpened():
            # 尝试3: DSHOW (DirectShow - 较旧的接口)
            camera.release()
            time.sleep(0.2)
            camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            backend_name = "DSHOW"
    
    # Linux 平台
    elif system == 'Linux':
        camera = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
        backend_name = "V4L2"
    
    # macOS 平台
    elif system == 'Darwin':
        camera = cv2.VideoCapture(camera_id, cv2.CAP_AVFOUNDATION)
        backend_name = "AVFoundation"
    
    # 其他平台
    else:
        camera = cv2.VideoCapture(camera_id, cv2.CAP_ANY)
        backend_name = "ANY"
    
    if not camera.isOpened():
        print(f"进程中无法打开摄像头 {camera_id} (尝试的后端: {backend_name})", flush=True)
        return
    
    # 设置摄像头参数
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    camera.set(cv2.CAP_PROP_FPS, rate)
    
    # 验证实际参数
    actual_width = camera.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = camera.get(cv2.CAP_PROP_FPS)
    
    print(f"进程中成功打开摄像头 {camera_id} (后端: {backend_name})", flush=True)
    print(f"  设置分辨率: {width}x{height}, 实际: {int(actual_width)}x{int(actual_height)}", flush=True)
    print(f"  设置帧率: {rate} fps, 实际: {actual_fps} fps", flush=True)
    
    try:
        while not stop_event.is_set():
            # 处理控制命令（非阻塞）
            try:
                if control_queue is not None:
                    while not control_queue.empty():
                        cmd = control_queue.get_nowait()
                        # 支持单个 set 命令和 sequence 命令
                        try:
                            if isinstance(cmd, dict):
                                if cmd.get('action') == 'set':
                                    prop = cmd.get('prop')
                                    val = cmd.get('value')
                                    try:
                                        print(f"[child] set prop={prop} val={val}", flush=True)
                                    except Exception:
                                        pass
                                    try:
                                        camera.set(prop, float(val))
                                    except Exception:
                                        # 忽略设置错误，继续处理下一个命令
                                        pass
                                    try:
                                        # 读取回显，观察驱动实际接受的值（用于调试单位/范围问题）
                                        actual = camera.get(prop)
                                        print(f"[child] after_set prop={prop} requested={val} actual={actual}", flush=True)
                                    except Exception:
                                        pass

                                elif cmd.get('action') == 'sequence':
                                    seq = cmd.get('seq', [])
                                    import time as _time
                                    for item in seq:
                                        try:
                                            prop = item.get('prop')
                                            val = item.get('value')
                                            try:
                                                print(f"[child] seq set prop={prop} val={val}", flush=True)
                                            except Exception:
                                                pass
                                            try:
                                                camera.set(prop, float(val))
                                            except Exception:
                                                pass
                                            try:
                                                actual = camera.get(prop)
                                                print(f"[child] after_seq_set prop={prop} requested={val} actual={actual}", flush=True)
                                            except Exception:
                                                pass
                                            # 在连续设置间短暂等待，给驱动缓冲时间
                                            _time.sleep(0.02)
                                        except Exception:
                                            pass
                        except Exception:
                            pass
            except Exception:
                pass

            ret, frame = camera.read()
            if ret:
                # 将 numpy 数组转换为字节串，以便跨进程传输
                frame_bytes = frame.tobytes()
                frame_shape = frame.shape
                frame_dtype = str(frame.dtype)
                # 将图像信息打包，包含采集时间戳（子进程时间，便于主进程配对）
                import time as _time
                frame_ts = _time.time()
                frame_data = {
                    'bytes': frame_bytes,
                    'shape': frame_shape,
                    'dtype': frame_dtype,
                    'timestamp': frame_ts,
                }

                # 将图像帧放入队列，如果队列满了则丢弃旧帧
                if not frame_queue.full():
                    frame_queue.put(frame_data)
                else:
                    # 清空队列中的旧帧，只保留最新的
                    try:
                        frame_queue.get_nowait()
                    except:
                        pass
                    frame_queue.put(frame_data)
            else:
                print(f"摄像头 {camera_id} 读取失败", flush=True)
                break
    except Exception as e:
        print(f"摄像头 {camera_id} 进程异常: {e}", flush=True)
    finally:
        camera.release()
        print(f"摄像头 {camera_id} 进程已关闭", flush=True)


class CameraManager:
    """双路摄像头管理器（多进程版本）"""
    
    def __init__(self, ir_label, rgb_label, ir_camera_id=1, rgb_camera_id=0, resolution=(1920, 1080), rate=30, use_circumscribed_roi=False):
        """
        初始化摄像头管理器
        
        Args:
            ir_label: 显示 IR 图像的 QLabel
            rgb_label: 显示 RGB 图像的 QLabel
            ir_camera_id: IR 摄像头 ID
            rgb_camera_id: RGB 摄像头 ID
            resolution: 分辨率 (width, height)
            rate: 帧率
            use_circumscribed_roi: 是否使用外接矩形 ROI
        """
        self.ir_label = ir_label
        self.rgb_label = rgb_label
        self.ir_camera_id = ir_camera_id
        self.rgb_camera_id = rgb_camera_id
        self.resolution = resolution
        self.rate = rate
        self.use_circumscribed_roi = use_circumscribed_roi
        
        # 队列用于跨进程通信
        self.ir_queue = Queue(maxsize=2)
        self.rgb_queue = Queue(maxsize=2)
        
        # 控制事件
        self.stop_event = Event()
        
        # 进程引用
        self.ir_process = None
        self.rgb_process = None
        
        # 定时器用于更新 UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        
        # 状态标志
        self.is_running = False
        
        # 缓存最新的帧用于配对
        self.latest_ir = None  # (frame, timestamp)
        self.latest_rgb = None # (frame, timestamp)
        self.pair_threshold = 0.05  # 配对时间阈值（秒）
        
        # 存储最后一次配对成功的帧，供快照使用
        self.last_paired = None # (ir_frame, rgb_frame, timestamp)
        
        # 摄像头控制命令队列 (camera_id -> queue)
        self.control_queues = {}
        self.ir_control_queue = None
        self.rgb_control_queue = None
        
        # ROI Worker
        self.roi_worker = None
        self._latest_detection = None
        self._detection_lock = threading.Lock()

    def start(self):
        """启动摄像头进程和更新定时器"""
        if self.is_running:
            return

        self.stop_event.clear()
        
        # 在 Label 上显示启动提示
        self.ir_label.setText(f"IR摄像头正在启动中...\n摄像头ID: {self.ir_camera_id}\n请稍候...")
        self.ir_label.setStyleSheet("background-color: black; color: white; font-size: 16px; qproperty-alignment: AlignCenter;")
        
        self.rgb_label.setText(f"RGB摄像头正在启动中...\n摄像头ID: {self.rgb_camera_id}\n请稍候...")
        self.rgb_label.setStyleSheet("background-color: black; color: white; font-size: 16px; qproperty-alignment: AlignCenter;")
        
        # 创建控制队列
        self.ir_control_queue = Queue()
        self.rgb_control_queue = Queue()
        self.control_queues[self.ir_camera_id] = self.ir_control_queue
        self.control_queues[self.rgb_camera_id] = self.rgb_control_queue

        # 启动 IR 摄像头进程
        self.ir_process = Process(
            target=camera_capture_process,
            args=(self.ir_camera_id, self.ir_queue, self.stop_event, 
                  self.resolution[0], self.resolution[1], self.rate, self.ir_control_queue)
        )
        self.ir_process.start()
        
        # 更新 IR Label 显示进程 ID
        self.ir_label.setText(
            f"IR摄像头已启动\n"
            f"摄像头ID: {self.ir_camera_id}\n"
            f"进程PID: {self.ir_process.pid}\n"
            f"正在等待图像..."
        )

        # 启动 RGB 摄像头进程
        self.rgb_process = Process(
            target=camera_capture_process,
            args=(self.rgb_camera_id, self.rgb_queue, self.stop_event, 
                  self.resolution[0], self.resolution[1], self.rate, self.rgb_control_queue)
        )
        self.rgb_process.start()
        
        # 更新 RGB Label 显示进程 ID
        self.rgb_label.setText(
            f"RGB摄像头已启动\n"
            f"摄像头ID: {self.rgb_camera_id}\n"
            f"进程PID: {self.rgb_process.pid}\n"
            f"正在等待图像..."
        )

        # 启动 ROI Worker (如果可用)
        if HAS_ROI_WORKER:
            try:
                self.roi_worker = PalmROIWorker(
                    max_num_hands=1,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                    process_every_n=1,
                    use_circumscribed_roi=self.use_circumscribed_roi  # 使用传入的参数
                )
                self.roi_worker.detection.connect(self._on_detection_result)
                self.roi_worker.start()
            except Exception as e:
                print(f"启动 ROI Worker 失败: {e}")
                self.roi_worker = None

        self.timer.start(30)  # 30ms 更新一次 UI (~33 FPS)
        self.is_running = True

    def stop(self):
        """停止摄像头采集进程"""
        self.is_running = False
        self.timer.stop()
        
        # 发送停止信号
        self.stop_event.set()
        
        # 等待进程结束
        if self.ir_process and self.ir_process.is_alive():
            self.ir_process.join(timeout=2)
            if self.ir_process.is_alive():
                self.ir_process.terminate()
            print("IR 摄像头进程已停止")
        
        if self.rgb_process and self.rgb_process.is_alive():
            self.rgb_process.join(timeout=2)
            if self.rgb_process.is_alive():
                self.rgb_process.terminate()
            print("RGB 摄像头进程已停止")
        
        # 清空队列
        while not self.ir_queue.empty():
            try:
                self.ir_queue.get_nowait()
            except:
                break
        
        while not self.rgb_queue.empty():
            try:
                self.rgb_queue.get_nowait()
            except:
                break
        
        # 清空显示（检查 QLabel 是否还存在）
        try:
            if self.ir_label and hasattr(self.ir_label, 'clear'):
                self.ir_label.clear()
        except RuntimeError:
            pass  # QLabel 已被删除，忽略
        
        try:
            if self.rgb_label and hasattr(self.rgb_label, 'clear'):
                self.rgb_label.clear()
        except RuntimeError:
            pass  # QLabel 已被删除，忽略
        
        # 停止 ROI Worker
        if self.roi_worker is not None:
            try:
                self.roi_worker.stop()
                self.roi_worker = None
                print("ROI Worker 已停止")
            except Exception as e:
                print(f"停止 ROI Worker 失败: {e}")
        
    def update_frames(self):
        """从队列读取并更新画面帧"""
        import time as _time

        # 从队列中取出最新的帧数据（非破坏性：丢弃旧帧，仅保留最新）
        try:
            frame_data = self._drain_latest(self.ir_queue)
            if frame_data is not None:
                dtype = np.dtype(frame_data['dtype'])
                frame = np.frombuffer(frame_data['bytes'], dtype=dtype).reshape(frame_data['shape']).copy()
                ts = frame_data.get('timestamp', _time.time())
                # 保存 latest_ir 以便后续配对使用
                self.latest_ir = (frame, float(ts))
                # 显示 IR（带检测覆盖）
                self._display_frame_with_detection(frame, self.ir_label, 'ir')
        except Exception:
            pass

        try:
            frame_data = self._drain_latest(self.rgb_queue)
            if frame_data is not None:
                dtype = np.dtype(frame_data['dtype'])
                frame = np.frombuffer(frame_data['bytes'], dtype=dtype).reshape(frame_data['shape']).copy()
                ts = frame_data.get('timestamp', _time.time())
                self.latest_rgb = (frame, float(ts))
                # 显示 RGB（带检测覆盖）
                self._display_frame_with_detection(frame, self.rgb_label, 'rgb')
        except Exception:
            pass

        # 尝试按时间戳配对最新的 IR 与 RGB
        try:
            if self.latest_ir and self.latest_rgb:
                ir_frame, ir_ts = self.latest_ir
                rgb_frame, rgb_ts = self.latest_rgb
                if abs(ir_ts - rgb_ts) <= float(self.pair_threshold):
                    pair_ts = max(ir_ts, rgb_ts)
                    # 保存配对副本供 capture_snapshot 使用
                    self.last_paired = (ir_frame.copy(), rgb_frame.copy(), pair_ts)
                    # 清理 latest 缓存，避免重复使用
                    self.latest_ir = None
                    self.latest_rgb = None

                    # 提交配对帧给 ROI worker 进行检测
                    if self.roi_worker is not None:
                        try:
                            self.roi_worker.submit_pair(ir_frame, rgb_frame, timestamp=pair_ts)
                        except Exception:
                            pass
        except Exception:
            pass

        return

    def _drain_latest(self, q):
        """从队列中取出并返回最后放入的一项，丢弃老数据。如果队列为空返回 None。"""
        latest = None
        try:
            while True:
                latest = q.get_nowait()
        except Exception:
            pass
        return latest
    
    def _on_detection_result(self, result_dict):
        """处理来自 ROI Worker 的检测结果"""
        try:
            with self._detection_lock:
                self._latest_detection = result_dict
                
            # 可选：向 worker 提交新帧
            # （当前在 update_frames 的配对逻辑中提交）
        except Exception:
            pass
    
    def get_latest_detection(self):
        """获取最新的检测结果（供 snapshot 使用）"""
        try:
            with self._detection_lock:
                return self._latest_detection
        except Exception:
            return None
    
    def _display_frame_with_detection(self, frame, label, frame_type='rgb'):
        """显示帧并叠加检测结果
        
        Args:
            frame: OpenCV 格式图像帧
            label: QLabel 控件
            frame_type: 'ir' 或 'rgb'
        """
        annotated = frame.copy()
        
        # 获取最新检测结果并绘制
        try:
            detection = self.get_latest_detection()
            if detection:
                # 判断使用哪个检测结果
                det_data = None
                if frame_type == 'ir' and 'ir_detection' in detection:
                    det_data = detection['ir_detection']
                elif frame_type == 'rgb' and 'rgb_detection' in detection:
                    det_data = detection['rgb_detection']
                elif 'detection' in detection:
                    # 单帧模式
                    det_data = detection['detection']
                
                if det_data and 'hands' in det_data:
                    annotated = self._draw_detection(annotated, det_data)
        except Exception:
            pass
        
        # 显示
        self.display_frame(annotated, label)
    
    def _draw_detection(self, frame, detection_data):
        """在帧上绘制检测结果
        
        Args:
            frame: 原始帧
            detection_data: 检测数据 dict
            
        Returns:
            带注释的帧
        """
        h, w = frame.shape[:2]
        
        try:
            for hand in detection_data.get('hands', []):
                # 绘制 ROI 正方形（绿色）
                roi_corners = hand.get('roi_corners')
                if roi_corners and len(roi_corners) == 4:
                    pts = np.array(roi_corners, dtype=np.int32)
                    cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                
                # 绘制掌心（红色圆点）
                palm_center = hand.get('palm_center')
                if palm_center:
                    cv2.circle(frame, palm_center, 5, (0, 0, 255), -1)
                
                # 绘制关键点（黄色小圆点）
                landmarks_px = hand.get('landmarks_px', [])
                for lm_px in landmarks_px:
                    cv2.circle(frame, lm_px, 2, (0, 255, 255), -1)
                
                # 绘制连接线（MediaPipe 手部连接）
                if len(landmarks_px) >= 21:
                    # 定义手部关键点连接
                    connections = [
                        (0, 1), (1, 2), (2, 3), (3, 4),  # 拇指
                        (0, 5), (5, 6), (6, 7), (7, 8),  # 食指
                        (0, 9), (9, 10), (10, 11), (11, 12),  # 中指
                        (0, 13), (13, 14), (14, 15), (15, 16),  # 无名指
                        (0, 17), (17, 18), (18, 19), (19, 20),  # 小指
                        (5, 9), (9, 13), (13, 17)  # 掌部
                    ]
                    for start, end in connections:
                        if start < len(landmarks_px) and end < len(landmarks_px):
                            pt1 = landmarks_px[start]
                            pt2 = landmarks_px[end]
                            cv2.line(frame, pt1, pt2, (255, 255, 0), 2)
                
                # 显示 handedness 标签
                handedness = hand.get('handedness')
                if handedness and palm_center:
                    label_text = f"{handedness}"
                    cv2.putText(frame, label_text, 
                               (palm_center[0] + 10, palm_center[1] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        except Exception:
            pass
        
        return frame
    
    def display_frame(self, frame, label):
        """
        在 QLabel 上显示画面帧，自动缩放适应标签大小并保持原始比例
        
        Args:
            frame: OpenCV 格式的图像帧
            label: 要显示的 QLabel
        """
        # 将 BGR 转换为 RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 获取图像尺寸
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        
        # 转换为 QImage
        q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # 获取 QLabel 的当前尺寸
        label_size = label.size()
        
        # 如果标签尺寸有效，则缩放图像以适应标签，保持宽高比
        if label_size.width() > 0 and label_size.height() > 0:
            pixmap = QPixmap.fromImage(q_image)
            scaled_pixmap = pixmap.scaled(
                label_size.width(),
                label_size.height(),
                Qt.AspectRatioMode.KeepAspectRatio,  # 保持原始宽高比
                Qt.TransformationMode.SmoothTransformation  # 平滑缩放
            )
            # 显示缩放后的图像
            label.setPixmap(scaled_pixmap)
        else:
            # 如果标签尺寸无效，直接显示原始图像
            label.setPixmap(QPixmap.fromImage(q_image))
    
    def capture_snapshot(self):
        """
        捕获当前画面快照（同步捕获IR和RGB）
        使用短暂等待机制确保同时获取两个画面
        
        Returns:
            tuple: (ir_frame, rgb_frame, detection_result) 
                   detection_result 为最新的检测结果 dict 或 None
        """
        import time

        # 优先使用最近一次成功配对的帧（由 update_frames 设置）
        max_attempts = 10
        attempt = 0
        while attempt < max_attempts:
            if self.last_paired is not None:
                try:
                    ir_frame, rgb_frame, _ = self.last_paired
                    # 清除以避免重复使用
                    self.last_paired = None
                    # 获取最新检测结果
                    detection = self.get_latest_detection()
                    logger.debug(f"使用配对帧进行捕获 (尝试次数: {attempt + 1})")
                    return ir_frame, rgb_frame, detection
                except Exception:
                    self.last_paired = None
            attempt += 1
            time.sleep(0.05)

        # 回退：如果没有可用的配对帧则使用原先的队列读取逻辑（尽量获取最新帧）
        ir_frame = None
        rgb_frame = None
        max_attempts = 5  # 最多尝试5次
        attempt = 0

        # 清空队列（丢弃旧帧）
        try:
            while True:
                self.ir_queue.get_nowait()
        except Exception:
            pass
        try:
            while True:
                self.rgb_queue.get_nowait()
        except Exception:
            pass

        # 等待并取最新帧
        while attempt < max_attempts:
            try:
                frame_data = self._drain_latest(self.ir_queue)
                if frame_data is not None:
                    dtype = np.dtype(frame_data['dtype'])
                    ir_frame = np.frombuffer(frame_data['bytes'], dtype=dtype).reshape(frame_data['shape']).copy()
            except Exception:
                pass

            try:
                frame_data = self._drain_latest(self.rgb_queue)
                if frame_data is not None:
                    dtype = np.dtype(frame_data['dtype'])
                    rgb_frame = np.frombuffer(frame_data['bytes'], dtype=dtype).reshape(frame_data['shape']).copy()
            except Exception:
                pass

            if ir_frame is not None and rgb_frame is not None:
                logger.debug(f"成功同步捕获IR和RGB画面 (尝试次数: {attempt + 1})")
                detection = self.get_latest_detection()
                return ir_frame, rgb_frame, detection

            attempt += 1
            time.sleep(0.05)

        # 如果超时仍未同时获取到两个画面
        if ir_frame is None or rgb_frame is None:
            logger.warning(f"画面捕获不完整 - IR: {'有' if ir_frame is not None else '无'}, RGB: {'有' if rgb_frame is not None else '无'}")

        detection = self.get_latest_detection()
        return ir_frame, rgb_frame, detection
    
    def set_camera_ids(self, ir_id, rgb_id):
        """
        设置摄像头ID并重启
        
        Args:
            ir_id: 红外摄像头ID
            rgb_id: RGB摄像头ID
        """
        was_running = self.is_running
        if was_running:
            self.stop()
        
        self.ir_camera_id = ir_id
        self.rgb_camera_id = rgb_id
        
        if was_running:
            self.start()

    def set_camera_property(self, which: str, prop, value):
        """设置摄像头属性（通过控制队列发送到子进程）。

        Args:
            which: 'ir' 或 'rgb' 或 'both'
            prop: OpenCV cv2.CAP_PROP_* 常量
            value: 要设置的值
        """
        cmd = {'action': 'set', 'prop': prop, 'value': value}
        try:
            if which == 'ir' or which == 'both':
                try:
                    self.ir_control_queue.put_nowait(cmd)
                except Exception:
                    # 如果队列已满，丢弃最旧的命令并插入新命令，避免阻塞
                    try:
                        _ = self.ir_control_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self.ir_control_queue.put_nowait(cmd)
                    except Exception:
                        logger.debug("ir_control_queue 已满且无法写入")
            if which == 'rgb' or which == 'both':
                try:
                    self.rgb_control_queue.put_nowait(cmd)
                except Exception:
                    try:
                        _ = self.rgb_control_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self.rgb_control_queue.put_nowait(cmd)
                    except Exception:
                        logger.debug("rgb_control_queue 已满且无法写入")
        except Exception as e:
            logger.error(f"发送摄像头属性设置命令失败: {e}")

    def set_manual_exposure(self, which: str, exposure_value):
        """以较稳健的序列在子进程中设置手动曝光。

        该函数会向控制队列发送一个 sequence 命令：先尝试修改 AUTO_EXPOSURE 的常见标志，
        然后设置 exposure 值，增加小延时以提高生效概率（子进程会在 sequence 中间休眠）。

        Args:
            which: 'ir'|'rgb'|'both'
            exposure_value: 已经映射到目标后端范围的曝光值
        """
        # 构建尝试序列（按经验在 Windows 上这样能提高成功率）
        seq_attempts = [
            {'prop': cv2.CAP_PROP_AUTO_EXPOSURE, 'value': 1},    # try toggle
            {'prop': cv2.CAP_PROP_AUTO_EXPOSURE, 'value': 0.25}, # try manual flag in some backends
            {'prop': cv2.CAP_PROP_EXPOSURE, 'value': exposure_value}
        ]
        cmd = {'action': 'sequence', 'seq': seq_attempts}
        try:
            if which == 'ir' or which == 'both':
                try:
                    self.ir_control_queue.put_nowait(cmd)
                except Exception:
                    try:
                        _ = self.ir_control_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self.ir_control_queue.put_nowait(cmd)
                    except Exception:
                        logger.debug('ir_control_queue 已满且无法写入 sequence')
            if which == 'rgb' or which == 'both':
                try:
                    self.rgb_control_queue.put_nowait(cmd)
                except Exception:
                    try:
                        _ = self.rgb_control_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self.rgb_control_queue.put_nowait(cmd)
                    except Exception:
                        logger.debug('rgb_control_queue 已满且无法写入 sequence')
        except Exception as e:
            logger.error(f"发送手动曝光 sequence 失败: {e}")
    
    def __del__(self):
        """析构函数，确保进程被正确关闭"""
        try:
            if hasattr(self, 'is_running') and self.is_running:
                # 只停止进程，不操作可能已删除的 QLabel
                self.is_running = False
                if hasattr(self, 'timer'):
                    self.timer.stop()
                
                if hasattr(self, 'ir_stop_event'):
                    self.ir_stop_event.set()
                if hasattr(self, 'rgb_stop_event'):
                    self.rgb_stop_event.set()
                
                if hasattr(self, 'ir_process') and self.ir_process and self.ir_process.is_alive():
                    self.ir_process.terminate()
                
                if hasattr(self, 'rgb_process') and self.rgb_process and self.rgb_process.is_alive():
                    self.rgb_process.terminate()
        except:
            pass  # 忽略析构时的所有错误
