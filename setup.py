# -*- coding: utf-8 -*-

import sys
import os
import json
import uuid
import shutil
from datetime import datetime
from PySide6.QtWidgets import QApplication, QWidget, QInputDialog, QMessageBox, QListWidgetItem, QMenu
from PySide6.QtGui import QIcon, QFont, QAction
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from Setup_ui import Ui_setup_form
from loguru import logger
import subprocess

# 获取应用程序根目录（兼容exe打包）
def get_app_dir():
    """获取应用程序根目录，兼容开发环境和打包后的exe环境"""
    if getattr(sys, 'frozen', False):
        # 打包为exe后，使用exe所在目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境，使用脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

# 全局图标路径（使用函数后调用）
def get_info_icon_path():
    return os.path.join(get_app_dir(), "icon", "info.ico")

INFO_ICON_PATH = None  # 延迟初始化

def get_message_box_icon():
    """获取消息框图标"""
    icon_path = get_info_icon_path()
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    return QIcon()


def show_text_input_dialog_with_icon(parent, title, label, text=""):
    """显示带图标的文本输入对话框"""
    dialog = QInputDialog(parent)
    dialog.setWindowIcon(get_message_box_icon())
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextValue(text)
    
    ok = dialog.exec()
    result = dialog.textValue()
    return result, ok


class SetupWindow(QWidget):
    """项目设置/启动窗口"""
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_setup_form()
        self.ui.setupUi(self)
        
        # 工作区目录（使用兼容函数）
        self.app_dir = get_app_dir()
        self.workspace_dir = os.path.join(self.app_dir, "workspace")
        self.workspace_logs_file = os.path.join(self.workspace_dir, "workspace_logs.json")
        self.show_signal_file = os.path.join(self.workspace_dir, ".show_setup_signal")
        
        # 确保工作区目录存在
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # 设置列表控件样式和右键菜单
        self.setup_list_widget_style()
        self.setup_context_menu()
        
        # 初始化
        self.init_workspace_logs()
        self.load_project_list()
        self.connect_signals()
        
        # 初始化导出按钮状态（默认禁用）
        self.ui.export_Button.setEnabled(False)
        
        # 标志位：区分隐藏和关闭
        self.is_hiding = False
        
        # 设置文件监控器，监听显示信号
        self.setup_file_watcher()
        
        logger.info("项目设置窗口已初始化")
    
    def setup_list_widget_style(self):
        """设置项目列表控件的样式"""
        # 设置列表项的间距
        self.ui.proj_listWidget.setSpacing(5)
        
        # 设置样式表 - 移除焦点框
        self.ui.proj_listWidget.setStyleSheet("""
            QListWidget {
                outline: none;
            }
            QListWidget::item {
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 10px;
                margin: 2px;
                outline: none;
            }
            QListWidget::item:selected {
                border: 2px solid #2196f3;
                background-color: palette(highlight);
                color: palette(text);
                outline: none;
            }
            QListWidget::item:focus {
                outline: none;
            }
        """)
        
        logger.debug("列表控件样式已设置")
    
    def setup_context_menu(self):
        """设置右键菜单"""
        self.ui.proj_listWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.proj_listWidget.customContextMenuRequested.connect(self.show_context_menu)
        logger.debug("右键菜单已设置")
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        if self.is_hiding:
            # 如果是程序隐藏窗口，只是隐藏，不退出
            logger.info("窗口被隐藏（程序继续运行）")
            self.is_hiding = False
            event.ignore()
            self.hide()
        else:
            # 如果是用户主动关闭，退出应用程序
            logger.info("用户关闭窗口，程序退出")
            self.check_timer.stop()
            QApplication.quit()
            event.accept()
    
    def setup_file_watcher(self):
        """设置文件监控器，监听来自main.py的显示信号"""
        # 使用定时器定期检查信号文件
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_show_signal)
        self.check_timer.start(500)  # 每500ms检查一次
        logger.debug("文件监控器已设置")
    
    def check_show_signal(self):
        """检查是否有显示窗口的信号"""
        if os.path.exists(self.show_signal_file):
            logger.info("收到显示窗口信号")
            # 删除信号文件
            try:
                os.remove(self.show_signal_file)
            except:
                pass
            
            # 重置隐藏标志（重新显示后允许用户关闭退出）
            self.is_hiding = False
            
            # 刷新项目列表
            self.load_project_list()
            
            # 显示并激活窗口
            self.show()
            self.raise_()
            self.activateWindow()
            logger.info("窗口已重新显示")
    
    def show_context_menu(self, pos):
        """显示右键菜单"""
        item = self.ui.proj_listWidget.itemAt(pos)
        if item is None:
            return
        
        # 创建菜单
        menu = QMenu(self)
        
        # 添加删除动作
        delete_action = QAction("删除项目", self)
        delete_action.triggered.connect(lambda: self.delete_project(item))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(self.ui.proj_listWidget.mapToGlobal(pos))
    
    def delete_project(self, item):
        """删除项目"""
        project_id = item.data(Qt.UserRole)
        
        if not project_id:
            logger.error("无法获取项目ID")
            return
        
        # 获取项目信息
        project_dir = os.path.join(self.workspace_dir, project_id)
        project_conf_file = os.path.join(project_dir, f"{project_id}_conf.json")
        
        project_name = project_id
        if os.path.exists(project_conf_file):
            try:
                with open(project_conf_file, 'r', encoding='utf-8') as f:
                    project_conf = json.load(f)
                project_name = project_conf.get("name", project_id)
            except:
                pass
        
        # 确认删除
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_message_box_icon())
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("确认删除")
        msg_box.setText(f"确定要删除项目 '{project_name}' 吗?\n\nID: {project_id}\n\n此操作将删除项目文件夹及所有数据,无法恢复!")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        reply = msg_box.exec()
        
        if reply != QMessageBox.Yes:
            logger.info("用户取消了删除操作")
            return
        
        # 删除项目文件夹
        try:
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
                logger.info(f"已删除项目文件夹: {project_dir}")
        except Exception as e:
            logger.error(f"删除项目文件夹失败: {e}")
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"删除项目文件夹失败:\n{e}")
            msg_box.exec()
            return
        
        # 从 workspace_logs.json 中删除记录
        try:
            if os.path.exists(self.workspace_logs_file):
                with open(self.workspace_logs_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                
                # 过滤掉要删除的项目
                logs["recent_projects"] = [
                    p for p in logs.get("recent_projects", [])
                    if p.get("id") != project_id
                ]
                
                with open(self.workspace_logs_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
                
                logger.info(f"已从workspace_logs.json中删除项目记录: {project_id}")
        except Exception as e:
            logger.warning(f"更新workspace_logs.json失败: {e}")
        
        # 刷新列表
        self.load_project_list()
        
        logger.info(f"项目删除完成: {project_name} (ID: {project_id})")
    
    def init_workspace_logs(self):
        """初始化 workspace_logs.json 文件"""
        if not os.path.exists(self.workspace_logs_file):
            default_logs = {
                "recent_projects": []
            }
            with open(self.workspace_logs_file, 'w', encoding='utf-8') as f:
                json.dump(default_logs, f, indent=2, ensure_ascii=False)
            logger.info("已创建 workspace_logs.json 文件")
    
    def load_project_list(self):
        """加载项目列表到 proj_listWidget"""
        self.ui.proj_listWidget.clear()
        
        try:
            # 扫描 workspace 目录下所有项目
            projects = []
            
            if os.path.exists(self.workspace_dir):
                for folder_name in os.listdir(self.workspace_dir):
                    folder_path = os.path.join(self.workspace_dir, folder_name)
                    
                    # 跳过 workspace_logs.json 和非目录
                    if not os.path.isdir(folder_path):
                        continue
                    
                    # 查找项目配置文件
                    conf_file = os.path.join(folder_path, f"{folder_name}_conf.json")
                    
                    if os.path.exists(conf_file):
                        try:
                            with open(conf_file, 'r', encoding='utf-8') as f:
                                project_conf = json.load(f)
                            
                            project_id = project_conf.get("id", folder_name)
                            project_name = project_conf.get("name", "未命名项目")
                            created_time = project_conf.get("created_time", "未知")
                            
                            # 计算相对路径
                            rel_path = os.path.relpath(folder_path, get_app_dir())
                            
                            projects.append({
                                "id": project_id,
                                "name": project_name,
                                "created_time": created_time,
                                "rel_path": rel_path
                            })
                        except Exception as e:
                            logger.error(f"读取项目配置失败 {conf_file}: {e}")
            
            # 按创建时间排序(最新的在前)
            projects.sort(key=lambda x: x.get("created_time", ""), reverse=True)
            
            # 添加到列表控件
            for project in projects:
                # 创建美化的显示文本(不包含emoji)
                display_text = self.format_project_item(
                    project["name"],
                    project["id"],
                    project["created_time"],
                    project["rel_path"]
                )
                
                # 创建列表项
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, project["id"])  # 存储项目ID
                
                # 设置项目图标
                icon_path = os.path.join(get_app_dir(), "icon", "small_folder.ico")
                if os.path.exists(icon_path):
                    item.setIcon(QIcon(icon_path))
                
                # 设置字体
                font = QFont()
                font.setPointSize(9)
                item.setFont(font)
                
                # 添加到列表
                self.ui.proj_listWidget.addItem(item)
            
            logger.info(f"已加载 {len(projects)} 个项目")
            
        except Exception as e:
            logger.error(f"加载项目列表失败: {e}")
    
    def format_project_item(self, name, project_id, created_time, rel_path):
        """格式化项目显示文本"""
        # 多行显示格式
        return (
            f"{name}\n"
            f"   ID: {project_id}\n"
            f"   创建时间: {created_time}\n"
            f"   路径: {rel_path}"
        )
    
    def connect_signals(self):
        """连接信号和槽"""
        self.ui.createProj_Button.clicked.connect(self.create_new_project)
        self.ui.openProj_Button.clicked.connect(self.open_selected_project)
        self.ui.proj_listWidget.itemDoubleClicked.connect(self.open_selected_project)
        self.ui.export_Button.clicked.connect(self.export_project)
        # 连接选择变化信号，控制导出按钮的启用状态
        self.ui.proj_listWidget.itemSelectionChanged.connect(self.on_selection_changed)
        logger.debug("信号连接完成")
    
    def create_new_project(self):
        """创建新项目"""
        logger.info(">>> 新建项目按钮被点击")
        
        # 弹出输入框,获取项目名称
        project_name, ok = show_text_input_dialog_with_icon(
            self,
            "新建项目",
            "请输入项目名称:",
            text="新项目"
        )
        
        if not ok or not project_name.strip():
            logger.info("用户取消了项目创建")
            return
        
        project_name = project_name.strip()
        
        # 生成项目ID (使用短UUID,不带前缀)
        project_id = str(uuid.uuid4())[:8]  # 取UUID的前8位
        
        # 创建项目目录
        project_dir = os.path.join(self.workspace_dir, project_id)
        try:
            os.makedirs(project_dir, exist_ok=True)
            logger.info(f"已创建项目目录: {project_dir}")
        except Exception as e:
            logger.error(f"创建项目目录失败: {e}")
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"创建项目目录失败:\n{e}")
            msg_box.exec()
            return
        
        # 创建项目配置文件
        project_conf_file = os.path.join(project_dir, f"{project_id}_conf.json")
        project_conf = {
            "id": project_id,
            "name": project_name,
            "created_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            with open(project_conf_file, 'w', encoding='utf-8') as f:
                json.dump(project_conf, f, indent=2, ensure_ascii=False)
            logger.info(f"已创建项目配置文件: {project_conf_file}")
        except Exception as e:
            logger.error(f"创建项目配置文件失败: {e}")
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"创建项目配置文件失败:\n{e}")
            msg_box.exec()
            return
        
        # 创建快照目录
        snapshots_dir = os.path.join(project_dir, "snapshots")
        os.makedirs(snapshots_dir, exist_ok=True)
        logger.info(f"已创建快照目录: {snapshots_dir}")
        
        # 更新 workspace_logs.json (只记录ID和访问时间)
        self.update_workspace_logs(project_id)
        
        # 刷新项目列表
        self.load_project_list()
        
        logger.info(f"项目创建完成: {project_name} (ID: {project_id})")
    
    def update_workspace_logs(self, project_id):
        """更新 workspace_logs.json (只记录ID和访问时间,不存储name避免冗余)"""
        try:
            with open(self.workspace_logs_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = {"recent_projects": []}
        
        # 检查项目是否已存在
        existing_project = None

        for project in logs["recent_projects"]:
            if project["id"] == project_id:
                existing_project = project
                break
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing_project:
            # 更新已有项目的打开时间
            existing_project["last_opened"] = current_time
            logger.debug(f"更新项目记录: {project_id}")
        else:
            # 添加新项目(只记录ID和时间)
            new_project = {
                "id": project_id,
                "last_opened": current_time
            }
            logs["recent_projects"].append(new_project)
            logger.debug(f"添加新项目记录: {project_id}")
        
        # 保存
        with open(self.workspace_logs_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        
        logger.info("workspace_logs.json 已更新")
    
    def on_selection_changed(self):
        """处理项目选择变化"""
        selected_items = self.ui.proj_listWidget.selectedItems()
        # 只有选中项目时才启用导出按钮
        self.ui.export_Button.setEnabled(len(selected_items) > 0)
    
    def export_project(self):
        """导出选中的项目快照"""
        logger.info(">>> 导出项目按钮被点击")
        
        # 获取选中的项目
        selected_items = self.ui.proj_listWidget.selectedItems()
        
        if not selected_items:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("请先选择一个项目!")
            msg_box.exec()
            logger.warning("未选择任何项目")
            return
        
        # 获取项目ID
        project_id = selected_items[0].data(Qt.UserRole)
        
        if not project_id:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText("无法获取项目ID!")
            msg_box.exec()
            logger.error("项目ID为空")
            return
        
        # 获取项目信息
        project_dir = os.path.join(self.workspace_dir, project_id)
        project_conf_file = os.path.join(project_dir, f"{project_id}_conf.json")
        
        project_name = project_id
        if os.path.exists(project_conf_file):
            try:
                with open(project_conf_file, 'r', encoding='utf-8') as f:
                    project_conf = json.load(f)
                project_name = project_conf.get("name", project_id)
            except Exception as e:
                logger.warning(f"读取项目配置失败: {e}")
        
        logger.info(f"准备导出项目: {project_name} (ID: {project_id})")
        
        # 验证项目目录是否存在
        if not os.path.exists(project_dir):
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"项目目录不存在!\n\n路径: {project_dir}")
            msg_box.exec()
            logger.error(f"项目目录不存在: {project_dir}")
            return
        
        # 让用户选择导出目录
        from PySide6.QtWidgets import QFileDialog
        export_base_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if not export_base_dir:
            logger.info("用户取消了导出操作")
            return
        
        logger.info(f"导出目标目录: {export_base_dir}")
        
        # 执行导出（改为调用 export.export_project_snapshots，以保持行为一致）
        try:
            import snapshot_io
            import export as export_module

            ok, stats = export_module.export_project_snapshots(project_dir, project_name, export_base_dir, snapshot_io)

            if ok:
                # 显示导出结果
                msg_box = QMessageBox()
                msg_box.setWindowIcon(get_message_box_icon())
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setWindowTitle("导出完成")
                msg_box.setText(
                    f"项目 '{project_name}' 导出完成!\n\n"
                    f"用户数: {stats.get('total_users')}\n"
                    f"快照数: {stats.get('total_snapshots')}\n"
                    f"文件数: {stats.get('total_files')}\n\n"
                    f"导出路径: {stats.get('export_path')}"
                )
                msg_box.exec()

                logger.info(f"导出完成: {stats.get('total_users')} 个用户, {stats.get('total_snapshots')} 个快照, {stats.get('total_files')} 个文件")
                logger.info(f"导出路径: {stats.get('export_path')}")
            else:
                raise Exception(stats.get('error', '导出失败'))

        except Exception as e:
            logger.error(f"导出失败: {e}", exc_info=True)
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"导出失败:\n{e}")
            msg_box.exec()
    
    def open_selected_project(self):
        """打开选中的项目"""
        logger.info(">>> 打开项目按钮被点击")
        
        # 获取选中的项目
        selected_items = self.ui.proj_listWidget.selectedItems()
        
        if not selected_items:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("请先选择一个项目!")
            msg_box.exec()
            logger.warning("未选择任何项目")
            return
        
        # 获取项目ID (从item的UserRole数据中)
        project_id = selected_items[0].data(Qt.UserRole)
        
        if not project_id:
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText("无法获取项目ID!")
            msg_box.exec()
            logger.error("项目ID为空")
            return
        
        logger.info(f"准备打开项目: {project_id}")
        
        # 验证项目目录是否存在
        project_dir = os.path.join(self.workspace_dir, project_id)
        if not os.path.exists(project_dir):
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"项目目录不存在!\n\n路径: {project_dir}\n\n该项目可能已被删除。")
            msg_box.exec()
            logger.error(f"项目目录不存在: {project_dir}")
            return
        
        # 更新打开时间 (只记录ID和访问时间,项目名从配置文件读取)
        self.update_workspace_logs(project_id)
        
        # 启动主程序,传递项目ID
        logger.info(f"正在启动主程序: main --project-id {project_id}")
        
        try:
            # 检测是否为打包后的exe环境
            if getattr(sys, 'frozen', False):
                # 打包为exe后，启动main.exe
                # 文件夹模式：setup/ 和 main/ 是并列目录
                parent_dir = os.path.dirname(self.app_dir)
                main_exe = os.path.join(parent_dir, "main", "main.exe")
                
                if not os.path.exists(main_exe):
                    # 尝试同目录（备用）
                    main_exe = os.path.join(self.app_dir, "main.exe")
                    if not os.path.exists(main_exe):
                        raise FileNotFoundError(f"找不到main.exe: {main_exe}")
                
                logger.info(f"启动exe: {main_exe}")
                subprocess.Popen([main_exe, "--project-id", project_id])
            else:
                # 开发环境，使用Python解释器启动main.py
                python_exe = sys.executable
                main_py = os.path.join(self.app_dir, "main.py")
                if not os.path.exists(main_py):
                    raise FileNotFoundError(f"找不到main.py: {main_py}")
                logger.info(f"启动py: {python_exe} {main_py}")
                subprocess.Popen([python_exe, main_py, "--project-id", project_id])
            
            logger.info("主程序已启动,隐藏设置窗口")
            
            # 设置隐藏标志，然后关闭窗口（实际会被closeEvent拦截并隐藏）
            self.is_hiding = True
            self.close()
            
        except Exception as e:
            logger.error(f"启动主程序失败: {e}")
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_message_box_icon())
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("错误")
            msg_box.setText(f"启动主程序失败:\n{e}")
            msg_box.exec()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("=== Plampture 项目设置启动 ===")
    logger.info("=" * 60)
    
    app = QApplication(sys.argv)
    
    # 设置应用程序在最后一个窗口关闭时也不退出（通过closeEvent手动控制）
    app.setQuitOnLastWindowClosed(False)
    
    # 创建设置窗口
    setup_window = SetupWindow()
    setup_window.show()
    
    logger.info("设置窗口已显示，进入后台运行模式")
    
    # 进入事件循环
    exit_code = app.exec()
    logger.info(f"应用程序退出，退出码: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
