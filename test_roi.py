
import sys
import os

# 添加当前目录到 path
sys.path.append(os.getcwd())

from ROI import get_roi_square_points_0_5_17

def test_roi_logic():
    print("Testing ROI logic...")
    
    # 模拟关键点 (WRIST, INDEX_MCP, PINKY_MCP)
    # 假设一个简单的正方形手掌
    p0 = (100, 200)  # WRIST
    p5 = (100, 100)  # INDEX_MCP
    p17 = (200, 100) # PINKY_MCP
    
    points = [p0, p5, p17]
    
    # 测试内接模式 (默认)
    roi_inscribed = get_roi_square_points_0_5_17(points, use_circumscribed=False)
    print(f"Inscribed ROI: {roi_inscribed}")
    
    # 测试外接模式
    roi_circumscribed = get_roi_square_points_0_5_17(points, use_circumscribed=True)
    print(f"Circumscribed ROI: {roi_circumscribed}")
    
    if roi_inscribed and roi_circumscribed:
        print("Both modes returned valid ROI.")
        # 简单验证外接矩形应该比内接矩形大 (或者坐标不同)
        if roi_inscribed != roi_circumscribed:
            print("SUCCESS: Inscribed and Circumscribed ROIs are different.")
        else:
            print("WARNING: ROIs are identical (might be expected depending on geometry, but usually not).")
    else:
        print("FAILURE: One or both modes returned None.")

if __name__ == "__main__":
    try:
        test_roi_logic()
    except Exception as e:
        print(f"Test failed with error: {e}")
