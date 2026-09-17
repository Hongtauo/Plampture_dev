# -*- coding: utf-8 -*-
"""
摄像头属性范围检测工具
用于检测摄像头支持的亮度、对比度、曝光等属性的实际范围
"""

import cv2
import sys

def detect_camera_property_range(camera_id, prop, prop_name):
    """
    检测摄像头属性的实际有效范围
    
    Args:
        camera_id: 摄像头ID
        prop: OpenCV 属性常量
        prop_name: 属性名称（用于显示）
    
    Returns:
        (min_val, max_val, current_val)
    """
    print(f"\n{'='*60}")
    print(f"检测摄像头 {camera_id} 的 {prop_name} 范围")
    print(f"{'='*60}")
    
    # 打开摄像头
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"❌ 无法打开摄像头 {camera_id}")
        return None, None, None
    
    # 获取当前值
    current_val = cap.get(prop)
    print(f"当前值: {current_val}")
    
    # 尝试设置不同的值来找出范围
    test_values = [0, 1, 10, 25, 32, 50, 64, 100, 127, 128, 255]
    valid_values = []
    
    print(f"\n测试不同的值:")
    for val in test_values:
        cap.set(prop, val)
        actual = cap.get(prop)
        is_valid = abs(actual - val) < 5  # 允许小误差
        status = "✅" if is_valid else "❌"
        print(f"  设置 {val:3d} -> 实际 {actual:6.1f} {status}")
        if is_valid:
            valid_values.append(val)
    
    # 分析结果
    if valid_values:
        min_val = min(valid_values)
        max_val = max(valid_values)
        print(f"\n✅ 检测到的有效范围: {min_val} - {max_val}")
    else:
        print(f"\n❌ 未检测到有效范围，该属性可能不受支持")
        min_val, max_val = None, None
    
    # 恢复原值
    cap.set(prop, current_val)
    cap.release()
    
    return min_val, max_val, current_val


def main():
    """主函数"""
    print("="*60)
    print("摄像头属性范围检测工具")
    print("="*60)
    
    # 检测摄像头数量
    print("\n检测可用摄像头...")
    available_cameras = []
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()
    
    if not available_cameras:
        print("❌ 未检测到可用摄像头")
        return
    
    print(f"✅ 检测到 {len(available_cameras)} 个摄像头: {available_cameras}")
    
    # 选择要检测的摄像头
    if len(sys.argv) > 1:
        camera_id = int(sys.argv[1])
    else:
        print(f"\n请选择要检测的摄像头 ID (默认 0): ", end="")
        try:
            user_input = input().strip()
            camera_id = int(user_input) if user_input else 0
        except:
            camera_id = 0
    
    if camera_id not in available_cameras:
        print(f"❌ 摄像头 {camera_id} 不可用")
        return
    
    print(f"\n开始检测摄像头 {camera_id}...")
    
    # 检测各个属性
    properties = [
        (cv2.CAP_PROP_BRIGHTNESS, "亮度 (Brightness)"),
        (cv2.CAP_PROP_CONTRAST, "对比度 (Contrast)"),
        (cv2.CAP_PROP_SATURATION, "饱和度 (Saturation)"),
        (cv2.CAP_PROP_HUE, "色调 (Hue)"),
        (cv2.CAP_PROP_GAIN, "增益 (Gain)"),
        (cv2.CAP_PROP_EXPOSURE, "曝光 (Exposure)"),
    ]
    
    results = {}
    for prop, name in properties:
        min_val, max_val, current = detect_camera_property_range(camera_id, prop, name)
        results[name] = {
            'min': min_val,
            'max': max_val,
            'current': current
        }
    
    # 输出总结
    print(f"\n{'='*60}")
    print("检测结果总结")
    print(f"{'='*60}")
    print(f"{'属性':<20} {'最小值':<10} {'最大值':<10} {'当前值':<10} {'状态'}")
    print("-"*60)
    
    for name, info in results.items():
        if info['min'] is not None:
            status = "✅ 支持"
            min_str = f"{info['min']}"
            max_str = f"{info['max']}"
            cur_str = f"{info['current']:.1f}"
        else:
            status = "❌ 不支持"
            min_str = "N/A"
            max_str = "N/A"
            cur_str = f"{info['current']:.1f}"
        
        print(f"{name:<20} {min_str:<10} {max_str:<10} {cur_str:<10} {status}")
    
    print(f"\n{'='*60}")
    print("建议:")
    print(f"{'='*60}")
    
    # 给出建议
    brightness_info = results.get("亮度 (Brightness)")
    if brightness_info and brightness_info['min'] is not None:
        print(f"✅ 亮度范围: {brightness_info['min']} - {brightness_info['max']}")
        print(f"   建议在代码中使用此范围，而不是 0-100")
    else:
        print(f"❌ 亮度不受支持，建议禁用亮度控制或使用其他方法")
    
    contrast_info = results.get("对比度 (Contrast)")
    if contrast_info and contrast_info['min'] is not None:
        print(f"✅ 对比度范围: {contrast_info['min']} - {contrast_info['max']}")
        print(f"   建议在代码中使用此范围，而不是 0-100")
    else:
        print(f"❌ 对比度不受支持")
    
    print(f"\n提示: 可以使用命令行参数指定摄像头ID:")
    print(f"  python {sys.argv[0]} 0  # 检测摄像头 0")
    print(f"  python {sys.argv[0]} 1  # 检测摄像头 1")


if __name__ == "__main__":
    main()
