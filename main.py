"""
main.py - 主程序入口
多模态交互压力数据分析系统

功能：
- 主窗口与界面布局
- 实时仪表盘
- 历史数据查看
- 设置面板
- 数据管理
- 后台采集与分析调度

运行方式: python main.py
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from config import (
    debug_print, APP_NAME, APP_VERSION,
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    COLORS, FONT_FAMILY, FONT_FALLBACK,
    COLLECTION_INTERVAL, STRESS_LEVELS, STRESS_SOURCES,
)
from collector import DataCollector, PYNPUT_AVAILABLE
from analyzer import StressAnalyzer
from storage import StorageManager
from visualizer import ChartFactory
from alerts import AlertManager


class StressMonitorApp(tk.Tk):
    """
    主应用程序窗口

    整体结构：
    ┌─────────────────────────────────────────────┐
    │  顶部标题栏                                    │
    ├──────────┬──────────────────────────────────┤
    │  侧边栏  │  内容区                            │
    │          │  (仪表盘/历史/设置 切换)            │
    │  导航    │                                    │
    │  按钮    │                                    │
    │          │                                    │
    ├──────────┴──────────────────────────────────┤
    │  底部状态栏                                    │
    └─────────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        # 核心模块
        self.storage = StorageManager()
        self.collector = DataCollector()
        self.analyzer = StressAnalyzer()
        self.alert_manager = AlertManager(root_window=self, storage=self.storage)

        # 状态
        self._is_collecting = False
        self._collection_thread = None
        self._current_page = "dashboard"
        self._charts = {}  # 当前显示的图表引用

        # 窗口配置
        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(bg=COLORS["bg"])

        # 尝试设置窗口图标
        try:
            if sys.platform == "win32":
                self.iconbitmap(default="")
        except Exception:
            pass

        # 居中显示
        self.update_idletasks()
        x = (self.winfo_screenwidth() - WINDOW_WIDTH) // 2
        y = (self.winfo_screenheight() - WINDOW_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")

        # 构建界面
        self._build_ui()

        # 关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        debug_print("主窗口初始化完成")

    # ============================================================
    # 界面构建
    # ============================================================

    def _build_ui(self):
        """构建完整界面"""
        # 顶部标题栏
        self._build_header()
        # 主体区域（侧边栏 + 内容区）
        self._build_main_area()
        # 底部状态栏
        self._build_statusbar()
        # 默认显示仪表盘
        self._show_dashboard()

    def _build_header(self):
        """构建顶部标题栏"""
        header = tk.Frame(self, bg=COLORS["sidebar_bg"], height=55)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # Logo/标题
        title_frame = tk.Frame(header, bg=COLORS["sidebar_bg"])
        title_frame.pack(side=tk.LEFT, padx=15)

        tk.Label(title_frame, text="📊", font=(FONT_FAMILY, 20),
                bg=COLORS["sidebar_bg"]).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(title_frame, text=APP_NAME, font=(FONT_FAMILY, 14, "bold"),
                fg=COLORS["sidebar_fg"], bg=COLORS["sidebar_bg"]).pack(side=tk.LEFT)

        # 右侧：采集控制按钮
        ctrl_frame = tk.Frame(header, bg=COLORS["sidebar_bg"])
        ctrl_frame.pack(side=tk.RIGHT, padx=15)

        self._btn_toggle = tk.Button(
            ctrl_frame, text="▶ 开始采集", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["success"], fg="white", relief=tk.FLAT,
            padx=15, pady=4, cursor="hand2",
            command=self._toggle_collection
        )
        self._btn_toggle.pack(side=tk.RIGHT)

        # 状态指示灯
        self._status_dot = tk.Label(
            ctrl_frame, text="●", font=(FONT_FAMILY, 12),
            fg="#BDBDBD", bg=COLORS["sidebar_bg"]
        )
        self._status_dot.pack(side=tk.RIGHT, padx=10)

    def _build_main_area(self):
        """构建主体区域"""
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True)

        # 侧边栏
        self._build_sidebar(main)

        # 内容区
        self.content_frame = tk.Frame(main, bg=COLORS["bg"])
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _build_sidebar(self, parent):
        """构建侧边栏导航"""
        sidebar = tk.Frame(parent, bg=COLORS["sidebar_bg"], width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # 导航按钮
        nav_items = [
            ("📊", "实时仪表盘", "dashboard"),
            ("📅", "历史记录",   "history"),
            ("⚙️", "系统设置",   "settings"),
        ]

        self._nav_buttons = {}
        for emoji, label, page_id in nav_items:
            btn_frame = tk.Frame(sidebar, bg=COLORS["sidebar_bg"], cursor="hand2")
            btn_frame.pack(fill=tk.X, pady=1)

            btn = tk.Label(
                btn_frame, text=f"  {emoji}  {label}",
                font=(FONT_FAMILY, 11), anchor="w",
                fg=COLORS["sidebar_fg"], bg=COLORS["sidebar_bg"],
                padx=10, pady=12,
            )
            btn.pack(fill=tk.X)

            # 绑定点击事件
            btn.bind("<Button-1>", lambda e, pid=page_id: self._switch_page(pid))
            btn_frame.bind("<Button-1>", lambda e, pid=page_id: self._switch_page(pid))

            # hover 效果
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=COLORS["sidebar_sel"]))
            btn.bind("<Leave>", lambda e, b=btn, pid=page_id: (
                b.configure(bg=COLORS["sidebar_sel"] if self._current_page == pid else COLORS["sidebar_bg"])
            ))

            self._nav_buttons[page_id] = btn

        # 底部版本信息
        tk.Label(
            sidebar, text=f"v{APP_VERSION}",
            font=(FONT_FAMILY, 8), fg="#7F8C8D", bg=COLORS["sidebar_bg"]
        ).pack(side=tk.BOTTOM, pady=10)

        # pynput 状态提示
        if not PYNPUT_AVAILABLE:
            tk.Label(
                sidebar, text="⚠ 模拟模式",
                font=(FONT_FAMILY, 8), fg="#F39C12", bg=COLORS["sidebar_bg"]
            ).pack(side=tk.BOTTOM, pady=2)

    def _build_statusbar(self):
        """构建底部状态栏"""
        self.statusbar = tk.Frame(self, bg=COLORS["border"], height=28)
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self.statusbar.pack_propagate(False)

        self._status_label = tk.Label(
            self.statusbar, text="就绪",
            font=(FONT_FAMILY, 9), fg=COLORS["text_secondary"],
            bg=COLORS["border"], padx=10
        )
        self._status_label.pack(side=tk.LEFT)

        self._time_label = tk.Label(
            self.statusbar, text="",
            font=(FONT_FAMILY, 9), fg=COLORS["text_secondary"],
            bg=COLORS["border"], padx=10
        )
        self._time_label.pack(side=tk.RIGHT)

        # 更新时间
        self._update_time()

    # ============================================================
    # 页面切换
    # ============================================================

    def _switch_page(self, page_id):
        """切换页面"""
        self._current_page = page_id

        # 更新侧边栏高亮
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(bg=COLORS["sidebar_sel"])
            else:
                btn.configure(bg=COLORS["sidebar_bg"])

        # 清空内容区
        self._destroy_charts()
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # 显示对应页面
        if page_id == "dashboard":
            self._show_dashboard()
        elif page_id == "history":
            self._show_history()
        elif page_id == "settings":
            self._show_settings()

    # ============================================================
    # 仪表盘页面
    # ============================================================

    def _show_dashboard(self):
        """显示实时仪表盘"""
        container = tk.Frame(self.content_frame, bg=COLORS["bg"], padx=15, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        # ----- 顶部状态卡片行 -----
        cards_frame = tk.Frame(container, bg=COLORS["bg"])
        cards_frame.pack(fill=tk.X, pady=(0, 10))

        # 获取最新数据
        result = self.analyzer.get_latest_result()
        level = result.get("stress_level", 0)
        level_info = STRESS_LEVELS.get(level, STRESS_LEVELS[0])
        score = result.get("stress_score", 0)

        # 状态卡片
        status_cards = [
            ("当前压力", f"{level_info['emoji']} {level_info['name']}", level_info["color"]),
            ("压力指数", f"{score:.0f}/100", COLORS["accent"]),
            ("今日记录", f"{self.storage.get_record_count()} 条", COLORS["text_secondary"]),
            ("采集状态", "采集中" if self._is_collecting else "已停止",
             COLORS["success"] if self._is_collecting else COLORS["text_secondary"]),
        ]

        for i, (title, value, color) in enumerate(status_cards):
            card = tk.Frame(cards_frame, bg=COLORS["card_bg"],
                           relief=tk.FLAT, bd=1,
                           highlightbackground=COLORS["border"],
                           highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                     padx=(0 if i == 0 else 5, 0))

            tk.Label(card, text=title, font=(FONT_FAMILY, 9),
                    fg=COLORS["text_secondary"], bg=COLORS["card_bg"],
                    padx=12, pady=(8, 0)).pack(anchor="w")
            tk.Label(card, text=value, font=(FONT_FAMILY, 14, "bold"),
                    fg=color, bg=COLORS["card_bg"],
                    padx=12, pady=(0, 8)).pack(anchor="w")

        # ----- 中间：图表行 -----
        charts_frame = tk.Frame(container, bg=COLORS["bg"])
        charts_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 左侧：仪表盘 + 贡献占比
        left_chart_frame = tk.Frame(charts_frame, bg=COLORS["card_bg"],
                                    relief=tk.FLAT, bd=1,
                                    highlightbackground=COLORS["border"],
                                    highlightthickness=1)
        left_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))

        tk.Label(left_chart_frame, text="  压力仪表盘", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        gauge_frame = tk.Frame(left_chart_frame, bg=COLORS["card_bg"])
        gauge_frame.pack(fill=tk.BOTH, expand=True)
        self._create_gauge(gauge_frame, score, level)

        # 贡献占比
        contrib_frame = tk.Frame(left_chart_frame, bg=COLORS["card_bg"])
        contrib_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(left_chart_frame, text="  模态贡献占比", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(5, 0))

        contributions = self.analyzer.get_modality_contributions(result)
        self._create_contribution_chart(contrib_frame, contributions)

        # 右侧：趋势图
        right_chart_frame = tk.Frame(charts_frame, bg=COLORS["card_bg"],
                                     relief=tk.FLAT, bd=1,
                                     highlightbackground=COLORS["border"],
                                     highlightthickness=1)
        right_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(right_chart_frame, text="  今日压力趋势", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        trend_frame = tk.Frame(right_chart_frame, bg=COLORS["card_bg"])
        trend_frame.pack(fill=tk.BOTH, expand=True)

        records = self.storage.get_today_records()
        self._create_trend_chart(trend_frame, records, "day")

        # ----- 底部：压力来源 + 每小时分布 -----
        bottom_frame = tk.Frame(container, bg=COLORS["bg"])
        bottom_frame.pack(fill=tk.X)

        # 压力来源标签
        sources_card = tk.Frame(bottom_frame, bg=COLORS["card_bg"],
                               relief=tk.FLAT, bd=1,
                               highlightbackground=COLORS["border"],
                               highlightthickness=1)
        sources_card.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))

        tk.Label(sources_card, text="  当前压力来源", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 5))

        sources = result.get("stress_sources", [])
        if sources:
            for src in sources:
                src_name = STRESS_SOURCES.get(src, src)
                tk.Label(sources_card, text=f"  ⚠ {src_name}",
                        font=(FONT_FAMILY, 10), fg=COLORS["warning"],
                        bg=COLORS["card_bg"], anchor="w").pack(fill=tk.X, padx=10)
        else:
            tk.Label(sources_card, text="  ✅ 未检测到明显压力来源",
                    font=(FONT_FAMILY, 10), fg=COLORS["success"],
                    bg=COLORS["card_bg"], anchor="w").pack(fill=tk.X, padx=10)

        # 增加底部间距
        tk.Frame(sources_card, bg=COLORS["card_bg"], height=8).pack()

        # 每小时分布图
        hourly_card = tk.Frame(bottom_frame, bg=COLORS["card_bg"],
                              relief=tk.FLAT, bd=1,
                              highlightbackground=COLORS["border"],
                              highlightthickness=1)
        hourly_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(hourly_card, text="  今日各时段压力", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        hourly_frame = tk.Frame(hourly_card, bg=COLORS["card_bg"])
        hourly_frame.pack(fill=tk.BOTH, expand=True)

        hourly_data = self.storage.get_hourly_summary()
        self._create_hourly_chart(hourly_frame, hourly_data)

        # 保存容器引用（用于刷新）
        self._dashboard_container = container

    # ============================================================
    # 历史记录页面
    # ============================================================

    def _show_history(self):
        """显示历史记录页面"""
        container = tk.Frame(self.content_frame, bg=COLORS["bg"], padx=15, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        # ----- 工具栏 -----
        toolbar = tk.Frame(container, bg=COLORS["bg"])
        toolbar.pack(fill=tk.X, pady=(0, 10))

        tk.Label(toolbar, text="📅 历史数据", font=(FONT_FAMILY, 14, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["bg"]).pack(side=tk.LEFT)

        # 时间范围选择
        range_frame = tk.Frame(toolbar, bg=COLORS["bg"])
        range_frame.pack(side=tk.LEFT, padx=20)

        self._history_range = tk.StringVar(value="week")
        for text, value in [("今日", "day"), ("本周", "week"), ("本月", "month")]:
            rb = tk.Radiobutton(
                range_frame, text=text, variable=self._history_range, value=value,
                font=(FONT_FAMILY, 10), bg=COLORS["bg"], fg=COLORS["text_primary"],
                selectcolor=COLORS["bg"], activebackground=COLORS["bg"],
                command=lambda: self._refresh_history_page(container)
            )
            rb.pack(side=tk.LEFT, padx=5)

        # 导出按钮
        export_btn = tk.Button(
            toolbar, text="📥 导出 Excel", font=(FONT_FAMILY, 10),
            bg=COLORS["accent"], fg="white", relief=tk.FLAT,
            padx=12, pady=3, cursor="hand2",
            command=self._export_data
        )
        export_btn.pack(side=tk.RIGHT)

        # ----- 趋势图 -----
        chart_card = tk.Frame(container, bg=COLORS["card_bg"],
                             relief=tk.FLAT, bd=1,
                             highlightbackground=COLORS["border"],
                             highlightthickness=1)
        chart_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(chart_card, text="  压力趋势", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        self._history_chart_frame = tk.Frame(chart_card, bg=COLORS["card_bg"])
        self._history_chart_frame.pack(fill=tk.X, pady=5)

        # ----- 每日汇总柱状图 -----
        daily_card = tk.Frame(container, bg=COLORS["card_bg"],
                             relief=tk.FLAT, bd=1,
                             highlightbackground=COLORS["border"],
                             highlightthickness=1)
        daily_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(daily_card, text="  每日压力汇总", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        self._daily_chart_frame = tk.Frame(daily_card, bg=COLORS["card_bg"])
        self._daily_chart_frame.pack(fill=tk.X, pady=5)

        # ----- 数据表格 -----
        table_card = tk.Frame(container, bg=COLORS["card_bg"],
                             relief=tk.FLAT, bd=1,
                             highlightbackground=COLORS["border"],
                             highlightthickness=1)
        table_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(table_card, text="  详细记录", font=(FONT_FAMILY, 10, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        self._history_table_frame = tk.Frame(table_card, bg=COLORS["card_bg"])
        self._history_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 加载数据
        self._refresh_history_data()

    def _refresh_history_page(self, container):
        """刷新历史页面数据"""
        self._refresh_history_data()

    def _refresh_history_data(self):
        """刷新历史数据显示"""
        period = getattr(self, '_history_range', tk.StringVar(value="week")).get()
        records = self.storage.get_records_by_period(period)

        # 更新趋势图
        if hasattr(self, '_history_chart_frame'):
            for w in self._history_chart_frame.winfo_children():
                w.destroy()
            self._create_trend_chart(self._history_chart_frame, records, period)

        # 更新每日汇总图
        if hasattr(self, '_daily_chart_frame'):
            for w in self._daily_chart_frame.winfo_children():
                w.destroy()
            days = {"day": 1, "week": 7, "month": 30}.get(period, 7)
            daily = self.storage.get_daily_summary(days=days)
            self._create_daily_chart(self._daily_chart_frame, daily)

        # 更新表格
        if hasattr(self, '_history_table_frame'):
            for w in self._history_table_frame.winfo_children():
                w.destroy()
            self._create_data_table(self._history_table_frame, records[:100])

    def _create_data_table(self, parent, records):
        """创建数据表格"""
        columns = ("time", "score", "level", "sources", "keyboard", "mouse", "window")
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)

        # 表头
        headers = {
            "time": ("时间", 140),
            "score": ("压力分数", 80),
            "level": ("等级", 80),
            "sources": ("压力来源", 150),
            "keyboard": ("键盘(键/分)", 90),
            "mouse": ("鼠标(次/分)", 90),
            "window": ("窗口切换", 80),
        }
        for col, (text, width) in headers.items():
            tree.heading(col, text=text, anchor="center")
            tree.column(col, width=width, anchor="center")

        # 数据
        for r in records:
            sources = r.get("stress_sources", [])
            if isinstance(sources, list):
                source_text = "、".join([STRESS_SOURCES.get(s, s) for s in sources])
            else:
                source_text = ""

            tree.insert("", tk.END, values=(
                str(r.get("timestamp", ""))[:19],
                f"{r.get('stress_score', 0):.0f}",
                r.get("stress_level_name", ""),
                source_text or "—",
                f"{r.get('keyboard_speed', 0):.0f}",
                f"{r.get('mouse_click_freq', 0):.0f}",
                f"{r.get('window_switch_freq', 0):.0f}",
            ))

        # 滚动条
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ============================================================
    # 设置页面
    # ============================================================

    def _show_settings(self):
        """显示设置页面"""
        container = tk.Frame(self.content_frame, bg=COLORS["bg"], padx=15, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        # 标题
        tk.Label(container, text="⚙️ 系统设置", font=(FONT_FAMILY, 14, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["bg"]).pack(anchor="w", pady=(0, 15))

        # ---- 预警设置 ----
        alert_card = self._create_setting_card(container, "🔔 预警设置")

        alert_settings = self.alert_manager.get_settings()

        # 启用预警
        self._alert_enabled_var = tk.BooleanVar(value=alert_settings["enabled"])
        tk.Checkbutton(
            alert_card, text="启用压力预警提醒",
            variable=self._alert_enabled_var,
            font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
            command=self._save_alert_settings
        ).pack(anchor="w", padx=10, pady=5)

        # 高压力阈值
        threshold_frame = tk.Frame(alert_card, bg=COLORS["card_bg"])
        threshold_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(threshold_frame, text="连续高压力预警阈值:",
                font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
                fg=COLORS["text_primary"]).pack(side=tk.LEFT)

        self._high_threshold_var = tk.IntVar(value=alert_settings["high_threshold_minutes"])
        tk.Spinbox(threshold_frame, from_=5, to=60, width=5,
                  textvariable=self._high_threshold_var,
                  font=(FONT_FAMILY, 10),
                  command=self._save_alert_settings).pack(side=tk.LEFT, padx=5)
        tk.Label(threshold_frame, text="分钟",
                font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"]).pack(side=tk.LEFT)

        # 中等压力阈值
        med_frame = tk.Frame(alert_card, bg=COLORS["card_bg"])
        med_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(med_frame, text="连续中等压力预警阈值:",
                font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
                fg=COLORS["text_primary"]).pack(side=tk.LEFT)

        self._med_threshold_var = tk.IntVar(value=alert_settings["medium_threshold_minutes"])
        tk.Spinbox(med_frame, from_=10, to=120, width=5,
                  textvariable=self._med_threshold_var,
                  font=(FONT_FAMILY, 10),
                  command=self._save_alert_settings).pack(side=tk.LEFT, padx=5)
        tk.Label(med_frame, text="分钟",
                font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"]).pack(side=tk.LEFT)

        # 冷却时间
        cool_frame = tk.Frame(alert_card, bg=COLORS["card_bg"])
        cool_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        tk.Label(cool_frame, text="预警冷却时间:",
                font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
                fg=COLORS["text_primary"]).pack(side=tk.LEFT)

        self._cooldown_var = tk.IntVar(value=alert_settings["cooldown_minutes"])
        tk.Spinbox(cool_frame, from_=5, to=60, width=5,
                  textvariable=self._cooldown_var,
                  font=(FONT_FAMILY, 10),
                  command=self._save_alert_settings).pack(side=tk.LEFT, padx=5)
        tk.Label(cool_frame, text="分钟",
                font=(FONT_FAMILY, 10), bg=COLORS["card_bg"],
                fg=COLORS["text_secondary"]).pack(side=tk.LEFT)

        # ---- 数据管理 ----
        data_card = self._create_setting_card(container, "💾 数据管理")

        db_info = f"数据库大小: {self.storage.get_db_size()} KB | 总记录数: {self.storage.get_record_count()}"
        tk.Label(data_card, text=db_info,
                font=(FONT_FAMILY, 10), fg=COLORS["text_secondary"],
                bg=COLORS["card_bg"]).pack(anchor="w", padx=10, pady=5)

        btn_frame = tk.Frame(data_card, bg=COLORS["card_bg"])
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        tk.Button(btn_frame, text="📥 导出 Excel", font=(FONT_FAMILY, 10),
                 bg=COLORS["accent"], fg="white", relief=tk.FLAT,
                 padx=10, pady=3, cursor="hand2",
                 command=self._export_data).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_frame, text="💾 备份数据库", font=(FONT_FAMILY, 10),
                 bg=COLORS["success"], fg="white", relief=tk.FLAT,
                 padx=10, pady=3, cursor="hand2",
                 command=self._backup_data).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_frame, text="🗑 清除全部数据", font=(FONT_FAMILY, 10),
                 bg=COLORS["danger"], fg="white", relief=tk.FLAT,
                 padx=10, pady=3, cursor="hand2",
                 command=self._clear_data).pack(side=tk.LEFT)

        # ---- 关于 ----
        about_card = self._create_setting_card(container, "ℹ️ 关于")

        about_text = (
            f"多模态交互压力数据分析系统 v{APP_VERSION}\n\n"
            "一款面向办公用户的桌面端工具，通过分析键盘、鼠标、窗口切换等\n"
            "多模态交互数据，实时评估工作压力状态，提供健康干预建议。\n\n"
            "🔒 隐私声明：所有数据仅在本地处理和存储，绝不上传任何云端。\n"
            "仅采集行为统计特征（频率、速度等），不记录具体的键盘输入内容。"
        )
        tk.Label(about_card, text=about_text,
                font=(FONT_FAMILY, 10), fg=COLORS["text_secondary"],
                bg=COLORS["card_bg"], justify=tk.LEFT,
                wraplength=500).pack(anchor="w", padx=10, pady=10)

        # 可穿戴设备接口说明
        wearable_card = self._create_setting_card(container, "⌚ 可穿戴设备（预留接口）")
        wearable_text = (
            "当前版本已预留可穿戴设备数据接入接口。\n"
            "支持的数据类型：心率（BPM）、皮电响应（GSR）\n\n"
            "开发者可通过 DataCollector.update_wearable_data() 方法\n"
            "传入生理数据，系统会自动将其纳入压力评估模型。"
        )
        tk.Label(wearable_card, text=wearable_text,
                font=(FONT_FAMILY, 10), fg=COLORS["text_secondary"],
                bg=COLORS["card_bg"], justify=tk.LEFT,
                wraplength=500).pack(anchor="w", padx=10, pady=10)

    def _create_setting_card(self, parent, title):
        """创建设置卡片"""
        card = tk.Frame(parent, bg=COLORS["card_bg"],
                       relief=tk.FLAT, bd=1,
                       highlightbackground=COLORS["border"],
                       highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text=f"  {title}", font=(FONT_FAMILY, 11, "bold"),
                fg=COLORS["text_primary"], bg=COLORS["card_bg"],
                anchor="w").pack(fill=tk.X, padx=5, pady=(8, 0))

        sep = ttk.Separator(card, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, padx=10, pady=5)

        return card

    # ============================================================
    # 图表创建辅助方法
    # ============================================================

    def _create_gauge(self, parent, score, level):
        """创建仪表盘"""
        try:
            fig, canvas = ChartFactory.create_gauge_chart(parent, score, level, figsize=(3.2, 2.5))
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._charts["gauge"] = (fig, canvas)
        except Exception as e:
            debug_print(f"创建仪表盘失败: {e}")
            tk.Label(parent, text=f"压力指数: {score:.0f}", font=(FONT_FAMILY, 18, "bold"),
                    fg=STRESS_LEVELS.get(level, STRESS_LEVELS[0])["color"],
                    bg=COLORS["card_bg"]).pack(expand=True)

    def _create_contribution_chart(self, parent, contributions):
        """创建贡献占比图"""
        try:
            fig, canvas = ChartFactory.create_contribution_chart(parent, contributions, figsize=(3.2, 3))
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._charts["contribution"] = (fig, canvas)
        except Exception as e:
            debug_print(f"创建贡献图失败: {e}")

    def _create_trend_chart(self, parent, records, period):
        """创建趋势图"""
        try:
            fig, canvas = ChartFactory.create_trend_chart(parent, records, period, figsize=(6, 2.5))
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._charts["trend"] = (fig, canvas)
        except Exception as e:
            debug_print(f"创建趋势图失败: {e}")

    def _create_hourly_chart(self, parent, hourly_data):
        """创建每小时分布图"""
        try:
            fig, canvas = ChartFactory.create_hourly_chart(parent, hourly_data, figsize=(6, 2.5))
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._charts["hourly"] = (fig, canvas)
        except Exception as e:
            debug_print(f"创建小时分布图失败: {e}")

    def _create_daily_chart(self, parent, daily_summary):
        """创建每日汇总图"""
        try:
            fig, canvas = ChartFactory.create_daily_bar_chart(parent, daily_summary, figsize=(6, 2.5))
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._charts["daily"] = (fig, canvas)
        except Exception as e:
            debug_print(f"创建每日汇总图失败: {e}")

    def _destroy_charts(self):
        """销毁所有图表资源"""
        for key, (fig, canvas) in self._charts.items():
            try:
                ChartFactory.destroy_chart(fig, canvas)
            except Exception:
                pass
        self._charts.clear()

    # ============================================================
    # 采集控制
    # ============================================================

    def _toggle_collection(self):
        """切换采集状态"""
        if self._is_collecting:
            self._stop_collection()
        else:
            self._start_collection()

    def _start_collection(self):
        """开始数据采集"""
        self._is_collecting = True
        self.collector.start()

        # 更新 UI
        self._btn_toggle.configure(text="⏹ 停止采集", bg=COLORS["danger"])
        self._status_dot.configure(fg=COLORS["success"])
        self._update_status("正在采集数据...")

        # 启动采集循环
        self._schedule_collection()

        debug_print("采集已启动")

    def _stop_collection(self):
        """停止数据采集"""
        self._is_collecting = False
        self.collector.stop()

        # 更新 UI
        self._btn_toggle.configure(text="▶ 开始采集", bg=COLORS["success"])
        self._status_dot.configure(fg="#BDBDBD")
        self._update_status("采集已停止")

        debug_print("采集已停止")

    def _schedule_collection(self):
        """调度下一次采集"""
        if not self._is_collecting:
            return

        # 在后台线程中执行采集和分析
        def collect_and_analyze():
            try:
                if PYNPUT_AVAILABLE:
                    data = self.collector.collect_period_data()
                else:
                    data = self.collector.generate_simulated_data()

                result = self.analyzer.analyze(data)
                self.storage.save_result(result)

                # 检查预警
                self.alert_manager.check(result)

                # 在主线程中更新 UI
                self.after(0, self._refresh_dashboard)
                self.after(0, lambda: self._update_status(
                    f"最新分析: {result['stress_level_name']} "
                    f"({result['stress_score']:.0f}分)"
                ))

            except Exception as e:
                debug_print(f"采集分析出错: {e}")

        thread = threading.Thread(target=collect_and_analyze, daemon=True)
        thread.start()

        # 调度下一次
        self.after(COLLECTION_INTERVAL * 1000, self._schedule_collection)

    def _refresh_dashboard(self):
        """刷新仪表盘（如果当前在仪表盘页面）"""
        if self._current_page == "dashboard":
            self._switch_page("dashboard")

    # ============================================================
    # 数据操作
    # ============================================================

    def _export_data(self):
        """导出数据到 Excel"""
        try:
            filepath = self.storage.export_to_excel()
            if filepath:
                messagebox.showinfo("导出成功", f"数据已导出到:\n{filepath}")
            else:
                messagebox.showwarning("导出失败", "没有可导出的数据，或 pandas 未安装")
        except Exception as e:
            messagebox.showerror("导出失败", f"发生错误: {e}")

    def _backup_data(self):
        """备份数据库"""
        try:
            path = self.storage.backup_database()
            if path:
                messagebox.showinfo("备份成功", f"数据库已备份到:\n{path}")
            else:
                messagebox.showwarning("备份失败", "备份失败")
        except Exception as e:
            messagebox.showerror("备份失败", f"发生错误: {e}")

    def _clear_data(self):
        """清除所有数据"""
        if messagebox.askyesno("确认清除", "确定要清除所有数据吗？此操作不可恢复！\n\n"
                               "建议先使用「备份数据库」功能进行备份。"):
            self.storage.clear_all_data()
            messagebox.showinfo("已清除", "所有数据已清除")
            # 刷新当前页面
            self._switch_page(self._current_page)

    def _save_alert_settings(self):
        """保存预警设置"""
        try:
            self.alert_manager.set_enabled(self._alert_enabled_var.get())
            self.alert_manager.set_thresholds(
                high_minutes=self._high_threshold_var.get(),
                medium_minutes=self._med_threshold_var.get(),
                cooldown_minutes=self._cooldown_var.get(),
            )
            self._update_status("设置已保存")
        except Exception as e:
            debug_print(f"保存设置失败: {e}")

    # ============================================================
    # 辅助方法
    # ============================================================

    def _update_status(self, text):
        """更新状态栏"""
        self._status_label.configure(text=text)

    def _update_time(self):
        """更新时间显示"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._time_label.configure(text=now)
        self.after(1000, self._update_time)

    def _on_close(self):
        """关闭窗口"""
        if self._is_collecting:
            self._stop_collection()
        self._destroy_charts()
        self.destroy()


# ============================================================
# 程序入口
# ============================================================

def main():
    """主程序入口"""
    print("=" * 50)
    print(f"  {APP_NAME} v{APP_VERSION}")
    print(f"  启动中...")
    print("=" * 50)

    try:
        app = StressMonitorApp()
        app.mainloop()
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
