"""
数据同步系统 GUI 应用模块
使用 CustomTkinter 实现三步向导式界面
"""

import customtkinter as ctk
import threading
import queue
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入现有模块
from src.config_loader import ConfigLoader
from src.config_selector import ConfigSelector
from src.db_connector import DatabaseConnector
from src.data_sync import DataSync
from src.logger import get_logger

# 设置 CustomTkinter 主题
ctk.set_appearance_mode("dark")  # 可选: "light", "dark", "system"
ctk.set_default_color_theme("blue")  # 可选: "blue", "green", "dark-blue"

logger = get_logger(__name__)


class SyncLogger:
    """日志处理器，将日志输出到 GUI"""
    
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
    
    def emit(self, record):
        """将日志记录放入队列"""
        try:
            msg = self.format(record)
            self.log_queue.put(('log', msg))
        except Exception:
            pass
    
    def flush(self):
        """刷新处理器"""
        pass


class DataSyncApp:
    """数据同步 GUI 应用主类"""
    
    def __init__(self):
        """初始化应用"""
        self.root = ctk.CTk()
        self.root.title("SQL Server 数据同步系统")
        self.root.geometry("1200x800")
        
        # 居中显示窗口
        self.center_window()
        
        # 应用状态
        self.current_step = 1
        self.selected_config = None
        self.sync_stats = None
        self.sync_thread = None
        self.log_queue = queue.Queue()
        self.is_syncing = False
        
        # 配置文件列表
        self.configs = []
        
        # 创建界面
        self.create_widgets()
        
        # 启动日志更新
        self.check_log_queue()
    
    def center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 标题
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="SQL Server 数据同步系统",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=(20, 30))
        
        # 步骤指示器
        self.step_indicator = ctk.CTkLabel(
            self.main_frame,
            text="步骤 1/3: 选择配置",
            font=ctk.CTkFont(size=16)
        )
        self.step_indicator.pack(pady=(0, 20))
        
        # 步骤 1: 配置选择界面
        self.step1_frame = self.create_step1_frame()
        
        # 步骤 2: 执行进度界面
        self.step2_frame = self.create_step2_frame()
        
        # 步骤 3: 结果展示界面
        self.step3_frame = self.create_step3_frame()
        
        # 初始显示步骤 1
        self.show_step1()
    
    def create_step1_frame(self):
        """创建步骤 1 界面"""
        frame = ctk.CTkFrame(self.main_frame)
        
        # 配置选择标签
        ctk.CTkLabel(
            frame,
            text="选择要同步的配置文件：",
            font=ctk.CTkFont(size=14)
        ).pack(pady=(20, 10))
        
        # 配置下拉列表
        self.config_combobox = ctk.CTkOptionMenu(frame, values=[], command=self.on_config_selected)
        self.config_combobox.pack(pady=10, padx=20, fill="x")
        
        # 配置详情
        self.config_details_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.config_details_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        self.config_name_label = ctk.CTkLabel(
            self.config_details_frame,
            text="配置名称: ",
            font=ctk.CTkFont(size=12)
        )
        self.config_name_label.pack(anchor="w", pady=2)
        
        self.config_desc_label = ctk.CTkLabel(
            self.config_details_frame,
            text="描述: ",
            font=ctk.CTkFont(size=12)
        )
        self.config_desc_label.pack(anchor="w", pady=2)
        
        self.config_file_label = ctk.CTkLabel(
            self.config_details_frame,
            text="文件: ",
            font=ctk.CTkFont(size=12)
        )
        self.config_file_label.pack(anchor="w", pady=2)
        
        # 按钮框架
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=20)
        
        # 下一步按钮
        self.next_btn = ctk.CTkButton(
            button_frame,
            text="下一步",
            command=self.go_to_step2,
            width=150,
            height=40
        )
        self.next_btn.pack(side="right", padx=10)
        
        # 退出按钮
        self.exit_btn = ctk.CTkButton(
            button_frame,
            text="退出",
            command=self.on_exit,
            width=150,
            height=40,
            fg_color="gray"
        )
        self.exit_btn.pack(side="right", padx=10)
        
        # 加载配置文件
        self.load_configs()
        
        return frame
    
    def create_step2_frame(self):
        """创建步骤 2 界面"""
        frame = ctk.CTkFrame(self.main_frame)
        
        # 进度信息框架
        info_frame = ctk.CTkFrame(frame)
        info_frame.pack(pady=(20, 20), padx=20, fill="x")
        
        # 当前配置标签
        self.current_config_label = ctk.CTkLabel(
            info_frame,
            text="当前配置: ",
            font=ctk.CTkFont(size=12)
        )
        self.current_config_label.pack(anchor="w", padx=10, pady=5)
        
        # 当前表标签
        self.current_table_label = ctk.CTkLabel(
            info_frame,
            text="当前表: 等待开始...",
            font=ctk.CTkFont(size=12)
        )
        self.current_table_label.pack(anchor="w", padx=10, pady=5)
        
        # 总体进度条
        ctk.CTkLabel(
            info_frame,
            text="总体进度:",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=10, pady=(15, 5))
        
        self.progress_bar = ctk.CTkProgressBar(info_frame)
        self.progress_bar.pack(padx=10, pady=5, fill="x")
        self.progress_bar.set(0)
        
        # 进度文本
        self.progress_text = ctk.CTkLabel(
            info_frame,
            text="0 / 0 表",
            font=ctk.CTkFont(size=12)
        )
        self.progress_text.pack(padx=10, pady=5)
        
        # 日志文本框
        ctk.CTkLabel(
            frame,
            text="执行日志:",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        self.log_textbox = ctk.CTkTextbox(frame, height=300)
        self.log_textbox.pack(padx=20, pady=(5, 10), fill="both", expand=True)
        
        # 按钮框架
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        
        # 取消按钮
        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="取消",
            command=self.cancel_sync,
            width=150,
            height=40,
            fg_color="orange"
        )
        self.cancel_btn.pack(side="right", padx=10)
        
        # 上一步按钮
        self.step2_prev_btn = ctk.CTkButton(
            button_frame,
            text="上一步",
            command=self.go_to_step1,
            width=150,
            height=40
        )
        self.step2_prev_btn.pack(side="right", padx=10)
        
        return frame
    
    def create_step3_frame(self):
        """创建步骤 3 界面"""
        frame = ctk.CTkFrame(self.main_frame)
        
        # 统计信息框架
        stats_frame = ctk.CTkFrame(frame)
        stats_frame.pack(pady=(20, 20), padx=20, fill="x")
        
        ctk.CTkLabel(
            stats_frame,
            text="同步结果统计",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(15, 15))
        
        # 统计标签网格
        grid_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        grid_frame.pack(padx=20, pady=(0, 20), fill="x")
        
        # 时间统计
        self.start_time_label = ctk.CTkLabel(
            grid_frame,
            text="开始时间: ",
            font=ctk.CTkFont(size=12)
        )
        self.start_time_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        
        self.end_time_label = ctk.CTkLabel(
            grid_frame,
            text="结束时间: ",
            font=ctk.CTkFont(size=12)
        )
        self.end_time_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        
        self.duration_label = ctk.CTkLabel(
            grid_frame,
            text="总耗时: ",
            font=ctk.CTkFont(size=12)
        )
        self.duration_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        
        # 分隔线
        ctk.CTkLabel(
            grid_frame,
            text="-" * 50,
            font=ctk.CTkFont(size=10)
        ).grid(row=3, column=0, columnspan=2, pady=10)
        
        # 表统计
        self.total_tables_label = ctk.CTkLabel(
            grid_frame,
            text="总表数: ",
            font=ctk.CTkFont(size=12)
        )
        self.total_tables_label.grid(row=4, column=0, sticky="w", pady=2)
        
        self.success_tables_label = ctk.CTkLabel(
            grid_frame,
            text="成功: ",
            font=ctk.CTkFont(size=12),
            text_color="green"
        )
        self.success_tables_label.grid(row=4, column=1, sticky="w", padx=20, pady=2)
        
        self.failed_tables_label = ctk.CTkLabel(
            grid_frame,
            text="失败: ",
            font=ctk.CTkFont(size=12),
            text_color="red"
        )
        self.failed_tables_label.grid(row=5, column=0, sticky="w", pady=2)
        
        self.skipped_tables_label = ctk.CTkLabel(
            grid_frame,
            text="跳过: ",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.skipped_tables_label.grid(row=5, column=1, sticky="w", padx=20, pady=2)
        
        self.synced_rows_label = ctk.CTkLabel(
            grid_frame,
            text="同步行数: ",
            font=ctk.CTkFont(size=12)
        )
        self.synced_rows_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=2)
        
        # 详细日志文本框
        ctk.CTkLabel(
            frame,
            text="详细日志:",
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        self.details_textbox = ctk.CTkTextbox(frame, height=200)
        self.details_textbox.pack(padx=20, pady=(5, 10), fill="both", expand=True)
        
        # 按钮框架
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=10)
        
        # 重新开始按钮
        self.restart_btn = ctk.CTkButton(
            button_frame,
            text="重新开始",
            command=self.restart,
            width=150,
            height=40
        )
        self.restart_btn.pack(side="right", padx=10)
        
        # 退出按钮
        self.step3_exit_btn = ctk.CTkButton(
            button_frame,
            text="退出",
            command=self.on_exit,
            width=150,
            height=40,
            fg_color="gray"
        )
        self.step3_exit_btn.pack(side="right", padx=10)
        
        return frame
    
    def load_configs(self):
        """加载配置文件列表"""
        try:
            selector = ConfigSelector()
            self.configs = selector.discover_configs()
            
            if self.configs:
                # 更新下拉列表
                config_names = [config['name'] for config in self.configs]
                self.config_combobox.configure(values=config_names)
                
                # 默认选择第一个配置
                if config_names:
                    self.config_combobox.set(config_names[0])
                    self.on_config_selected(config_names[0])
            else:
                self.config_combobox.configure(values=["未找到配置文件"])
                self.config_combobox.set("未找到配置文件")
                self.next_btn.configure(state="disabled")
                
        except Exception as e:
            self.config_combobox.configure(values=[f"加载失败: {str(e)}"])
            self.config_combobox.set(f"加载失败: {str(e)}")
            self.next_btn.configure(state="disabled")
    
    def on_config_selected(self, config_name: str):
        """配置选择回调"""
        for config in self.configs:
            if config['name'] == config_name:
                self.selected_config = config
                
                # 更新配置详情
                self.config_name_label.configure(text=f"配置名称: {config['name']}")
                self.config_desc_label.configure(text=f"描述: {config['description'] or '无'}")
                self.config_file_label.configure(text=f"文件: {config['filename']}")
                
                # 启用下一步按钮
                self.next_btn.configure(state="normal")
                break
    
    def show_step1(self):
        """显示步骤 1"""
        self.step1_frame.pack(fill="both", expand=True)
        self.step2_frame.pack_forget()
        self.step3_frame.pack_forget()
        self.current_step = 1
        self.step_indicator.configure(text="步骤 1/3: 选择配置")
    
    def show_step2(self):
        """显示步骤 2"""
        self.step1_frame.pack_forget()
        self.step2_frame.pack(fill="both", expand=True)
        self.step3_frame.pack_forget()
        self.current_step = 2
        self.step_indicator.configure(text="步骤 2/3: 执行同步")
        
        # 清空日志
        self.log_textbox.delete("0.0", "end")
        
        # 显示当前配置
        if self.selected_config:
            self.current_config_label.configure(text=f"当前配置: {self.selected_config['name']}")
    
    def show_step3(self):
        """显示步骤 3"""
        self.step1_frame.pack_forget()
        self.step2_frame.pack_forget()
        self.step3_frame.pack(fill="both", expand=True)
        self.current_step = 3
        self.step_indicator.configure(text="步骤 3/3: 查看结果")
        
        # 显示统计信息
        if self.sync_stats:
            self.display_stats()
    
    def go_to_step1(self):
        """返回步骤 1"""
        self.show_step1()
    
    def go_to_step2(self):
        """进入步骤 2 并开始同步"""
        if not self.selected_config:
            return
        
        self.show_step2()
        self.start_sync()
    
    def start_sync(self):
        """开始同步任务"""
        if self.is_syncing:
            return
        
        self.is_syncing = True
        self.cancel_btn.configure(state="normal")
        self.step2_prev_btn.configure(state="disabled")
        
        # 清空日志
        self.log_textbox.delete("0.0", "end")
        self.append_log("开始数据同步任务...")
        
        # 在后台线程中执行同步
        self.sync_thread = threading.Thread(target=self.run_sync, daemon=True)
        self.sync_thread.start()
    
    def run_sync(self):
        """在后台线程中运行同步任务"""
        try:
            # 设置日志处理器
            sync_logger = SyncLogger(self.log_queue)
            
            # 加载配置
            self.log_queue.put(('log', "正在加载配置文件..."))
            config_loader = ConfigLoader(tables_config_path=self.selected_config['path'])
            
            # 加载数据库配置
            db_config = config_loader.load_db_config()
            source_db_config = config_loader.get_source_database_config()
            target_db_config = config_loader.get_target_database_config()
            sync_settings = config_loader.get_sync_settings()
            related_table_config = config_loader.get_related_table_config()
            
            # 加载表配置
            tables_to_sync = config_loader.get_tables_to_sync()
            
            if not tables_to_sync:
                self.log_queue.put(('log', "错误: 没有配置需要同步的表"))
                self.log_queue.put(('finish', None))
                return
            
            self.log_queue.put(('log', f"配置加载完成，待同步表数量: {len(tables_to_sync)}"))
            
            # 创建数据库连接器
            self.log_queue.put(('log', "正在创建数据库连接..."))
            source_db = DatabaseConnector(
                source_db_config,
                retry_times=sync_settings['retry_times'],
                retry_interval=sync_settings['retry_interval']
            )
            target_db = DatabaseConnector(
                target_db_config,
                retry_times=sync_settings['retry_times'],
                retry_interval=sync_settings['retry_interval']
            )
            
            # 创建数据同步器
            self.log_queue.put(('log', "正在创建数据同步器..."))
            data_sync = DataSync(
                source_db=source_db,
                target_db=target_db,
                batch_size=sync_settings['batch_size'],
                related_table_config=related_table_config
            )
            
            # 发送表数量信息
            self.log_queue.put(('tables_count', len(tables_to_sync)))
            
            # 执行数据同步
            self.log_queue.put(('log', "开始执行数据同步任务..."))
            sync_stats = data_sync.sync_tables(tables_to_sync)
            
            # 发送完成信息
            self.log_queue.put(('finish', sync_stats))
            
        except Exception as e:
            self.log_queue.put(('log', f"错误: {str(e)}"))
            self.log_queue.put(('finish', None))
    
    def cancel_sync(self):
        """取消同步任务"""
        if self.is_syncing:
            self.is_syncing = False
            self.log_queue.put(('log', "正在取消同步任务..."))
            self.append_log("同步任务已取消")
            self.cancel_btn.configure(state="disabled")
            self.step2_prev_btn.configure(state="normal")
    
    def check_log_queue(self):
        """检查并处理日志队列"""
        try:
            while True:
                msg_type, msg = self.log_queue.get_nowait()
                
                if msg_type == 'log':
                    self.append_log(msg)
                elif msg_type == 'progress':
                    current, total = msg
                    self.update_progress(current, total)
                elif msg_type == 'tables_count':
                    total = msg
                    self.progress_text.configure(text=f"0 / {total} 表")
                elif msg_type == 'finish':
                    self.is_syncing = False
                    self.sync_stats = msg
                    self.cancel_btn.configure(state="disabled")
                    
                    if msg:
                        self.log_queue.put(('log', "数据同步任务完成"))
                        # 延迟跳转到结果页面
                        self.root.after(1000, self.show_step3)
                    else:
                        self.log_queue.put(('log', "数据同步任务失败"))
                        self.step2_prev_btn.configure(state="normal")
        
        except queue.Empty:
            pass
        
        # 继续检查
        self.root.after(100, self.check_log_queue)
    
    def append_log(self, message: str):
        """追加日志到文本框"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")
    
    def update_progress(self, current: int, total: int):
        """更新进度条"""
        if total > 0:
            progress = current / total
            self.progress_bar.set(progress)
            self.progress_text.configure(text=f"{current} / {total} 表")
    
    def display_stats(self):
        """显示统计信息"""
        if not self.sync_stats:
            return
        
        stats = self.sync_stats
        
        # 时间统计
        self.start_time_label.configure(
            text=f"开始时间: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.end_time_label.configure(
            text=f"结束时间: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        duration = (stats['end_time'] - stats['start_time']).total_seconds()
        self.duration_label.configure(text=f"总耗时: {duration:.2f} 秒")
        
        # 表统计
        self.total_tables_label.configure(text=f"总表数: {stats['total_tables']}")
        self.success_tables_label.configure(
            text=f"成功: {stats['success_tables']}",
            text_color="green" if stats['success_tables'] == stats['total_tables'] else "green"
        )
        self.failed_tables_label.configure(
            text=f"失败: {stats['failed_tables']}",
            text_color="red" if stats['failed_tables'] > 0 else "red"
        )
        self.skipped_tables_label.configure(text=f"跳过: {stats['skipped_tables']}")
        self.synced_rows_label.configure(text=f"同步行数: {stats['synced_rows']}")
        
        # 详细日志
        self.details_textbox.delete("0.0", "end")
        details = "=" * 60 + "\n"
        details += "详细信息\n"
        details += "=" * 60 + "\n\n"
        
        for detail in stats['details']:
            status_symbol = "✓" if detail['status'] == 'success' else ("✗" if detail['status'] == 'failed' else "○")
            details += f"{status_symbol} {detail['table_name']}: 源数据 {detail['source_rows']} 行\n"
            
            # 显示主表同步详细信息
            if detail.get('inserted_rows', 0) > 0 or detail.get('skipped_rows', 0) > 0:
                details += f"    主表同步: 插入 {detail['inserted_rows']} 行\n"
                if detail.get('skipped_rows', 0) > 0:
                    details += f"             跳过重复 {detail['skipped_rows']} 行\n"
            
            # 显示关联表同步详细信息
            if detail.get('related_synced_rows', 0) > 0:
                details += f"    关联表 WFC_PROCESS:\n"
                details += f"      需同步: {detail['related_synced_rows']} 行\n"
                details += f"      已存在: {detail['related_existing_count']} 行\n"
                details += f"      成功插入: {detail['related_inserted_count']} 行\n"
                if detail.get('related_skipped_count', 0) > 0:
                    details += f"      跳过重复: {detail['related_skipped_count']} 行\n"
            
            if detail['status'] == 'failed':
                details += f"    错误: {detail['error']}\n"
            elif detail['status'] == 'skipped':
                details += f"    原因: {detail['error']}\n"
            
            details += "\n"
        
        self.details_textbox.insert("0.0", details)
    
    def restart(self):
        """重新开始"""
        self.selected_config = None
        self.sync_stats = None
        self.log_textbox.delete("0.0", "end")
        self.details_textbox.delete("0.0", "end")
        self.progress_bar.set(0)
        self.progress_text.configure(text="0 / 0 表")
        
        # 重新加载配置
        self.load_configs()
        
        # 返回步骤 1
        self.show_step1()
    
    def on_exit(self):
        """退出应用"""
        if self.is_syncing:
            self.cancel_sync()
        self.root.destroy()
        sys.exit(0)
    
    def run(self):
        """运行应用"""
        self.root.mainloop()


def main():
    """主函数"""
    app = DataSyncApp()
    app.run()


if __name__ == "__main__":
    main()
