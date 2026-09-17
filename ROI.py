import os
from typing import List, Dict, Tuple, Optional

import cv2
import numpy as np


def get_circumcenter(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float]) -> Tuple[Optional[float], Optional[float]]:
    """计算三角形外接圆心（p1,p2,p3 为 (x,y)）
    若三点共线返回 (None, None)。"""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(D) < 1e-9:
        return None, None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / D
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / D
    return ux, uy


def get_roi_square_points_from_3pts(p_wrist: Tuple[float, float], 
                                  p_index_mcp: Tuple[float, float], 
                                  p_pinky_mcp: Tuple[float, float], 
                                  use_circumscribed: bool = False) -> Optional[List[Tuple[float, float]]]:
    """
    计算手掌 ROI 的四个顶点坐标 (核心逻辑)。
    
    Args:
        p_wrist: 手腕关键点 (P0)
        p_index_mcp: 食指根部 (P5)
        p_pinky_mcp: 小指根部 (P17)
        use_circumscribed: 是否使用外接矩形模式
            - False (默认): 内接正方形模式，边长 = P5-P17 距离
            - True: 外接矩形模式，基于 P0-P5-P17 外接圆，覆盖更大区域
    
    Returns:
        [TL, TR, BR, BL] 四个顶点坐标，或 None
    """
    try:
        p0 = np.array(p_wrist, dtype=float)
        p5 = np.array(p_index_mcp, dtype=float)
        p17 = np.array(p_pinky_mcp, dtype=float)

        # 计算基准方向向量 (P5 -> P17)
        vec_top = p17 - p5
        base_len = np.linalg.norm(vec_top)
        if base_len < 1e-6:
            return None
        
        dir_top = vec_top / base_len
        
        if use_circumscribed:
            # ========== 外接矩形模式 ==========
            # 1. 计算 P0, P5, P17 三点的外接圆圆心和半径
            cx, cy = get_circumcenter(tuple(p5), tuple(p17), tuple(p0))
            if cx is None or cy is None:
                return None
            
            center = np.array([cx, cy], dtype=float)
            
            # 计算半径（使用到 P5 的距离）
            radius = np.linalg.norm(p5 - center)
            if radius < 1e-3:
                return None
            
            # 2. 计算垂直方向（指向手腕）
            vec_to_wrist = p0 - center
            perp1 = np.array([-dir_top[1], dir_top[0]])  # 逆时针90度
            perp2 = np.array([dir_top[1], -dir_top[0]])  # 顺时针90度
            
            # 选择与 vec_to_wrist 方向一致的那个垂线作为 "Down"
            if np.dot(perp1, vec_to_wrist) > 0:
                dir_down = perp1
            else:
                dir_down = perp2
            
            # 3. 构建外接矩形（正方形，边长 = 直径）
            side_len = 2 * radius
            half_side = side_len / 2.0
            
            # 矩形中心就是圆心，构建四个顶点
            pt_top_left = center - dir_top * half_side - dir_down * half_side
            pt_top_right = center + dir_top * half_side - dir_down * half_side
            pt_bot_right = center + dir_top * half_side + dir_down * half_side
            pt_bot_left = center - dir_top * half_side + dir_down * half_side
            
        else:
            # ========== 内接正方形模式（默认）==========
            # 1. 边长严格等于 P5-P17 距离
            real_side_len = base_len
            
            # 2. 确定 P5-P17 中点
            mid_finger = (p5 + p17) / 2.0

            # 3. 计算垂直向下的方向 (Towards Wrist P0)
            vec_to_wrist = p0 - mid_finger
            perp1 = np.array([-dir_top[1], dir_top[0]])  # 逆时针90度
            perp2 = np.array([dir_top[1], -dir_top[0]])  # 顺时针90度
            
            # 选择与 vec_to_wrist 方向一致的那个垂线作为 "Down"
            if np.dot(perp1, vec_to_wrist) > 0:
                dir_down = perp1
            else:
                dir_down = perp2
                
            # 4. 构建严格锚定在 P5-P17 上的正方形顶点
            half_side = real_side_len / 2.0
            
            # pt_top_a 靠近 P5 (Index) 的一侧
            pt_top_left = mid_finger - dir_top * half_side
            # pt_top_b 靠近 P17 (Pinky) 的一侧
            pt_top_right = mid_finger + dir_top * half_side
            
            # 沿着 dir_down 方向延伸 real_side_len
            pt_bot_left = pt_top_left + dir_down * real_side_len
            pt_bot_right = pt_top_right + dir_down * real_side_len

        # 手性自适应 (Handedness Handling)
        vec_ref_up = p5 - p0 
        vec_ref_right = np.array([-vec_ref_up[1], vec_ref_up[0]])
        
        proj_5 = np.dot(p5, vec_ref_right)
        proj_17 = np.dot(p17, vec_ref_right) 
        
        if proj_5 < proj_17:
            # 右手: P5侧在左, P17侧在右
            tl, tr = pt_top_left, pt_top_right
            bl, br = pt_bot_left, pt_bot_right
        else:
            # 左手: P17侧在左, P5侧在右
            tl, tr = pt_top_right, pt_top_left
            bl, br = pt_bot_right, pt_bot_left

        return [tuple(tl), tuple(tr), tuple(br), tuple(bl)]
    except Exception:
        return None


def get_roi_square_points(points: List[Tuple[float, float]], use_circumscribed: bool = False) -> Optional[List[Tuple[float, float]]]:
    """
    【新方法】：以 P5-P17 连线为正方形的一条边，沿着 P0 方向构建 ROI。
    边长严格等于 P5-P17 距离，顶边严格锚定在 P5-P17 连线上。
    
    输入: points 为长度至少为7的列表，包含关键点:
        points[0]: WRIST (P0)
        points[1]: THUMB_CMC (P1)
        points[2]: THUMB_MCP (P2)
        points[3]: INDEX_MCP (P5)
        points[4]: MIDDLE_MCP (P9)
        points[5]: RING_MCP (P13)
        points[6]: PINKY_MCP (P17)
    
    返回: 四个顶点 [(tl),(tr),(br),(bl)] 或 None
    """
    if not points or len(points) < 7:
        return None
    
    return get_roi_square_points_from_3pts(points[0], points[3], points[6], use_circumscribed)


def compute_palm_rois_from_results(
    results_list: List[Tuple[str, object]],
    prepared_dict: Optional[Dict[str, np.ndarray]] = None,
    save_dir: Optional[str] = None,
    resize_to: Optional[Tuple[int, int]] = None,
) -> Dict[str, List[Dict]]:
    """为 results_list 中每只手计算掌心 ROI 并（可选）从增强图像裁切出旋转对齐的 ROI 图像。

    输入：
      - results_list: list of (path, results)，results 为 MediaPipe Hands 的输出对象
      - prepared_dict: 可选，{path: RGB ndarray}，优先使用该增强图像来裁切
      - save_dir: 可选，如果提供则把 roi_image 保存为 PNG，返回的 hand_data 中包含 'roi_path'
      - resize_to: 可选，(w,h) 若提供则把裁切结果缩放到该尺寸

    返回：palm_roi_data 字典，key=path，value=list of hand_data，hand_data 包含：
      - 'palm_center': (x,y) 外接圆心（浮点）
      - 'roi_corners': list of 4 (x,y) 顶点（浮点）或 None
      - 'roi_image': RGB ndarray or None
      - 'roi_path': 保存路径（如果 save_dir 提供并已保存）
    """
    os.makedirs(save_dir, exist_ok=True) if save_dir else None
    palm_roi_data: Dict[str, List[Dict]] = {}

    for path, results in results_list:
        hands_info: List[Dict] = []

        # 准备用于裁切的 RGB 图像（优先使用 prepared_dict）
        prepared_img = None
        if prepared_dict and path in prepared_dict:
            prepared_img = prepared_dict[path]
            image_h, image_w = prepared_img.shape[:2]
        else:
            img_bgr = cv2.imread(path)
            if img_bgr is None:
                palm_roi_data[path] = []
                continue
            image_h, image_w = img_bgr.shape[:2]
            prepared_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        if not results or not getattr(results, 'multi_hand_landmarks', None):
            palm_roi_data[path] = hands_info
            continue

        for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # 使用 7 个关键点计算 ROI
            key_points = [
                (hand_landmarks.landmark[0].x * image_w, hand_landmarks.landmark[0].y * image_h),   # WRIST
                (hand_landmarks.landmark[1].x * image_w, hand_landmarks.landmark[1].y * image_h),   # THUMB_CMC
                (hand_landmarks.landmark[2].x * image_w, hand_landmarks.landmark[2].y * image_h),   # THUMB_MCP
                (hand_landmarks.landmark[5].x * image_w, hand_landmarks.landmark[5].y * image_h),   # INDEX_FINGER_MCP
                (hand_landmarks.landmark[9].x * image_w, hand_landmarks.landmark[9].y * image_h),   # MIDDLE_FINGER_MCP
                (hand_landmarks.landmark[13].x * image_w, hand_landmarks.landmark[13].y * image_h), # RING_FINGER_MCP
                (hand_landmarks.landmark[17].x * image_w, hand_landmarks.landmark[17].y * image_h)  # PINKY_MCP
            ]
            
            # 计算掌心（使用食指、小指、手腕三点的外接圆心）
            p1 = key_points[3]  # INDEX_FINGER_MCP
            p2 = key_points[6]  # PINKY_MCP
            p3 = key_points[0]  # WRIST
            cx, cy = get_circumcenter(p1, p2, p3)
            
            # 计算 ROI 矩形顶点（使用新方法）
            roi_corners = get_roi_square_points(key_points)

            roi_image = None
            roi_path = None
            if roi_corners is not None and prepared_img is not None:
                # 使用透视变换裁切为轴对齐正方形 ROI（基于 roi_corners 提供的 4 个点）
                try:
                    orig_name = os.path.basename(path)
                    name_parts = orig_name.split('_')
                    # 期望格式如 003_r_850_04.jpg -> folder '003_r' and filename '04.jpg'
                    if save_dir:
                        if len(name_parts) >= 4:
                            folder_name = f"{name_parts[0]}_{name_parts[1]}"
                            file_name = name_parts[-1]
                        else:
                            # 回退到原始 base 名称并添加 hand index
                            base = os.path.splitext(orig_name)[0]
                            folder_name = base
                            file_name = f"{base}_hand{hand_idx}_roi.png"
                        out_subdir = os.path.join(save_dir, folder_name)
                        os.makedirs(out_subdir, exist_ok=True)
                        roi_path = os.path.join(out_subdir, file_name)
                    else:
                        roi_path = None

                    # 如果要保存到磁盘，直接调用 crop_and_save_roi
                    if roi_path:
                        dst = crop_and_save_roi(prepared_img, roi_corners, roi_path)
                        roi_image = dst if dst is not None else None
                    else:
                        # 内存中执行透视裁切
                        pts1 = np.array([[float(x), float(y)] for (x, y) in roi_corners], dtype=np.float32)
                        side = float(np.linalg.norm(pts1[1] - pts1[0]))
                        if side > 1.0:
                            # 标准正方形映射
                            pts2 = np.array([
                                [0.0, 0.0], 
                                [side - 1.0, 0.0], 
                                [side - 1.0, side - 1.0], 
                                [0.0, side - 1.0]
                            ], dtype=np.float32)
                            
                            M = cv2.getPerspectiveTransform(pts1, pts2)
                            dst = cv2.warpPerspective(prepared_img, M, (int(round(side)), int(round(side))), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                            roi_image = dst
                        else:
                            roi_image = None

                    if roi_image is not None and resize_to is not None:
                        roi_image = cv2.resize(roi_image, (resize_to[0], resize_to[1]), interpolation=cv2.INTER_LINEAR)
                except Exception:
                    roi_image = None

            hand_data = {
                'palm_center': (cx, cy),
                'roi_corners': roi_corners,
                'roi_image': roi_image,
                'roi_path': roi_path,
            }
            hands_info.append(hand_data)

        palm_roi_data[path] = hands_info

    return palm_roi_data


if __name__ == '__main__':
    # 简单示例：当作为脚本单独运行时不执行实际 MediaPipe 推理，仅展示函数用法签名。
    print('ROI module loaded. Use compute_palm_rois_from_results(results_list, prepared_dict=...) in your notebook.')


def crop_and_save_roi(original_image: np.ndarray, roi_corners: List[Tuple[float, float]], output_path: str) -> Optional[np.ndarray]:
    if roi_corners is None or len(roi_corners) != 4:
        return None

    pts1 = np.array([[float(x), float(y)] for (x, y) in roi_corners], dtype=np.float32)

    # 以第一条边（TopEdge）长度为边长
    side = float(np.linalg.norm(pts1[1] - pts1[0]))
    if side <= 1.0:
        return None
    
    size = int(round(side))

    # 【重要】：映射到标准正方形，不旋转
    # 输入点已经是 [TL, TR, BR, BL]，直接对应输出图的四个角
    pts2 = np.array([
        [0.0, 0.0],         # Top-Left (0,0)
        [size, 0.0],        # Top-Right (w,0)
        [size, size],       # Bottom-Right (w,h)
        [0.0, size]         # Bottom-Left (0,h)
    ], dtype=np.float32)

    try:
        M = cv2.getPerspectiveTransform(pts1, pts2)
        dst = cv2.warpPerspective(original_image, M, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return None

    # 保存部分保持不变
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    
    to_save = dst
    if dst.ndim == 3 and dst.shape[2] == 3:
        try:
            to_save = cv2.cvtColor(dst, cv2.COLOR_RGB2BGR)
        except Exception:
            to_save = dst

    cv2.imwrite(output_path, to_save)
    return dst


def get_roi_square_points_0_5_17(points: List[Tuple[float, float]], use_circumscribed: bool = False) -> Optional[List[Tuple[float, float]]]:
    """
    使用关键点 (0,5,17) 计算 ROI 正方形顶点（兼容性函数）。
    输入: points 为长度为3的列表: [p0 (WRIST), p5 (INDEX_MCP), p17 (PINKY_MCP)]
    返回: 四个顶点 [(tl),(tr),(br),(bl)] 或 None
    
    注意：此函数为兼容性保留，实际使用与 get_roi_square_points 相同的算法。
    """
    if not points or len(points) < 3:
        return None
    
    # 构建7点格式以调用主函数
    # 由于只有3个点，我们用占位符填充其他点
    extended_points = [
        points[0],  # WRIST
        points[0],  # THUMB_CMC (占位)
        points[0],  # THUMB_MCP (占位)
        points[1],  # INDEX_MCP
        points[1],  # MIDDLE_MCP (占位)
        points[1],  # RING_MCP (占位)
        points[2]   # PINKY_MCP
    ]
    
    return get_roi_square_points(extended_points, use_circumscribed=use_circumscribed)
