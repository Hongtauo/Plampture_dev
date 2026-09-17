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


def get_roi_square_points(p_wrist: Tuple[float, float], 
                          p_index_mcp: Tuple[float, float], # P5: Index MCP (食指根部)
                          p_pinky_mcp: Tuple[float, float]  # P17: Pinky MCP (小指根部)
                          ) -> Optional[List[Tuple[float, float]]]:
    """
    【严格模式】：以 P5-P17 连线为正方形的一条边，沿着 P0 方向构建 ROI。
    边长严格等于 P5-P17 距离，顶边严格锚定在 P5-P17 连线上。
    """
    p0 = np.array(p_wrist, dtype=float)
    p5 = np.array(p_index_mcp, dtype=float)
    p17 = np.array(p_pinky_mcp, dtype=float)

    # 1. 计算基准方向向量 (P5 -> P17) 和长度
    vec_top = p17 - p5
    base_len = np.linalg.norm(vec_top)
    if base_len < 1e-6:
        return None
    
    dir_top = vec_top / base_len
    
    # 确定实际边长 (严格等于 P5-P17 距离)
    real_side_len = base_len # <--- 严格模式
    
    # 2. 确定 P5-P17 中点
    mid_finger = (p5 + p17) / 2.0

    # 3. 计算垂直向下的方向 (Towards Wrist P0)
    vec_to_wrist = p0 - mid_finger
    perp1 = np.array([-dir_top[1], dir_top[0]]) # 逆时针90度
    perp2 = np.array([dir_top[1], -dir_top[0]]) # 顺时针90度
    
    # 选择与 vec_to_wrist 方向一致的那个垂线作为 "Down"
    if np.dot(perp1, vec_to_wrist) > 0:
        dir_down = perp1
    else:
        dir_down = perp2
        
    # 4. 构建严格锚定在 P5-P17 上的正方形顶点
    half_side = real_side_len / 2.0
    
    # pt_top_a 靠近 P5 (Index) 的一侧
    pt_top_a = mid_finger - dir_top * half_side # TL或TR
    # pt_top_b 靠近 P17 (Pinky) 的一侧
    pt_top_b = mid_finger + dir_top * half_side # TR或TL
    
    # 沿着 dir_down 方向延伸 real_side_len
    pt_bot_a = pt_top_a + dir_down * real_side_len
    pt_bot_b = pt_top_b + dir_down * real_side_len

    # 5. 手性自适应 (Handedness Handling) - 保持不变
    vec_ref_up = p5 - p0 
    vec_ref_right = np.array([-vec_ref_up[1], vec_ref_up[0]])
    
    proj_5 = np.dot(p5, vec_ref_right)
    proj_17 = np.dot(p17, vec_ref_right) 
    
    if proj_5 < proj_17:
        # 右手: P5侧在左, P17侧在右。
        tl, tr = pt_top_a, pt_top_b
        bl, br = pt_bot_a, pt_bot_b
    else:
        # 左手: P17侧在左, P5侧在右。
        tl, tr = pt_top_b, pt_top_a
        bl, br = pt_bot_b, pt_bot_a

    return [tuple(tl), tuple(tr), tuple(br), tuple(bl)]


def _rotate_and_mask_crop(rgb_img: np.ndarray, pts: np.ndarray) -> Optional[np.ndarray]:
    """给定 RGB 图像和多边形顶点 pts (Nx2, int)，返回旋转对齐后的掩膜裁切图像（RGB uint8）。
    基线使用 pts[0]->pts[1]，将其旋转为水平后裁切多边形的最小外接矩形并应用掩膜。
    如果计算失败返回 None。"""
    if rgb_img is None or pts is None or len(pts) < 3:
        return None
    h, w = rgb_img.shape[:2]
    x_coords = pts[:, 0]
    y_coords = pts[:, 1]
    min_x = max(0, int(np.min(x_coords)))
    max_x = min(w - 1, int(np.max(x_coords)))
    min_y = max(0, int(np.min(y_coords)))
    max_y = min(h - 1, int(np.max(y_coords)))
    if max_x <= min_x or max_y <= min_y:
        return None

    crop = rgb_img[min_y:max_y + 1, min_x:max_x + 1].copy()
    pts_rel = pts - np.array([min_x, min_y])

    # 基线向量
    try:
        p1_rel = pts_rel[0].astype(float)
        p2_rel = pts_rel[1].astype(float)
        base_vec = p2_rel - p1_rel
        base_len = np.linalg.norm(base_vec)
    except Exception:
        base_len = 0.0

    if base_len > 1e-6:
        angle = np.degrees(np.arctan2(base_vec[1], base_vec[0]))
        h_crop, w_crop = crop.shape[:2]
        center = (w_crop / 2.0, h_crop / 2.0)
        M = cv2.getRotationMatrix2D(center, -angle, 1.0)
        rotated = cv2.warpAffine(crop, M, (w_crop, h_crop), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        # 变换顶点
        ones = np.ones((pts_rel.shape[0], 1), dtype=np.float32)
        pts_rel_h = np.hstack([pts_rel.astype(np.float32), ones])
        new_pts = (M.dot(pts_rel_h.T)).T
        new_pts = np.round(new_pts).astype(np.int32)

        bx, by, bw, bh = cv2.boundingRect(new_pts)
        if bw <= 0 or bh <= 0:
            return None
        rotated_h, rotated_w = rotated.shape[:2]
        bx = max(0, min(bx, rotated_w - 1))
        by = max(0, min(by, rotated_h - 1))
        bw = max(1, min(bw, rotated_w - bx))
        bh = max(1, min(bh, rotated_h - by))
        crop_rot = rotated[by:by + bh, bx:bx + bw].copy()
        new_pts_rel = new_pts - np.array([bx, by])
        mask = np.zeros((bh, bw), dtype=np.uint8)
        cv2.fillPoly(mask, [new_pts_rel.astype(np.int32)], 255)
        crop_masked = cv2.bitwise_and(crop_rot, crop_rot, mask=mask)
        return crop_masked.astype(np.uint8)
    else:
        # 无法确定基线：直接以包围盒裁切并掩膜
        crop_rgb = crop.copy()
        h0, w0 = crop_rgb.shape[:2]
        mask = np.zeros((h0, w0), dtype=np.uint8)
        cv2.fillPoly(mask, [pts_rel.astype(np.int32)], 255)
        crop_masked = cv2.bitwise_and(crop_rgb, crop_rgb, mask=mask)
        return crop_masked.astype(np.uint8)


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

        # ... 在 compute_palm_rois_from_results 函数内部 ...

        for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # 获取所有关键点坐标
            key_points = [
                (hand_landmarks.landmark[0].x * image_w, hand_landmarks.landmark[0].y * image_h),   # 0: WRIST
                (hand_landmarks.landmark[1].x * image_w, hand_landmarks.landmark[1].y * image_h),   # 1: THUMB_CMC
                (hand_landmarks.landmark[2].x * image_w, hand_landmarks.landmark[2].y * image_h),   # 2: THUMB_MCP
                (hand_landmarks.landmark[5].x * image_w, hand_landmarks.landmark[5].y * image_h),   # 3: INDEX_MCP
                (hand_landmarks.landmark[9].x * image_w, hand_landmarks.landmark[9].y * image_h),   # 4: MIDDLE_MCP (P9)
                (hand_landmarks.landmark[13].x * image_w, hand_landmarks.landmark[13].y * image_h), # 5: RING_MCP (P13)
                (hand_landmarks.landmark[17].x * image_w, hand_landmarks.landmark[17].y * image_h)  # 6: PINKY_MCP
            ]
            
            # ... 在 compute_palm_rois_from_results 函数内部 ...

            # 定义关键点: Rp1=Index(P5), Rp2=Pinky(P17), Rp3=Wrist(P0)
            p_wrist = key_points[0]  # P0
            p_rp1 = key_points[3]    # P5 (食指根部)
            p_rp2 = key_points[6]    # P17 (小指根部)

            # 1. 计算圆心 (P0, P5, P17 外接圆心，仅记录数据)
            cx, cy = get_circumcenter(p_rp1, p_rp2, p_wrist)
            
            # 2. 计算 ROI 
            # 【严格模式】：不传入 scale_factor 或 center_offset_factor
            roi_corners = get_roi_square_points(p_wrist, p_rp1, p_rp2)
            
            # ... (后续代码不变，保持对 crop_and_save_roi 的调用) ...

            roi_image = None
            roi_path = None
            
            # ... (后续代码逻辑不变，保持之前的 crop_and_save_roi 使用标准正方形映射即可) ...
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
                            # 【修改这里】：与 crop_and_save_roi 保持一致
                            pts2 = np.array([
                                [0.0, 0.0], 
                                [side - 1.0, 0.0], 
                                [side - 1.0, side - 1.0], 
                                [0.0, side - 1.0]
                            ], dtype=np.float32)
                            
                            M = cv2.getPerspectiveTransform(pts1, pts2)
                            # ...
                        # ...
                            dst = cv2.warpPerspective(prepared_img, M, (int(round(side)), int(round(side))), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                            roi_image = dst
                        else:
                            roi_image = None

                    if roi_image is not None and resize_to is not None:
                        roi_image = cv2.resize(roi_image, (resize_to[0], resize_to[1]), interpolation=cv2.INTER_LINEAR)
                except Exception:
                    roi_image = None

            # 计算左右中心（基于 roi_corners 返回的 [TL,TR,BR,BL]）
            Lxcenter = Lycenter = Rxcenter = Rycenter = None
            if roi_corners is not None:
                try:
                    tl, tr, br, bl = [np.array(pt, dtype=float) for pt in roi_corners]
                    left_mid = (tl + bl) / 2.0
                    right_mid = (tr + br) / 2.0
                    Lxcenter, Lycenter = float(left_mid[0]), float(left_mid[1])
                    Rxcenter, Rycenter = float(right_mid[0]), float(right_mid[1])
                except Exception:
                    Lxcenter = Lycenter = Rxcenter = Rycenter = None

            hand_data = {
                'palm_center': (cx, cy),
                'Lxcenter': Lxcenter,
                'Lycenter': Lycenter,
                'Rxcenter': Rxcenter,
                'Rycenter': Rycenter,
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
    side = float(np.linalg.norm(pts1[1] - pts1[0]))
    if side <= 1.0: return None
    size = int(round(side))

    # 【关键】：映射到标准正方形 (TL->TR->BR->BL)
    # 这保证了输入图片中“指尖朝上”的部分，在输出图片中也是朝上(y=0)
    pts2 = np.array([
        [0.0, 0.0],       # Top-Left
        [size, 0.0],      # Top-Right
        [size, size],     # Bottom-Right
        [0.0, size]       # Bottom-Left
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
