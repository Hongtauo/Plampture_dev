# -*- coding: utf-8 -*-
"""
快照 I/O 模块 - 元数据驱动的版本控制系统
处理快照的加载和保存，使用 snapshots_metadata.json 作为唯一真实来源
类似 Git 的设计理念：所有操作都记录在元数据中
"""

import os
import json
import glob
import cv2
import shutil
import hashlib
from datetime import datetime, timedelta
from loguru import logger

# 导入 ROI 裁剪函数
try:
    from ROI import crop_and_save_roi
    HAS_ROI_UTILS = True
except Exception:
    crop_and_save_roi = None
    HAS_ROI_UTILS = False


def _select_best_hand(hands):
    """从多只手中选择最佳的一只（按 ROI 面积最大）
    
    Args:
        hands: list of hand dicts，每个包含 roi_corners
    
    Returns:
        最佳 hand dict 或 None
    """
    if not hands:
        return None
    
    best_hand = None
    best_area = 0.0
    
    for hand in hands:
        roi_corners = hand.get('roi_corners')
        if not roi_corners or len(roi_corners) != 4:
            continue
        
        # 计算 ROI 面积（使用 Shoelace 公式）
        try:
            import numpy as np
            pts = np.array(roi_corners, dtype=np.float32)
            area = cv2.contourArea(pts)
            if area > best_area:
                best_area = area
                best_hand = hand
        except Exception:
            continue
    
    return best_hand


# 元数据版本号，用于支持未来的格式升级
METADATA_VERSION = "1.0"

# 统一的时间格式常量
METADATA_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # 元数据中的标准时间格式
OPERATION_LOG_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"  # 操作日志的详细时间格式（带毫秒）


def _calculate_file_hash(file_path):
    """
    计算文件的 MD5 哈希值
    
    Args:
        file_path: 文件路径
    
    Returns:
        MD5 哈希值字符串，失败返回 None
    """
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败 {file_path}: {e}")
        return None

def _load_metadata(metadata_file):
    """
    加载元数据文件（带版本检查和错误恢复）
    
    Args:
        metadata_file: 元数据文件路径
    
    Returns:
        元数据字典
    """
    if not os.path.exists(metadata_file):
        logger.info(f"元数据文件不存在，创建新元数据: {metadata_file}")
        return _create_empty_metadata()
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 检查版本
        version = metadata.get("_version", "0.0")
        if version != METADATA_VERSION:
            logger.warning(f"元数据版本不匹配: {version} -> {METADATA_VERSION}，尝试迁移")
            metadata = _migrate_metadata(metadata, version)
        
        # 验证必需字段
        if "_snapshots" not in metadata:
            metadata["_snapshots"] = {}
        if "_deleted_ids" not in metadata:
            metadata["_deleted_ids"] = []
        if "_operation_log" not in metadata:
            metadata["_operation_log"] = []
        
        logger.debug(f"成功加载元数据: {metadata_file}")
        return metadata
        
    except json.JSONDecodeError as e:
        logger.error(f"元数据文件损坏: {e}")
        # 尝试从备份恢复
        backup_file = metadata_file + ".backup"
        if os.path.exists(backup_file):
            logger.info(f"尝试从备份恢复: {backup_file}")
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                logger.info("从备份成功恢复元数据")
                return metadata
            except:
                logger.error("备份文件也损坏")
        
        # 如果无法恢复，创建新元数据
        logger.warning("创建新的空元数据")
        return _create_empty_metadata()
    
    except Exception as e:
        logger.error(f"加载元数据失败: {e}")
        return _create_empty_metadata()


def _create_empty_metadata():
    """
    创建空的元数据结构
    
    Returns:
        空元数据字典
    """
    current_time = datetime.now().strftime(METADATA_TIMESTAMP_FORMAT)
    return {
        "_version": METADATA_VERSION,
        "_created_at": current_time,
        "_last_updated": current_time,
        "_snapshots": {},  # {snapshot_id: {timestamp, user_id, ir_file, rgb_file, ir_hash, rgb_hash, created_at}}
        "_deleted_ids": [],  # 已删除的快照ID列表（保留历史）
        "_operation_log": []  # 操作日志 [{action, snapshot_id, timestamp, details}]
    }


def _migrate_metadata(old_metadata, old_version):
    """
    迁移旧版本元数据到新格式
    
    Args:
        old_metadata: 旧元数据
        old_version: 旧版本号
    
    Returns:
        新格式的元数据
    """
    logger.info(f"迁移元数据从版本 {old_version} 到 {METADATA_VERSION}")
    
    # 创建新元数据结构
    new_metadata = _create_empty_metadata()
    
    # 迁移旧数据（假设旧版本是扁平结构或带索引的结构）
    for key, value in old_metadata.items():
        if key.startswith("_"):
            continue
        
        # 旧版本的 key 可能是 "0001", "0002" 等索引，或者已经是 snapshot_id
        if isinstance(value, dict) and "timestamp" in value:
            # 为旧记录生成 snapshot_id（如果没有）
            snapshot_id = value.get("snapshot_id", key)
            
            new_metadata["_snapshots"][snapshot_id] = {
                "timestamp": value.get("timestamp"),
                "user_id": value.get("user_id"),
                "ir_file": value.get("ir_file"),
                "rgb_file": value.get("rgb_file"),
                "created_at": value.get("created_at", datetime.now().strftime(METADATA_TIMESTAMP_FORMAT)),
                "ir_hash": value.get("ir_hash"),  # 旧版本可能没有
                "rgb_hash": value.get("rgb_hash"),
                "deleted": value.get("deleted", False)
            }
    
    logger.info(f"元数据迁移完成，共迁移 {len(new_metadata['_snapshots'])} 条记录")
    return new_metadata


def _save_metadata(metadata_file, metadata, create_backup=True):
    """
    原子性保存元数据文件（使用临时文件+重命名）
    
    Args:
        metadata_file: 元数据文件路径
        metadata: 元数据字典
        create_backup: 是否创建备份
    
    Returns:
        是否成功
    """
    try:
        # 更新时间戳
        metadata["_last_updated"] = datetime.now().strftime(METADATA_TIMESTAMP_FORMAT)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
        
        # 先写入临时文件
        temp_file = metadata_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # 创建备份（如果原文件存在）
        if create_backup and os.path.exists(metadata_file):
            backup_file = metadata_file + ".backup"
            try:
                shutil.copy2(metadata_file, backup_file)
                logger.debug(f"已创建元数据备份: {backup_file}")
            except Exception as e:
                logger.warning(f"创建备份失败: {e}")
        
        # 原子性重命名
        if os.path.exists(metadata_file):
            os.remove(metadata_file)
        os.rename(temp_file, metadata_file)
        
        logger.debug(f"元数据已保存: {metadata_file}")
        return True
        
    except Exception as e:
        logger.error(f"保存元数据失败: {e}")
        # 清理临时文件
        temp_file = metadata_file + ".tmp"
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        return False


def _add_operation_log(metadata, action, index, details=None):
    """
    添加操作日志到元数据
    
    Args:
        metadata: 元数据字典
        action: 操作类型 (add/delete/modify)
        index: 快照索引
        details: 额外详情
    """
    log_entry = {
        "action": action,
        "index": str(index) if isinstance(index, int) else index,
        "timestamp": datetime.now().strftime(OPERATION_LOG_TIMESTAMP_FORMAT)[:-3],  # 截取到毫秒
        "details": details or {}
    }
    
    if "_operation_log" not in metadata:
        metadata["_operation_log"] = []
    
    metadata["_operation_log"].append(log_entry)
    
    # 限制日志长度（保留最近1000条）
    if len(metadata["_operation_log"]) > 1000:
        metadata["_operation_log"] = metadata["_operation_log"][-1000:]


def cleanup_old_deleted_records(project_dir, days_to_keep=3):
    """
    清理超过指定天数的已删除记录（在程序退出时自动调用）
    
    Args:
        project_dir: 项目目录
        days_to_keep: 保留多少天内的删除记录（默认3天）
    
    Returns:
        清理的记录数
    """
    if not project_dir:
        logger.warning("未设置项目目录，无法清理已删除记录")
        return 0
    
    snapshots_dir = os.path.join(project_dir, "snapshots")
    if not os.path.exists(snapshots_dir):
        return 0
    
    # 计算截止时间
    cutoff_datetime = datetime.now() - timedelta(days=days_to_keep)
    
    total_cleaned = 0
    
    # 遍历所有用户目录
    try:
        for user_id in os.listdir(snapshots_dir):
            user_dir = os.path.join(snapshots_dir, user_id)
            if not os.path.isdir(user_dir):
                continue
            
            metadata_file = os.path.join(user_dir, "snapshots_metadata.json")
            if not os.path.exists(metadata_file):
                continue
            
            # 加载元数据
            metadata = _load_metadata(metadata_file)
            
            # 查找需要清理的记录
            snapshots_to_remove = []
            for snapshot_id, snap_meta in metadata.get("_snapshots", {}).items():
                # 只处理已删除的记录
                if not snap_meta.get("deleted", False):
                    continue
                
                deleted_at_str = snap_meta.get("deleted_at")
                if not deleted_at_str:
                    # 如果没有删除时间，跳过（保留）
                    continue
                
                # 尝试解析删除时间（支持多种格式）
                deleted_datetime = None
                for fmt in [METADATA_TIMESTAMP_FORMAT, OPERATION_LOG_TIMESTAMP_FORMAT]:
                    try:
                        deleted_datetime = datetime.strptime(deleted_at_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if deleted_datetime is None:
                    logger.warning(f"无法解析删除时间: {deleted_at_str}，跳过快照 {snapshot_id}")
                    continue
                
                # 比较 datetime 对象
                if deleted_datetime < cutoff_datetime:
                    snapshots_to_remove.append(snapshot_id)
            
            # 从元数据中移除旧的删除记录
            if snapshots_to_remove:
                for snapshot_id in snapshots_to_remove:
                    del metadata["_snapshots"][snapshot_id]
                    
                    # 从 _deleted_ids 中也移除
                    if snapshot_id in metadata.get("_deleted_ids", []):
                        metadata["_deleted_ids"].remove(snapshot_id)
                
                # 记录清理操作
                _add_operation_log(metadata, "cleanup", f"batch_{len(snapshots_to_remove)}", {
                    "cleaned_count": len(snapshots_to_remove),
                    "cutoff_date": cutoff_datetime.strftime(METADATA_TIMESTAMP_FORMAT),
                    "snapshot_ids": snapshots_to_remove[:10]  # 只记录前10个
                })
                
                # 保存更新后的元数据
                if _save_metadata(metadata_file, metadata):
                    total_cleaned += len(snapshots_to_remove)
                    logger.info(f"用户 {user_id} 清理了 {len(snapshots_to_remove)} 条旧的删除记录（>{days_to_keep}天）")
                else:
                    logger.error(f"保存清理后的元数据失败: {metadata_file}")
    
    except Exception as e:
        logger.error(f"清理已删除记录时出错: {e}")
    
    if total_cleaned > 0:
        logger.info(f"清理完成，共清理 {total_cleaned} 条超过 {days_to_keep} 天的删除记录")
    else:
        logger.debug("没有需要清理的旧删除记录")
    
    return total_cleaned


def delete_snapshot_files(file_paths):
    """
    删除指定的快照文件，并在元数据中标记为已删除（不删除记录，保留历史）
    
    Args:
        file_paths: 要删除的文件路径列表
    
    Returns:
        删除成功的数量
    """
    if not file_paths:
        return 0
    
    logger.info(f"准备删除 {len(file_paths)} 个文件")
    
    # 按用户分组文件路径
    user_files = {}
    for file_path in file_paths:
        if not file_path:
            continue
            
        # 提取用户ID和快照ID
        try:
            parent_dir = os.path.dirname(file_path)  # .../user_id/ir 或 .../user_id/rgb
            user_dir = os.path.dirname(parent_dir)  # .../user_id
            user_id = os.path.basename(user_dir)
            filename = os.path.basename(file_path)
            
            # 文件名格式: {snapshot_id}.bmp
            name, ext = os.path.splitext(filename)
            if ext.lower() != '.bmp':
                logger.warning(f"跳过非BMP文件: {file_path}")
                continue
            snapshot_id = name
            
            if user_id not in user_files:
                user_files[user_id] = {
                    'dir': user_dir,
                    'snapshot_ids': set(),
                    'files': []
                }
            user_files[user_id]['snapshot_ids'].add(snapshot_id)
            user_files[user_id]['files'].append(file_path)
        except Exception as e:
            logger.error(f"解析文件路径失败 {file_path}: {e}")
            continue
    
    deleted_count = 0
    
    # 删除文件并更新元数据
    for user_id, info in user_files.items():
        user_dir = info['dir']
        metadata_file = os.path.join(user_dir, "snapshots_metadata.json")
        
        # 加载元数据
        metadata = _load_metadata(metadata_file)
        
        # 删除物理文件
        for file_path in info['files']:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"已删除文件: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"删除文件失败 {file_path}: {e}")
        
        # 在元数据中标记为已删除（保留记录）
        for snapshot_id in info['snapshot_ids']:
            if "_snapshots" in metadata and snapshot_id in metadata["_snapshots"]:
                # 标记为已删除
                metadata["_snapshots"][snapshot_id]["deleted"] = True
                metadata["_snapshots"][snapshot_id]["deleted_at"] = datetime.now().strftime(METADATA_TIMESTAMP_FORMAT)
                
                # 添加到已删除列表
                if "_deleted_ids" not in metadata:
                    metadata["_deleted_ids"] = []
                if snapshot_id not in metadata["_deleted_ids"]:
                    metadata["_deleted_ids"].append(snapshot_id)
                
                # 记录操作日志
                _add_operation_log(metadata, "delete", snapshot_id, {
                    "user_id": user_id,
                    "files": [f for f in info['files'] if snapshot_id in f]
                })
                
                logger.debug(f"在元数据中标记删除: {snapshot_id}")
        
        # 保存更新后的元数据
        if not _save_metadata(metadata_file, metadata):
            logger.error(f"保存元数据失败: {metadata_file}")
    
    logger.info(f"删除操作完成，共删除 {deleted_count} 个文件")
    return deleted_count


def load_snapshot_logs(project_dir):
    """
    加载快照日志文件
    
    Args:
        project_dir: 项目目录
    
    Returns:
        用户快照计数器字典
    """
    if not project_dir:
        return {}
    
    snapshots_dir = os.path.join(project_dir, "snapshots")
    logs_file = os.path.join(snapshots_dir, "snapshot_logs.json")
    
    if os.path.exists(logs_file):
        try:
            with open(logs_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            user_counters = logs.get("user_counters", {})
            logger.info(f"已加载快照日志: {len(user_counters)} 个用户")
            return user_counters
        except Exception as e:
            logger.error(f"加载快照日志失败: {e}")
            return {}
    else:
        logger.info("快照日志文件不存在，创建新日志")
        return {}


def save_snapshot_logs(project_dir, user_counters):
    """
    保存快照日志文件
    
    Args:
        project_dir: 项目目录
        user_counters: 用户快照计数器字典
    """
    if not project_dir:
        logger.warning("未设置项目目录，无法保存快照日志")
        return
    
    snapshots_dir = os.path.join(project_dir, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    
    logs_file = os.path.join(snapshots_dir, "snapshot_logs.json")
    
    logs = {
        "user_counters": user_counters,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        with open(logs_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        logger.info(f"快照日志已保存: {logs_file}")
    except Exception as e:
        logger.error(f"保存快照日志失败: {e}")


def save_user_snapshots(project_dir, user_id, snapshots, user_counters):
    """
    保存用户的所有快照到磁盘（元数据驱动，原子性操作）
    新文件结构: workspace/{project}/snapshots/{user_id}/ir/{snapshot_id}.bmp
                                                        /rgb/{snapshot_id}.bmp
    
    Args:
        project_dir: 项目目录
        user_id: 用户ID
        snapshots: 快照列表
        user_counters: 用户快照计数器字典（已弃用，保留兼容性）
    
    Returns:
        (是否成功, 保存的数量)
    """
    if not project_dir:
        logger.error("未设置项目目录，无法保存快照")
        return False, 0
    
    if not snapshots:
        logger.warning(f"用户 {user_id} 没有快照需要保存")
        return True, 0
    
    # 筛选出未保存的快照
    unsaved_snapshots = [s for s in snapshots if not s.is_saved]
    
    if not unsaved_snapshots:
        logger.info(f"用户 {user_id} 的所有快照都已保存，无需重复保存")
        return True, 0
    
    # 用户快照保存目录
    user_snapshots_dir = os.path.join(project_dir, "snapshots", user_id)
    ir_dir = os.path.join(user_snapshots_dir, "ir")
    rgb_dir = os.path.join(user_snapshots_dir, "rgb")
    
    # 创建目录结构
    os.makedirs(ir_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)
    
    # 加载元数据
    metadata_file = os.path.join(user_snapshots_dir, "snapshots_metadata.json")
    metadata = _load_metadata(metadata_file)
    
    logger.info(f"用户 {user_id} 准备保存 {len(unsaved_snapshots)} 张新快照")
    
    saved_count = 0
    failed_snapshots = []
    successfully_saved_files = []  # 记录成功保存的文件，用于可能的回滚
    
    for snapshot in unsaved_snapshots:
        snapshot_id = snapshot.snapshot_id
        
        if not snapshot_id:
            logger.error(f"快照缺少 snapshot_id，跳过")
            failed_snapshots.append("NO_ID")
            continue
        
        # 检查ID是否已被使用
        if snapshot_id in metadata.get("_snapshots", {}):
            logger.warning(f"快照ID {snapshot_id} 已存在，跳过")
            failed_snapshots.append(snapshot_id)
            continue
        
        # 保存 IR 图像（ROI 裁剪）
        ir_path = None
        ir_hash = None
        ir_roi_saved = False
        if snapshot.ir_frame is not None:
            ir_filename = f"{snapshot_id}.bmp"  # 使用 BMP 保存
            ir_path = os.path.join(ir_dir, ir_filename)
            try:
                # 尝试从检测结果中提取 IR ROI
                roi_saved = False
                logger.info(f"IR 保存检查: HAS_ROI_UTILS={HAS_ROI_UTILS}, detection_result={snapshot.detection_result is not None}")
                if HAS_ROI_UTILS and crop_and_save_roi and hasattr(snapshot, 'detection_result') and snapshot.detection_result:
                    ir_detection = snapshot.detection_result.get('ir_detection', {})
                    hands = ir_detection.get('hands', [])
                    logger.info(f"IR 检测结果: {len(hands)} 只手")
                    if hands:
                        # 选择面积最大的手
                        hand = _select_best_hand(hands)
                        if hand:
                            roi_corners = hand.get('roi_corners')
                            logger.info(f"IR ROI corners: {roi_corners}")
                            if roi_corners and len(roi_corners) == 4:
                                # crop_and_save_roi 期望 RGB 输入，需要转换
                                ir_rgb = cv2.cvtColor(snapshot.ir_frame, cv2.COLOR_BGR2RGB)
                                # 使用 ROI.crop_and_save_roi 裁剪并保存（自动旋转对齐）
                                roi_img = crop_and_save_roi(ir_rgb, roi_corners, ir_path)
                                if roi_img is not None:
                                    roi_saved = True
                                    ir_roi_saved = True
                                    logger.info(f"已保存 IR ROI 图像 ({len(hands)}只手): ir/{ir_filename}")
                                else:
                                    logger.warning(f"IR ROI 裁剪失败，将保存全图")
                
                # 回退：如果没有检测结果，保存全图
                if not roi_saved:
                    success = cv2.imwrite(ir_path, snapshot.ir_frame)
                    if not success:
                        raise Exception("cv2.imwrite 返回 False")
                    logger.debug(f"已保存 IR 全图（无检测结果）: ir/{ir_filename}")
                
                # 计算文件哈希
                ir_hash = _calculate_file_hash(ir_path)
                snapshot.ir_file_path = ir_path
            except Exception as e:
                logger.error(f"保存 IR 图像失败: {e}")
                # 清理可能的不完整文件
                if os.path.exists(ir_path):
                    try:
                        os.remove(ir_path)
                    except:
                        pass
                failed_snapshots.append(snapshot_id)
                continue
        
        # 保存 RGB 图像（ROI 裁剪）
        rgb_path = None
        rgb_hash = None
        rgb_roi_saved = False
        if snapshot.rgb_frame is not None:
            rgb_filename = f"{snapshot_id}.bmp"  # 使用 BMP 保存
            rgb_path = os.path.join(rgb_dir, rgb_filename)
            try:
                # 尝试从检测结果中提取 RGB ROI
                roi_saved = False
                logger.info(f"RGB 保存检查: HAS_ROI_UTILS={HAS_ROI_UTILS}, detection_result={snapshot.detection_result is not None}")
                if HAS_ROI_UTILS and crop_and_save_roi and hasattr(snapshot, 'detection_result') and snapshot.detection_result:
                    rgb_detection = snapshot.detection_result.get('rgb_detection', {})
                    hands = rgb_detection.get('hands', [])
                    logger.info(f"RGB 检测结果: {len(hands)} 只手")
                    if hands:
                        # 选择面积最大的手
                        hand = _select_best_hand(hands)
                        if hand:
                            roi_corners = hand.get('roi_corners')
                            logger.info(f"RGB ROI corners: {roi_corners}")
                            if roi_corners and len(roi_corners) == 4:
                                # crop_and_save_roi 期望 RGB 输入，需要转换
                                rgb_rgb = cv2.cvtColor(snapshot.rgb_frame, cv2.COLOR_BGR2RGB)
                                # 使用 ROI.crop_and_save_roi 裁剪并保存（自动旋转对齐）
                                roi_img = crop_and_save_roi(rgb_rgb, roi_corners, rgb_path)
                                if roi_img is not None:
                                    roi_saved = True
                                    rgb_roi_saved = True
                                    logger.info(f"已保存 RGB ROI 图像 ({len(hands)}只手): rgb/{rgb_filename}")
                                else:
                                    logger.warning(f"RGB ROI 裁剪失败，将保存全图")
                                    logger.debug(f"已保存 RGB ROI 图像: rgb/{rgb_filename}")
                
                # 回退：如果没有检测结果，保存全图
                if not roi_saved:
                    success = cv2.imwrite(rgb_path, snapshot.rgb_frame)
                    if not success:
                        raise Exception("cv2.imwrite 返回 False")
                    logger.debug(f"已保存 RGB 全图（无检测结果）: rgb/{rgb_filename}")
                
                # 计算文件哈希
                rgb_hash = _calculate_file_hash(rgb_path)
                snapshot.rgb_file_path = rgb_path
            except Exception as e:
                logger.error(f"保存 RGB 图像失败: {e}")
                # 清理可能的不完整文件
                if os.path.exists(rgb_path):
                    try:
                        os.remove(rgb_path)
                    except:
                        pass
                # 如果RGB保存失败，也要删除已保存的IR
                if ir_path and os.path.exists(ir_path):
                    try:
                        os.remove(ir_path)
                        logger.warning(f"回滚: 已删除 {ir_path}")
                    except:
                        pass
                failed_snapshots.append(snapshot_id)
                continue
        
        # 记录成功保存的文件（用于可能的回滚）
        if ir_path:
            successfully_saved_files.append(ir_path)
        if rgb_path:
            successfully_saved_files.append(rgb_path)
        
        # 添加到元数据（以snapshot_id为键）
        if "_snapshots" not in metadata:
            metadata["_snapshots"] = {}
        
        metadata["_snapshots"][snapshot_id] = {
            "timestamp": snapshot.timestamp,
            "user_id": snapshot.user_id,
            "ir_file": f"ir/{snapshot_id}.bmp" if ir_path else None,
            "rgb_file": f"rgb/{snapshot_id}.bmp" if rgb_path else None,
            "ir_hash": ir_hash,
            "rgb_hash": rgb_hash,
            "ir_roi_saved": ir_roi_saved,  # 标记是否保存了 ROI
            "rgb_roi_saved": rgb_roi_saved,
            "hand": snapshot.hand if hasattr(snapshot, 'hand') else None,
            "created_at": datetime.now().strftime(METADATA_TIMESTAMP_FORMAT),
            "deleted": False
        }
        
        # 记录操作日志
        _add_operation_log(metadata, "add", snapshot_id, {
            "user_id": user_id,
            "timestamp": snapshot.timestamp,
            "ir_file": f"ir/{snapshot_id}.bmp" if ir_path else None,
            "rgb_file": f"rgb/{snapshot_id}.bmp" if rgb_path else None,
            "ir_roi_saved": ir_roi_saved,
            "rgb_roi_saved": rgb_roi_saved
        })
        
        # 标记为已保存
        snapshot.is_saved = True
        saved_count += 1
    
    # 保存元数据
    if not _save_metadata(metadata_file, metadata):
        logger.error(f"保存元数据失败: {metadata_file}")
        
        # 回滚：删除所有已保存的图像文件
        logger.warning(f"开始回滚操作：删除 {len(successfully_saved_files)} 个已保存的文件")
        rollback_count = 0
        for file_path in successfully_saved_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    rollback_count += 1
                    logger.debug(f"回滚删除: {file_path}")
            except Exception as e:
                logger.error(f"回滚删除文件失败 {file_path}: {e}")
        
        logger.warning(f"回滚完成：已删除 {rollback_count}/{len(successfully_saved_files)} 个文件")
        
        # 恢复 is_saved 状态
        for snapshot in unsaved_snapshots:
            snapshot.is_saved = False
        
        return False, 0
    
    # 为了兼容性，更新 user_counters（虽然不再使用索引）
    if user_counters is not None:
        user_counters[user_id] = len(metadata.get("_snapshots", {}))
        save_snapshot_logs(project_dir, user_counters)
    
    if failed_snapshots:
        logger.warning(f"部分快照保存失败: {failed_snapshots[:5]}...")
    
    logger.info(f"用户 {user_id} 的 {saved_count} 张新快照已保存到 {user_snapshots_dir}")
    logger.info(f"文件结构: ir/ 和 rgb/ 子目录，文件名为快照ID")
    
    return True, saved_count


def load_user_snapshots(project_dir, user_id):
    """
    加载指定用户的历史快照信息（完全基于元数据，不依赖文件扫描）
    新文件结构: workspace/{project}/snapshots/{user_id}/ir/{snapshot_id}.bmp
                                                        /rgb/{snapshot_id}.bmp
    
    Args:
        project_dir: 项目目录
        user_id: 用户ID
    
    Returns:
        (快照信息列表[(ir_path, rgb_path, timestamp, snapshot_id)], 快照总数)
    """
    if not project_dir:
        logger.error("未设置项目目录，无法加载快照")
        return [], 0
    
    user_snapshots_dir = os.path.join(project_dir, "snapshots", user_id)
    
    if not os.path.exists(user_snapshots_dir):
        logger.info(f"用户 {user_id} 没有历史快照目录")
        return [], 0
    
    # 加载元数据（这是唯一真实来源）
    metadata_file = os.path.join(user_snapshots_dir, "snapshots_metadata.json")
    metadata = _load_metadata(metadata_file)
    
    # 从元数据构建快照列表（只加载未删除的）
    snapshot_files = []
    missing_files = []
    corrupted_files = []
    
    snapshots_data = metadata.get("_snapshots", {})
    if not snapshots_data:
        logger.info(f"用户 {user_id} 的元数据中没有快照记录")
        return [], 0
    
    # 按创建时间排序（或按 snapshot_id）
    sorted_snapshots = sorted(snapshots_data.items(), 
                             key=lambda x: x[1].get("created_at", ""))
    
    for snapshot_id, snap_meta in sorted_snapshots:
        # 跳过已删除的快照
        if snap_meta.get("deleted", False):
            logger.debug(f"跳过已删除的快照: {snapshot_id}")
            continue
        
        ir_file = snap_meta.get("ir_file")  # 格式: ir/{snapshot_id}.bmp
        rgb_file = snap_meta.get("rgb_file")  # 格式: rgb/{snapshot_id}.bmp
        timestamp = snap_meta.get("timestamp")

        # 构建完整路径
        ir_path = os.path.join(user_snapshots_dir, ir_file) if ir_file else None
        rgb_path = os.path.join(user_snapshots_dir, rgb_file) if rgb_file else None
        
        # 验证文件存在性
        ir_exists = ir_path and os.path.exists(ir_path)
        rgb_exists = rgb_path and os.path.exists(rgb_path)
        
        if not ir_exists and not rgb_exists:
            logger.warning(f"快照 {snapshot_id} 的文件丢失: IR={ir_file}, RGB={rgb_file}")
            missing_files.append(snapshot_id)
            continue
        
        # 可选：验证文件哈希完整性
        if ir_exists and "ir_hash" in snap_meta and snap_meta["ir_hash"]:
            actual_hash = _calculate_file_hash(ir_path)
            if actual_hash != snap_meta["ir_hash"]:
                logger.error(f"IR 文件哈希不匹配: {snapshot_id}, 预期={snap_meta['ir_hash'][:8]}..., 实际={actual_hash[:8] if actual_hash else 'None'}...")
                corrupted_files.append((snapshot_id, "IR"))
        
        if rgb_exists and "rgb_hash" in snap_meta and snap_meta["rgb_hash"]:
            actual_hash = _calculate_file_hash(rgb_path)
            if actual_hash != snap_meta["rgb_hash"]:
                logger.error(f"RGB 文件哈希不匹配: {snapshot_id}, 预期={snap_meta['rgb_hash'][:8]}..., 实际={actual_hash[:8] if actual_hash else 'None'}...")
                corrupted_files.append((snapshot_id, "RGB"))
        
        # 添加到结果列表（包含 snapshot_id 和 hand）
        hand = snap_meta.get("hand") if isinstance(snap_meta, dict) else None
        snapshot_files.append((
            ir_path if ir_exists else None,
            rgb_path if rgb_exists else None,
            timestamp,
            snapshot_id,  # 返回 snapshot_id
            hand
        ))
    
    # 报告问题
    if missing_files:
        logger.warning(f"发现 {len(missing_files)} 个快照的文件丢失: {missing_files[:5]}...")
    if corrupted_files:
        logger.error(f"发现 {len(corrupted_files)} 个文件损坏: {corrupted_files[:5]}...")
    
    total_snapshots = len(snapshots_data)
    active_snapshots = len(snapshot_files)
    
    logger.info(f"从元数据加载用户 {user_id} 的 {active_snapshots} 张活跃快照（元数据总数: {total_snapshots}）")
    logger.debug(f"已删除快照数: {len(metadata.get('_deleted_ids', []))}")
    
    # 返回快照数量（返回元数据总条目数，与 user_snapshot_counter 语义一致）
    return snapshot_files, total_snapshots
