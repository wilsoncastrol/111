"""
多模态交互压力数据分析系统 - 主应用程序
Main Tkinter application with dashboard, history, settings panels.
Multimodal Interaction Stress Analysis System — fully offline, privacy-first.
"""

import sys
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import (
    WINDOW_TITLE,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    THEME_BG,
    THEME_FG,
    THEME_ACCENT,
    STRESS_LEVELS,
    COLLECTION_INTERVAL,
    EXPORT_DIR,
    EXPORT_FILENAME_TEMPLATE,
    DEBUG_MODE,
    get_stress_name,
    get_stress_color,
    logger,
)
from collector import DataCollector, PYNPUT_AVAILABLE
from analyzer import StressAnalyzer
from storage import StorageManager
from visualizer import StressVisualizer
from alerts import AlertManager


class StressAnalysisApp:
    """多模态交互压力数据分析系统 - 主应用程序"""

    def __init__(self):
        logger.info("=" * 50)
        logger.info("启动多模态交互压力数据分析系统")
        logger.info("=" * 50)

        # 初始化核心组件
        self.storage = StorageManager()
        self.collector = DataCollector()
        self.analyzer = StressAnalyzer()
        self.visualizer = StressVisualizer()
        self.alert_manager = AlertManager()

        # 当前状态
        self._current_score = 0.0
        self._current_level = 1  # 默认"正常"
        self._current_features = {}
        self._is_collecting = False

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=THEME_BG)

        # 窗口居中
        self._center_window(1000, 700)

        # 设置关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 设置预警回调
        self.alert_manager.set_alert_callback(self._show_alert_dialog)

        # 构建界面
        self._build_ui()

        # 定时刷新UI
        self._schedule_ui_update()

        logger.info("应用程序界面已初始化")

    def _center_window(self, width: int, height: int):
        """将窗口居中显示"""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    # ==================== 界面构建 ====================

    def _build_ui(self):
        """构建主界面"""
        # 顶部工具栏
        self._build_toolbar()

        # 标签页容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 各标签页
        self._build_dashboard_tab()
        self._build_history_tab()
        self._build_settings_tab()

        # 底部状态栏
        self._build_statusbar()

    def _build_toolbar(self):
        """构建顶部工具栏"""
        toolbar = tk.Frame(self.root, bg=THEME_ACCENT, height=50)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        # 标题
        title_label = tk.Label(
            toolbar, text="🧠 " + WINDOW_TITLE,
            bg=THEME_ACCENT, fg="white", font=("", 14, "bold")
        )
        title_label.pack(side="left", padx=15)

        # 采集控制按钮
        btn_frame = tk.Frame(toolbar, bg=THEME_ACCENT)
        btn_frame.pack(side="right", padx=15)

        self.btn_start = tk.Button(
            btn_frame, text="▶ 开始采集", command=self._start_collection,
            bg="#4CAF50", fg="white", font=("", 10, "bold"),
            relief="flat", padx=15, pady=5, cursor="hand2"
        )
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = tk.Button(
            btn_frame, text="⏹ 停止采集", command=self._stop_collection,
            bg="#F44336", fg="white", font=("", 10, "bold"),
            relief="flat", padx=15, pady=5, cursor="hand2", state="disabled"
        )
        self.btn_stop.pack(side="left", padx=5)

    def _build_dashboard_tab(self):
        """构建仪表盘标签页"""
        self.tab_dashboard = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.tab_dashboard, text="  📊 实时仪表盘  ")

        # 上半区：压力仪表 + 当前状态
        top_frame = tk.Frame(self.tab_dashboard, bg="white")
        top_frame.pack(fill="x", padx=10, pady=10)

        # 左侧：压力仪表盘
        gauge_frame = tk.Frame(top_frame, bg="white")
        gauge_frame.pack(side="left", fill="both", expand=True)

        self._gauge_canvas_widget = tk.Frame(gauge_frame, bg="white")
        self._gauge_canvas_widget.pack(fill="both", expand=True)
        self._gauge_canvas = None
        self._update_gauge()

        # 右侧：状态信息卡片
        info_frame = tk.Frame(top_frame, bg="#F8F9FA", relief="groove", bd=1)
        info_frame.pack(side="right", fill="y", padx=(10, 0), ipadx=15, ipady=10)

        tk.Label(info_frame, text="当前状态", bg="#F8F9FA", fg=THEME_FG,
                 font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(5, 10))

        self.lbl_score = tk.Label(info_frame, text="评分: --", bg="#F8F9FA",
                                  fg=THEME_FG, font=("", 11))
        self.lbl_score.pack(anchor="w", padx=10, pady=2)

        self.lbl_level = tk.Label(info_frame, text="等级: --", bg="#F8F9FA",
                                  fg=THEME_FG, font=("", 11))
        self.lbl_level.pack(anchor="w", padx=10, pady=2)

        self.lbl_sources = tk.Label(info_frame, text="压力来源: --", bg="#F8F9FA",
                                    fg=THEME_FG, font=("", 10), wraplength=200, justify="left")
        self.lbl_sources.pack(anchor="w", padx=10, pady=2)

        self.lbl_baseline = tk.Label(info_frame, text="基线: 建立中...", bg="#F8F9FA",
                                     fg="#999999", font=("", 9))
        self.lbl_baseline.pack(anchor="w", padx=10, pady=(10, 2))

        self.lbl_collecting = tk.Label(info_frame, text="采集状态: 未启动", bg="#F8F9FA",
                                       fg="#999999", font=("", 9))
        self.lbl_collecting.pack(anchor="w", padx=10, pady=2)

        # 下半区：趋势图 + 雷达图
        bottom_frame = tk.Frame(self.tab_dashboard, bg="white")
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 趋势图
        self._trend_frame = tk.Frame(bottom_frame, bg="white")
        self._trend_frame.pack(side="left", fill="both", expand=True)
        self._trend_canvas = None
        self._update_trend_chart()

        # 雷达图
        self._radar_frame = tk.Frame(bottom_frame, bg="white")
        self._radar_frame.pack(side="right", fill="both", expand=True)
        self._radar_canvas = None
        self._update_radar_chart()

    def _build_history_tab(self):
        """构建历史记录标签页"""
        self.tab_history = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.tab_history, text="  📅 历史记录  ")

        # 控制面板
        ctrl_frame = tk.Frame(self.tab_history, bg="white")
        ctrl_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(ctrl_frame, text="查看范围:", bg="white", font=("", 10)).pack(side="left")

        self.history_range = ttk.Combobox(
            ctrl_frame, values=["今日", "最近7天", "最近30天", "全部"],
            state="readonly", width=12
        )
        self.history_range.set("今日")
        self.history_range.pack(side="left", padx=5)

        ttk.Button(ctrl_frame, text="刷新", command=self._refresh_history).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="导出Excel", command=self._export_data).pack(side="left", padx=5)

        # 图表区域
        self._history_chart_frame = tk.Frame(self.tab_history, bg="white")
        self._history_chart_frame.pack(fill="both", expand=True, padx=10)
        self._history_bar_canvas = None
        self._history_dist_canvas = None

        # 初始加载
        self._refresh_history()

    def _build_settings_tab(self):
        """构建设置标签页"""
        self.tab_settings = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.tab_settings, text="  ⚙️ 设置  ")

        # 滚动容器
        canvas = tk.Canvas(self.tab_settings, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_settings, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="white")

        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # -- 预警设置 --
        self._build_section(scroll_frame, "🔔 预警设置")

        alert_frame = tk.Frame(scroll_frame, bg="white")
        alert_frame.pack(fill="x", padx=20, pady=5)

        self.var_alert_enabled = tk.BooleanVar(value=True)
        tk.Checkbutton(alert_frame, text="启用高压力预警", variable=self.var_alert_enabled,
                       bg="white", font=("", 10)).pack(anchor="w")

        threshold_frame = tk.Frame(alert_frame, bg="white")
        threshold_frame.pack(fill="x", pady=5)
        tk.Label(threshold_frame, text="高压力持续时间阈值(分钟):", bg="white").pack(side="left")
        self.var_threshold = tk.StringVar(value="30")
        tk.Entry(threshold_frame, textvariable=self.var_threshold, width=8).pack(side="left", padx=5)

        cooldown_frame = tk.Frame(alert_frame, bg="white")
        cooldown_frame.pack(fill="x", pady=5)
        tk.Label(cooldown_frame, text="预警冷却时间(分钟):", bg="white").pack(side="left")
        self.var_cooldown = tk.StringVar(value="10")
        tk.Entry(cooldown_frame, textvariable=self.var_cooldown, width=8).pack(side="left", padx=5)

        break_frame = tk.Frame(alert_frame, bg="white")
        break_frame.pack(fill="x", pady=5)
        tk.Label(break_frame, text="建议休息时长(分钟):", bg="white").pack(side="left")
        self.var_break = tk.StringVar(value="15")
        tk.Entry(break_frame, textvariable=self.var_break, width=8).pack(side="left", padx=5)

        ttk.Button(alert_frame, text="保存预警设置",
                   command=self._save_alert_settings).pack(anchor="w", pady=10)

        # -- 数据管理 --
        self._build_section(scroll_frame, "🗄️ 数据管理")

        data_frame = tk.Frame(scroll_frame, bg="white")
        data_frame.pack(fill="x", padx=20, pady=5)

        # 数据库统计
        self.lbl_db_stats = tk.Label(data_frame, text="正在加载统计信息...",
                                      bg="white", font=("", 10), justify="left")
        self.lbl_db_stats.pack(anchor="w", pady=5)
        self._update_db_stats()

        btn_row = tk.Frame(data_frame, bg="white")
        btn_row.pack(fill="x", pady=5)

        ttk.Button(btn_row, text="备份数据库", command=self._backup_data).pack(side="left", padx=5)
        ttk.Button(btn_row, text="清除所有数据", command=self._clear_data).pack(side="left", padx=5)
        ttk.Button(btn_row, text="刷新统计", command=self._update_db_stats).pack(side="left", padx=5)

        # -- 关于 --
        self._build_section(scroll_frame, "ℹ️ 关于")

        about_frame = tk.Frame(scroll_frame, bg="white")
        about_frame.pack(fill="x", padx=20, pady=5)

        about_text = (
            "多模态交互压力数据分析系统 v1.0\n\n"
            "一款面向办公用户的桌面端工具，能够在本地采集用户与电脑交互的\n"
            "多模态数据，自动分析用户的工作压力状态，提供压力监测、趋势分析\n"
            "与健康干预建议。\n\n"
            "✅ 所有功能完全离线可用\n"
            "✅ 数据仅本地加密存储，保障用户隐私\n"
            "✅ 无需调用任何外部API"
        )
        tk.Label(about_frame, text=about_text, bg="white", font=("", 10),
                 justify="left", wraplength=500).pack(anchor="w")

    def _build_section(self, parent, title):
        """构建设置分区标题"""
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", padx=10, pady=(15, 5))
        tk.Label(parent, text=title, bg="white", fg=THEME_ACCENT,
                 font=("", 12, "bold")).pack(anchor="w", padx=15)

    def _build_statusbar(self):
        """构建底部状态栏"""
        statusbar = tk.Frame(self.root, bg="#E0E0E0", height=25)
        statusbar.pack(fill="x", side="bottom")
        statusbar.pack_propagate(False)

        self.lbl_status = tk.Label(
            statusbar, text="就绪 | 数据采集: 未启动",
            bg="#E0E0E0", fg="#666666", font=("", 9)
        )
        self.lbl_status.pack(side="left", padx=10)

        mode_text = "模拟模式" if not PYNPUT_AVAILABLE else "实时采集"
        self.lbl_mode = tk.Label(
            statusbar, text=f"模式: {mode_text}",
            bg="#E0E0E0", fg="#666666", font=("", 9)
        )
        self.lbl_mode.pack(side="right", padx=10)

    # ==================== 采集控制 ====================

    def _start_collection(self):
        """启动数据采集"""
        if self._is_collecting:
            return

        self._is_collecting = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        if PYNPUT_AVAILABLE:
            self.collector.start(snapshot_callback=self._on_snapshot)
        else:
            # 模拟模式：启动模拟数据线程
            self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self._sim_thread.start()

        self.lbl_collecting.config(text="采集状态: 运行中 ✅")
        self.lbl_status.config(text="数据采集中...")
        logger.info("用户启动数据采集")

    def _stop_collection(self):
        """停止数据采集"""
        self._is_collecting = False
        self.collector.stop()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_collecting.config(text="采集状态: 已停止 ⏹")
        self.lbl_status.config(text="数据采集已停止")
        logger.info("用户停止数据采集")

    def _simulation_loop(self):
        """模拟数据采集循环（当pynput不可用时）"""
        while self._is_collecting:
            time.sleep(COLLECTION_INTERVAL)
            if not self._is_collecting:
                break
            snapshot = self.collector.simulate_data()
            self._on_snapshot(snapshot)

    def _on_snapshot(self, snapshot: dict):
        """数据快照回调 — 执行分析并更新UI"""
        try:
            # 保存原始数据
            self.storage.save_raw_data("snapshot", snapshot)

            # 执行压力分析
            result = self.analyzer.analyze(snapshot)

            # 保存分析结果
            self.storage.save_stress_record(
                score=result["stress_score"],
                level=result["stress_level"],
                sources=result["sources"],
                features=result["features"],
            )

            # 更新当前状态
            self._current_score = result["stress_score"]
            self._current_level = result["stress_level"]
            self._current_features = result["features"]

            # 检查预警
            self.alert_manager.check_stress(result["stress_level"], result["stress_score"])

            # 调度UI更新（Tkinter线程安全）
            self.root.after(0, self._update_dashboard)

        except Exception as e:
            logger.error(f"快照处理失败: {e}", exc_info=True)

    # ==================== UI更新 ====================

    def _schedule_ui_update(self):
        """定时刷新UI（每10秒）"""
        if self._is_collecting:
            self._update_dashboard()
        self.root.after(10000, self._schedule_ui_update)

    def _update_dashboard(self):
        """更新仪表盘所有组件"""
        self._update_gauge()
        self._update_info_panel()
        self._update_trend_chart()
        self._update_radar_chart()

    def _update_gauge(self):
        """更新压力仪表盘"""
        try:
            # 清除旧图
            for widget in self._gauge_canvas_widget.winfo_children():
                widget.destroy()
            if self._gauge_canvas:
                self.visualizer.close_figure(self._gauge_canvas.figure)

            fig = self.visualizer.create_realtime_gauge(self._current_score, self._current_level)
            self._gauge_canvas = FigureCanvasTkAgg(fig, master=self._gauge_canvas_widget)
            self._gauge_canvas.draw()
            self._gauge_canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            logger.error(f"更新仪表盘失败: {e}")

    def _update_info_panel(self):
        """更新状态信息面板"""
        self.lbl_score.config(text=f"评分: {self._current_score:.0f} / 100")
        level_name = get_stress_name(self._current_level)
        level_color = get_stress_color(self._current_level)
        self.lbl_level.config(text=f"等级: {level_name}", fg=level_color)

        # 压力来源
        latest = self.storage.get_latest_stress()
        if latest and latest.get("sources"):
            sources_text = "、".join(latest["sources"].values())
            self.lbl_sources.config(text=f"压力来源: {sources_text}")
        else:
            self.lbl_sources.config(text="压力来源: 无明显来源")

        # 基线状态
        baseline = self.analyzer.get_baseline_status()
        if baseline["ready"]:
            self.lbl_baseline.config(text="基线: 已建立 ✅", fg="#4CAF50")
        else:
            count = baseline["sample_count"]
            self.lbl_baseline.config(text=f"基线: 建立中 ({count}/30)", fg="#FF9800")

    def _update_trend_chart(self):
        """更新趋势图"""
        try:
            for widget in self._trend_frame.winfo_children():
                widget.destroy()
            if self._trend_canvas:
                self.visualizer.close_figure(self._trend_canvas.figure)

            df = self.storage.get_stress_records(hours=24)
            fig = self.visualizer.create_trend_chart(df, period="day")
            self._trend_canvas = FigureCanvasTkAgg(fig, master=self._trend_frame)
            self._trend_canvas.draw()
            self._trend_canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            logger.error(f"更新趋势图失败: {e}")

    def _update_radar_chart(self):
        """更新雷达图"""
        try:
            for widget in self._radar_frame.winfo_children():
                widget.destroy()
            if self._radar_canvas:
                self.visualizer.close_figure(self._radar_canvas.figure)

            fig = self.visualizer.create_modality_contribution(self._current_features)
            self._radar_canvas = FigureCanvasTkAgg(fig, master=self._radar_frame)
            self._radar_canvas.draw()
            self._radar_canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            logger.error(f"更新雷达图失败: {e}")

    # ==================== 历史记录 ====================

    def _refresh_history(self):
        """刷新历史记录页面"""
        range_text = self.history_range.get()
        hours_map = {"今日": 24, "最近7天": 168, "最近30天": 720, "全部": 8760}
        hours = hours_map.get(range_text, 24)

        try:
            # 清除旧图表
            for widget in self._history_chart_frame.winfo_children():
                widget.destroy()

            df = self.storage.get_stress_records(hours=hours)

            # 上半区：趋势/柱状图
            period = "day" if hours <= 24 else "week" if hours <= 168 else "month"

            if hours <= 24:
                fig_top = self.visualizer.create_trend_chart(df, period=period)
            else:
                fig_top = self.visualizer.create_daily_bar_chart(df)

            top_canvas = FigureCanvasTkAgg(fig_top, master=self._history_chart_frame)
            top_canvas.draw()
            top_canvas.get_tk_widget().pack(fill="both", expand=True, pady=(0, 5))

            # 下半区：分布饼图
            fig_bottom = self.visualizer.create_distribution_chart(df)
            bottom_canvas = FigureCanvasTkAgg(fig_bottom, master=self._history_chart_frame)
            bottom_canvas.draw()
            bottom_canvas.get_tk_widget().pack(fill="both", expand=True)

        except Exception as e:
            logger.error(f"刷新历史记录失败: {e}")
            messagebox.showerror("错误", f"加载历史数据失败: {e}")

    def _export_data(self):
        """导出数据到Excel"""
        try:
            default_name = EXPORT_FILENAME_TEMPLATE.format(
                date=datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx")],
                initialdir=EXPORT_DIR,
                initialfile=default_name,
            )
            if filepath:
                success = self.storage.export_to_excel(filepath)
                if success:
                    messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}")
                else:
                    messagebox.showwarning("导出提示", "没有数据可导出")
        except Exception as e:
            logger.error(f"导出失败: {e}")
            messagebox.showerror("导出失败", str(e))

    # ==================== 设置操作 ====================

    def _save_alert_settings(self):
        """保存预警设置"""
        try:
            rules = {
                "enabled": self.var_alert_enabled.get(),
                "high_stress_threshold": int(self.var_threshold.get()) * 60,  # 转为秒
                "alert_cooldown": int(self.var_cooldown.get()) * 60,
                "break_duration": int(self.var_break.get()),
            }
            self.alert_manager.update_rules(rules)
            self.storage.save_setting("alert_rules", rules)
            messagebox.showinfo("保存成功", "预警设置已保存")
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的数字")

    def _update_db_stats(self):
        """更新数据库统计信息"""
        try:
            stats = self.storage.get_data_stats()
            text = (
                f"原始数据记录: {stats['raw_data_count']} 条\n"
                f"压力分析记录: {stats['stress_records_count']} 条\n"
                f"预警记录: {stats['alert_records_count']} 条\n"
                f"数据库大小: {stats['db_size_mb']:.2f} MB\n"
                f"最早记录: {stats['earliest_record']}\n"
                f"最新记录: {stats['latest_record']}"
            )
            self.lbl_db_stats.config(text=text)
        except Exception as e:
            self.lbl_db_stats.config(text=f"获取统计失败: {e}")

    def _backup_data(self):
        """备份数据库"""
        try:
            path = self.storage.backup_database()
            messagebox.showinfo("备份成功", f"数据库已备份到:\n{path}")
        except Exception as e:
            messagebox.showerror("备份失败", str(e))

    def _clear_data(self):
        """清除所有数据"""
        if messagebox.askyesno("确认清除", "确定要清除所有数据吗？\n此操作不可撤销！\n\n建议先执行备份。"):
            try:
                self.storage.clear_data()
                self.analyzer.reset()
                self.alert_manager.reset()
                self._current_score = 0
                self._current_level = 1
                self._current_features = {}
                self._update_dashboard()
                self._update_db_stats()
                messagebox.showinfo("清除完成", "所有数据已清除")
            except Exception as e:
                messagebox.showerror("清除失败", str(e))

    # ==================== 预警弹窗 ====================

    def _show_alert_dialog(self, alert: dict):
        """显示预警弹窗（从任意线程安全调用）"""
        self.root.after(0, lambda: self._display_alert(alert))

    def _display_alert(self, alert: dict):
        """在主线程中显示预警对话框"""
        # 记录到存储
        self.storage.save_alert(
            alert_type=alert["type"],
            stress_level=alert["level"],
            message=alert["message"],
        )

        # 弹出温和提醒
        messagebox.showwarning(alert["title"], alert["message"])

    # ==================== 生命周期 ====================

    def _on_close(self):
        """关闭应用程序"""
        if self._is_collecting:
            if messagebox.askyesno("确认退出", "数据采集正在进行中，确定要退出吗？"):
                self._stop_collection()
            else:
                return

        # 清理资源
        self.storage.close()
        plt.close("all")
        logger.info("应用程序已关闭")
        self.root.destroy()

    def run(self):
        """运行主事件循环"""
        logger.info("启动主事件循环")
        self.root.mainloop()


# ==================== 程序入口 ====================

def main():
    """程序主入口"""
    print("=" * 50)
    print("  多模态交互压力数据分析系统")
    print("  Multimodal Interaction Stress Analysis System")
    print("=" * 50)
    print()

    if DEBUG_MODE:
        print("[调试模式] 已启用")
        if not PYNPUT_AVAILABLE:
            print("[调试模式] pynput不可用，将使用模拟数据")

    app = StressAnalysisApp()
    app.run()


if __name__ == "__main__":
    main()
