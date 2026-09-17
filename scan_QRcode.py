import cv2
import numpy as np
from typing import Optional

def scan_qrcode(frame: np.ndarray) -> Optional[str]:
    """
    使用 OpenCV 扫描并解码图像中的QR码。

    参数:
        frame: 包含QR码的图像帧（numpy数组格式，BGR格式）。

    返回:
        解码后的QR码数据字符串。如果没有检测到QR码，则返回 None。
    """
    try:
        # 创建二维码检测器
        qr_detector = cv2.QRCodeDetector()
        
        # 检测并解码二维码
        data, bbox, straight_qrcode = qr_detector.detectAndDecode(frame)
        
        # 如果检测到二维码且数据不为空
        if data:
            return data
        else:
            return None
    except cv2.error as e:
        # OpenCV 内部错误（如无效的轮廓点），静默忽略
        # 这通常发生在图像质量差或没有有效 QR 码时
        return None
    except Exception:
        # 其他未预期的错误，也返回 None
        return None