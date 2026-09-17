# -*- coding: utf-8 -*-
"""
导出模块 - 将项目快照导出到指定目录
"""
import os
import shutil
from loguru import logger


def export_project_snapshots(project_dir, project_name, export_base_dir, snapshot_io_module):
    """
    导出项目的所有快照到指定目录
    
    目标文件结构（每个 user 按 hand 分为同级目录）:
    <export_base_dir>/
        <project_name>/
            <personID>-left/
                ir/
                    0.bmp
                    1.bmp
                    ...
                rgb/
                    0.bmp
                    1.bmp
                    ...
            <personID>-right/
                ir/
                rgb/
            <personID>-unknown/  # hand 字段为空或未知时
    
    Args:
        project_dir: 项目目录路径
        project_name: 项目名称
        export_base_dir: 导出基础目录
        snapshot_io_module: snapshot_io 模块引用
    
    Returns:
        (是否成功, 统计信息字典)
    """
    try:
        # 先执行清理操作
        logger.info("执行旧记录清理...")
        cleaned_count = snapshot_io_module.cleanup_old_deleted_records(project_dir, days_to_keep=3)
        if cleaned_count > 0:
            logger.info(f"已清理 {cleaned_count} 条旧删除记录")
        
        # 读取所有用户的快照
        snapshots_dir = os.path.join(project_dir, "snapshots")
        if not os.path.exists(snapshots_dir):
            logger.warning(f"项目没有快照目录: {snapshots_dir}")
            return False, {"error": "没有快照数据"}
        
        # 创建导出根目录（project_name 作为导出根）
        # 最终在该目录下直接创建 <personID>-left / <personID>-right 等目录
        export_project_dir = os.path.join(export_base_dir, project_name)
        os.makedirs(export_project_dir, exist_ok=True)
        logger.info(f"创建导出项目目录: {export_project_dir}")
        
        # 统计信息
        stats = {
            "total_users": 0,
            "total_snapshots": 0,
            "total_files": 0,
            "export_path": export_project_dir
        }
        
        # 在导出根目录下创建按类型的根目录（ir / rgb）
        export_ir_root = os.path.join(export_project_dir, "ir")
        export_rgb_root = os.path.join(export_project_dir, "rgb")
        os.makedirs(export_ir_root, exist_ok=True)
        os.makedirs(export_rgb_root, exist_ok=True)

        # 遍历所有用户目录
        for user_id in os.listdir(snapshots_dir):
            user_dir = os.path.join(snapshots_dir, user_id)
            if not os.path.isdir(user_dir):
                continue
            
            metadata_file = os.path.join(user_dir, "snapshots_metadata.json")
            if not os.path.exists(metadata_file):
                logger.warning(f"用户 {user_id} 没有元数据文件，跳过")
                continue
            
            # 加载元数据
            metadata = snapshot_io_module._load_metadata(metadata_file)
            snapshots_data = metadata.get("_snapshots", {})
            
            if not snapshots_data:
                logger.info(f"用户 {user_id} 没有快照数据，跳过")
                continue
            
            logger.info(f"处理用户: {user_id}")

            # 按创建时间排序快照
            sorted_snapshots = sorted(
                snapshots_data.items(),
                key=lambda x: x[1].get("created_at", "")
            )

            # 为每种 hand 创建独立计数器和目录（按 hand 分组导出）
            # key: hand_label (left/right/unknown) -> counters
            hand_stats = {}

            # 复制文件并重命名（分 hand）
            for snapshot_id, snap_meta in sorted_snapshots:
                # 跳过已删除的快照
                if snap_meta.get("deleted", False):
                    continue

                # 读取 hand 字段，缺失或非 left/right 视作 unknown
                hand_label = snap_meta.get("hand") or "unknown"
                if hand_label not in ("left", "right"):
                    hand_label = "unknown"

                # 确保为该 hand 初始化统计和目标目录（在 ir/ 或 rgb/ 下按 userID-hand 分组）
                if hand_label not in hand_stats:
                    hand_stats[hand_label] = {
                        "ir_counter": 0,
                        "rgb_counter": 0,
                        "snapshot_count": 0,
                        # 每种类型的目标目录
                        "export_ir_dir": os.path.join(export_ir_root, f"{user_id}-{hand_label}"),
                        "export_rgb_dir": os.path.join(export_rgb_root, f"{user_id}-{hand_label}"),
                    }
                    os.makedirs(hand_stats[hand_label]["export_ir_dir"], exist_ok=True)
                    os.makedirs(hand_stats[hand_label]["export_rgb_dir"], exist_ok=True)

                export_ir_dir = hand_stats[hand_label]["export_ir_dir"]
                export_rgb_dir = hand_stats[hand_label]["export_rgb_dir"]

                ir_file = snap_meta.get("ir_file")  # 格式: ir/{snapshot_id}.bmp
                rgb_file = snap_meta.get("rgb_file")

                # 处理 IR 文件（复制到 export_project_dir/ir/<userID>-hand/）
                if ir_file:
                    src_ir_path = os.path.join(user_dir, ir_file)
                    if os.path.exists(src_ir_path):
                        dst_ir_path = os.path.join(export_ir_dir, f"{hand_stats[hand_label]['ir_counter']}.bmp")
                        shutil.copy2(src_ir_path, dst_ir_path)
                        hand_stats[hand_label]["ir_counter"] += 1
                        stats["total_files"] += 1
                    else:
                        logger.warning(f"IR 文件不存在: {src_ir_path}")

                # 处理 RGB 文件（复制到 export_project_dir/rgb/<userID>-hand/）
                if rgb_file:
                    src_rgb_path = os.path.join(user_dir, rgb_file)
                    if os.path.exists(src_rgb_path):
                        dst_rgb_path = os.path.join(export_rgb_dir, f"{hand_stats[hand_label]['rgb_counter']}.bmp")
                        shutil.copy2(src_rgb_path, dst_rgb_path)
                        hand_stats[hand_label]["rgb_counter"] += 1
                        stats["total_files"] += 1
                    else:
                        logger.warning(f"RGB 文件不存在: {src_rgb_path}")

                hand_stats[hand_label]["snapshot_count"] += 1

            # 汇总并记录每个 hand 的导出结果
            total_user_snapshots = 0
            total_ir = 0
            total_rgb = 0
            for hand_label, hs in hand_stats.items():
                logger.info(f"用户 {user_id} ({hand_label}) 导出完成: {hs['snapshot_count']} 个快照, IR={hs['ir_counter']}, RGB={hs['rgb_counter']}")
                total_user_snapshots += hs["snapshot_count"]
                total_ir += hs["ir_counter"]
                total_rgb += hs["rgb_counter"]

            stats["total_users"] += 1
            stats["total_snapshots"] += total_user_snapshots
        
        logger.info(f"导出完成: {stats['total_users']} 个用户, {stats['total_snapshots']} 个快照, {stats['total_files']} 个文件")
        return True, stats
        
    except Exception as e:
        logger.error(f"导出失败: {e}", exc_info=True)
        return False, {"error": str(e)}
