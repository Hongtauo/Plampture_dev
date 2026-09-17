# -*- coding: utf-8 -*-
"""
摄像头属性范围快速检测 - 自动化版本
"""

import cv2

def quick_detect(camera_id):
    """快速检测摄像头属性范围"""
    print(f"检测摄像头 {camera_id}...")
    
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        print(f"❌ 无法打开摄像头 {camera_id}")
        return
    
    # 测试亮度
    print(f"\n{'='*50}")
    print("亮度 (CAP_PROP_BRIGHTNESS) 测试:")
    print(f"{'='*50}")
    
    test_values = [0, 10, 20, 30, 40, 50, 60, 64, 70, 80, 90, 100]
    valid_brightness = []
    
    for val in test_values:
        cap.set(cv2.CAP_PROP_BRIGHTNESS, val)
        actual = cap.get(cv2.CAP_PROP_BRIGHTNESS)
        is_valid = abs(actual - val) < 5
        status = "✅" if is_valid else "❌"
        print(f"  设置 {val:3d} -> 实际 {actual:6.1f} {status}")
        if is_valid:
            valid_brightness.append(val)
    
    if valid_brightness:
        print(f"\n✅ 亮度有效范围: {min(valid_brightness)} - {max(valid_brightness)}")
    else:
        print(f"\n❌ 亮度不受支持")
    
    # 测试对比度
    print(f"\n{'='*50}")
    print("对比度 (CAP_PROP_CONTRAST) 测试:")
    print(f"{'='*50}")
    
    valid_contrast = []
    for val in test_values:
        cap.set(cv2.CAP_PROP_CONTRAST, val)
        actual = cap.get(cv2.CAP_PROP_CONTRAST)
        is_valid = abs(actual - val) < 5
        status = "✅" if is_valid else "❌"
        print(f"  设置 {val:3d} -> 实际 {actual:6.1f} {status}")
        if is_valid:
            valid_contrast.append(val)
    
    if valid_contrast:
        print(f"\n✅ 对比度有效范围: {min(valid_contrast)} - {max(valid_contrast)}")
    else:
        print(f"\n❌ 对比度不受支持")
    
    cap.release()
    
    # 输出建议
    print(f"\n{'='*50}")
    print("建议:")
    print(f"{'='*50}")
    
    if valid_brightness:
        max_b = max(valid_brightness)
        if max_b < 100:
            print(f"⚠️  亮度最大值是 {max_b}，不是 100！")
            print(f"   需要修改映射逻辑: 0-100% -> 0-{max_b}")
    
    if valid_contrast:
        max_c = max(valid_contrast)
        if max_c < 100:
            print(f"⚠️  对比度最大值是 {max_c}，不是 100！")
            print(f"   需要修改映射逻辑: 0-100% -> 0-{max_c}")


if __name__ == "__main__":
    print("="*50)
    print("摄像头属性范围快速检测")
    print("="*50)
    
    # 检测摄像头 0 和 1
    for cam_id in [0, 1]:
        quick_detect(cam_id)
        print("\n")
