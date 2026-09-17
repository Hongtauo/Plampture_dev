# -*- coding: utf-8 -*-
"""
MediaPipe 手部关键点检测 + ROI 提取 Worker
在后台 QThread 中运行，接收视频帧并返回检测结果与 ROI
"""
import cv2
import numpy as np
from collections import deque
import threading
import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except Exception:
    HAS_MEDIAPIPE = False

# 导入 ROI 提取函数
try:
    from ROI import get_circumcenter, get_roi_square_points, get_roi_square_points_0_5_17
    HAS_ROI_UTILS = True
except Exception:
    HAS_ROI_UTILS = False


class PalmROIWorker(QThread):
    """后台 Worker：MediaPipe 手部检测 + ROI 提取
    
    输入：通过 submit_frame 或 submit_pair 提交帧
    输出信号：
        - detection: 发送检测结果（包含关键点、bbox、ROI corners等）
        - annotated_frame: 发送带注释的 QImage（可选，用于直接显示）
    """
    # 信号定义
    detection = Signal(object)  # dict: {timestamp, ir_result, rgb_result}
    annotated_frame = Signal(object, float)  # (QImage, timestamp) - 可选可视化
    
    def __init__(self, 
                 max_num_hands=1,
                 min_detection_confidence=0.3,
                 min_tracking_confidence=0.3,
                 process_every_n=1,  # 每帧都检测，实时跟踪
                 model_complexity=0,  # 0=最快，1=平衡，2=最准确
                 use_circumscribed_roi=False, # 是否使用外接矩形 ROI
                 parent=None):
        super().__init__(parent)
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self._process_every_n = process_every_n
        self.model_complexity = model_complexity
        self.use_circumscribed_roi = use_circumscribed_roi
        
        self._queue = deque()
        self._lock = threading.Lock()
        self._running = False
    
    def submit_frame(self, frame_bgr, timestamp=None, frame_type='rgb'):
        """提交单个帧进行处理
        
        Args:
            frame_bgr: BGR numpy array
            timestamp: 帧时间戳
            frame_type: 'ir' 或 'rgb'
        """
        if frame_bgr is None:
            return
        ts = float(timestamp) if timestamp is not None else time.time()
        with self._lock:
            self._queue.append({
                'type': 'single',
                'frame': frame_bgr.copy(),
                'timestamp': ts,
                'frame_type': frame_type
            })
            # 限制队列长度
            if len(self._queue) > 8:
                while len(self._queue) > 8:
                    self._queue.popleft()
    
    def submit_pair(self, ir_frame, rgb_frame, timestamp=None):
        """提交 IR+RGB 配对帧
        
        Args:
            ir_frame: IR 帧（BGR）
            rgb_frame: RGB 帧（BGR）
            timestamp: 配对时间戳
        """
        if ir_frame is None or rgb_frame is None:
            return
        ts = float(timestamp) if timestamp is not None else time.time()
        with self._lock:
            self._queue.append({
                'type': 'pair',
                'ir_frame': ir_frame.copy(),
                'rgb_frame': rgb_frame.copy(),
                'timestamp': ts
            })
            if len(self._queue) > 8:
                while len(self._queue) > 8:
                    self._queue.popleft()
    
    def stop(self):
        """停止 worker"""
        self._running = False
        self.wait(500)
    
    def run(self):
        """主循环：处理队列中的帧"""
        if not HAS_MEDIAPIPE:
            return
        
        self._running = True
        
        # 初始化 MediaPipe Hands
        mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=self.max_num_hands,
            model_complexity=1,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        )
        
        frame_count = 0
        
        try:
            while self._running:
                item = None
                with self._lock:
                    if self._queue:
                        item = self._queue.popleft()
                
                if item is None:
                    time.sleep(0.005)
                    continue
                
                frame_count += 1
                if (frame_count % self._process_every_n) != 0:
                    continue
                
                # 处理帧
                if item['type'] == 'single':
                    self._process_single_frame(item, mp_hands)
                elif item['type'] == 'pair':
                    self._process_paired_frames(item, mp_hands)
        
        finally:
            try:
                mp_hands.close()
            except Exception:
                pass
    
    def _process_single_frame(self, item, mp_hands):
        """处理单个帧"""
        frame_bgr = item['frame']
        timestamp = item['timestamp']
        frame_type = item.get('frame_type', 'rgb')
        
        # 转换为 RGB
        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            rgb = frame_bgr
        
        # 性能优化：降低分辨率到 640x480（MediaPipe 在低分辨率下更快）
        h, w = rgb.shape[:2]
        if w > 640 or h > 480:
            scale = min(640/w, 480/h)
            new_w, new_h = int(w * scale), int(h * scale)
            rgb_resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            rgb_resized = rgb
        
        # MediaPipe 检测
        results = mp_hands.process(rgb_resized)
        
        # 提取检测结果
        detection_data = self._extract_detection_data(results, frame_bgr.shape[:2])
        
        # 发送结果
        try:
            result_dict = {
                'timestamp': timestamp,
                'frame_type': frame_type,
                'detection': detection_data
            }
            self.detection.emit(result_dict)
        except Exception:
            pass
    
    def _process_paired_frames(self, item, mp_hands):
        """处理配对帧（IR + RGB）"""
        ir_frame = item['ir_frame']
        rgb_frame = item['rgb_frame']
        timestamp = item['timestamp']
        
        # 处理 RGB 帧
        try:
            rgb = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2RGB)
        except Exception:
            rgb = rgb_frame
        
        # 性能优化：降低分辨率
        h_rgb, w_rgb = rgb.shape[:2]
        if w_rgb > 640 or h_rgb > 480:
            scale = min(640/w_rgb, 480/h_rgb)
            rgb = cv2.resize(rgb, (int(w_rgb * scale), int(h_rgb * scale)), interpolation=cv2.INTER_LINEAR)
        
        rgb_results = mp_hands.process(rgb)
        rgb_detection = self._extract_detection_data(rgb_results, rgb_frame.shape[:2])
        
        # 处理 IR 帧（可选，如果需要在 IR 上也检测）
        # 由于 MediaPipe 对灰度图支持有限，这里可以转为 3 通道或跳过
        ir_detection = None
        try:
            if len(ir_frame.shape) == 2:
                ir_rgb = cv2.cvtColor(ir_frame, cv2.COLOR_GRAY2RGB)
            else:
                ir_rgb = cv2.cvtColor(ir_frame, cv2.COLOR_BGR2RGB)
            
            # 性能优化：降低分辨率
            h_ir, w_ir = ir_rgb.shape[:2]
            if w_ir > 640 or h_ir > 480:
                scale = min(640/w_ir, 480/h_ir)
                ir_rgb = cv2.resize(ir_rgb, (int(w_ir * scale), int(h_ir * scale)), interpolation=cv2.INTER_LINEAR)
            
            ir_results = mp_hands.process(ir_rgb)
            ir_detection = self._extract_detection_data(ir_results, ir_frame.shape[:2])
        except Exception:
            pass
        
        # 发送结果
        try:
            result_dict = {
                'timestamp': timestamp,
                'ir_detection': ir_detection,
                'rgb_detection': rgb_detection
            }
            self.detection.emit(result_dict)
        except Exception:
            pass
    
    def _extract_detection_data(self, results, image_shape):
        """从 MediaPipe results 提取检测数据和 ROI
        
        Returns:
            dict: {
                'hands': [
                    {
                        'landmarks': [(x,y,z), ...],  # normalized
                        'landmarks_px': [(x,y), ...],  # pixel coords
                        'handedness': 'Left'/'Right',
                        'bbox': [xmin, ymin, xmax, ymax],  # normalized
                        'roi_corners': [(x,y), ...] or None,  # pixel coords, 4个顶点
                        'palm_center': (x,y) or None  # pixel coords
                    },
                    ...
                ]
            }
        """
        h, w = image_shape
        hands_data = []
        
        if not results or not results.multi_hand_landmarks:
            return {'hands': hands_data}
        
        for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # 提取 handedness
            handedness_label = None
            try:
                if results.multi_handedness and hand_idx < len(results.multi_handedness):
                    handedness_label = results.multi_handedness[hand_idx].classification[0].label
            except Exception:
                pass
            
            # 提取关键点（normalized 和 pixel）
            landmarks_norm = []
            landmarks_px = []
            for lm in hand_landmarks.landmark:
                landmarks_norm.append((lm.x, lm.y, lm.z))
                landmarks_px.append((int(lm.x * w), int(lm.y * h)))
            
            # 计算 bbox（normalized）
            xs = [p[0] for p in landmarks_norm]
            ys = [p[1] for p in landmarks_norm]
            bbox = [min(xs), min(ys), max(xs), max(ys)] if xs and ys else [0, 0, 0, 0]
            
            # 计算 ROI（使用 ROI.py 的函数）
            roi_corners = None
            palm_center = None
            
            if HAS_ROI_UTILS and len(landmarks_px) > 17:
                try:
                    # 使用 7 个关键点：WRIST(0), THUMB_CMC(1), THUMB_MCP(2), 
                    # INDEX_FINGER_MCP(5), MIDDLE_FINGER_MCP(9), RING_FINGER_MCP(13), PINKY_MCP(17)
                    key_points = [
                        landmarks_px[0],   # WRIST
                        landmarks_px[1],   # THUMB_CMC
                        landmarks_px[2],   # THUMB_MCP
                        landmarks_px[5],   # INDEX_FINGER_MCP
                        landmarks_px[9],   # MIDDLE_FINGER_MCP
                        landmarks_px[13],  # RING_FINGER_MCP
                        landmarks_px[17]   # PINKY_MCP
                    ]
                    
                    # 计算外接圆心（掌心）- 使用食指、小指、手腕三点
                    p1 = landmarks_px[5]
                    p2 = landmarks_px[17]
                    p3 = landmarks_px[0]
                    cx, cy = get_circumcenter(p1, p2, p3)
                    if cx is not None and cy is not None:
                        palm_center = (int(cx), int(cy))
                    
                    # 计算 ROI 矩形顶点（改为使用 0-5-17 方法）
                    try:
                        roi_corners = get_roi_square_points_0_5_17(
                            [landmarks_px[0], landmarks_px[5], landmarks_px[17]],
                            use_circumscribed=self.use_circumscribed_roi
                        )
                    except Exception:
                        roi_corners = None
                except Exception:
                    pass
            
            hand_data = {
                'landmarks': landmarks_norm,
                'landmarks_px': landmarks_px,
                'handedness': handedness_label,
                'bbox': bbox,
                'roi_corners': roi_corners,
                'palm_center': palm_center
            }
            hands_data.append(hand_data)
        
        return {'hands': hands_data}
