"""
alerts.py - 预警干预模块
多模态交互压力数据分析系统

功能：
- 连续高压力检测
- 温和的弹窗提醒
- 放松建议推送
- 自定义预警规则
- 预警记录存储
"""

import time
import random
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from config import (
    debug_print, STRESS_LEVELS, RELAXATION_TIPS,
    ALERT_HIGH_STRESS_MINUTES, ALERT_MEDIUM_STRESS_MINUTES,
    ALERT_COOLDOWN_MINUTES, COLORS, FONT_FAMILY,
)


class AlertManager:
    """
    预警管理器

    持续监测压力状态，当检测到：
    - 连续高压力超过阈值（默认15分钟）
    - 连续中等压力超过阈值（默认30分钟）
    时触发温和提醒，给出休息建议和放松技巧
    """

    def __init__(self, root_window=None, storage=None):
        self._root = root_window
        self._storage = storage

        # 预警状态
        self._high_stress_start = None     # 连续高压力开始时间
        self._medium_stress_start = None   # 连续中等压力开始时间
        self._last_alert_time = None       # 上次预警时间
        self._alert_count = 0              # 今日预警次数

        # 自定义设置
        self._high_threshold_minutes = ALERT_HIGH_STRESS_MINUTES
        self._medium_threshold_minutes = ALERT_MEDIUM_STRESS_MINUTES
        self._cooldown_minutes = ALERT_COOLDOWN_MINUTES
        self._enabled = True

        # 从存储加载设置
        self._load_settings()

        # 回调函数
        self._on_alert_callbacks = []

        debug_print("AlertManager 初始化完成")

    # ============================================================
    # 预警检测
    # ============================================================

    def check(self, result):
        """
        检查分析结果，判断是否需要触发预警

        参数:
            result: 分析引擎返回的结果字典

        返回:
            bool: 是否触发了预警
        """
        if not self._enabled:
            return False

        level = result.get("stress_level", 0)
        now = datetime.now()

        # 检查冷却时间
        if self._last_alert_time:
            elapsed = (now - self._last_alert_time).total_seconds() / 60
            if elapsed < self._cooldown_minutes:
                return False

        triggered = False

        # 高压力检测
        if level >= 3:
            if self._high_stress_start is None:
                self._high_stress_start = now
            else:
                duration = (now - self._high_stress_start).total_seconds() / 60
                if duration >= self._high_threshold_minutes:
                    self._trigger_alert(result, "high")
                    self._high_stress_start = None
                    triggered = True
        else:
            self._high_stress_start = None

        # 中等压力检测
        if level >= 2 and not triggered:
            if self._medium_stress_start is None:
                self._medium_stress_start = now
            else:
                duration = (now - self._medium_stress_start).total_seconds() / 60
                if duration >= self._medium_threshold_minutes:
                    self._trigger_alert(result, "medium")
                    self._medium_stress_start = None
                    triggered = True
        elif level < 2:
            self._medium_stress_start = None

        return triggered

    def _trigger_alert(self, result, alert_type):
        """触发预警"""
        now = datetime.now()
        self._last_alert_time = now
        self._alert_count += 1

        level = result.get("stress_level", 2)
        score = result.get("stress_score", 50)
        level_info = STRESS_LEVELS.get(level, STRESS_LEVELS[2])
        tip = random.choice(RELAXATION_TIPS)

        if alert_type == "high":
            message = f"检测到您已持续处于高压力状态超过 {self._high_threshold_minutes} 分钟"
        else:
            message = f"检测到您已持续处于中等压力状态超过 {self._medium_threshold_minutes} 分钟"

        debug_print(f"触发预警: type={alert_type}, score={score}, level={level_info['name']}")

        # 保存预警记录
        if self._storage:
            self._storage.save_alert(level, message)

        # 显示弹窗
        if self._root:
            self._root.after(0, lambda: self._show_alert_dialog(
                level_info, message, tip, score
            ))

        # 触发回调
        for callback in self._on_alert_callbacks:
            try:
                callback(result, message)
            except Exception as e:
                debug_print(f"预警回调执行失败: {e}")

    # ============================================================
    # 预警弹窗
    # ============================================================

    def _show_alert_dialog(self, level_info, message, tip, score):
        """显示温和的预警弹窗"""
        try:
            dialog = tk.Toplevel(self._root)
            dialog.title("💡 温馨提醒")
            dialog.geometry("420x380")
            dialog.resizable(False, False)
            dialog.configure(bg="white")

            # 使弹窗置顶但不是模态的（不强制阻塞用户）
            dialog.attributes("-topmost", True)

            # 顶部横条（压力等级颜色）
            color_bar = tk.Frame(dialog, bg=level_info["color"], height=6)
            color_bar.pack(fill=tk.X)

            # 内容区
            content = tk.Frame(dialog, bg="white", padx=25, pady=20)
            content.pack(fill=tk.BOTH, expand=True)

            # emoji 和状态
            emoji_label = tk.Label(content, text=level_info["emoji"],
                                  font=(FONT_FAMILY, 36), bg="white")
            emoji_label.pack()

            status_label = tk.Label(content, text=level_info["name"],
                                   font=(FONT_FAMILY, 16, "bold"),
                                   fg=level_info["color"], bg="white")
            status_label.pack(pady=(5, 10))

            # 压力分数
            score_label = tk.Label(content, text=f"当前压力指数: {score:.0f}/100",
                                  font=(FONT_FAMILY, 11),
                                  fg=COLORS["text_secondary"], bg="white")
            score_label.pack()

            # 提示信息
            msg_label = tk.Label(content, text=message,
                                font=(FONT_FAMILY, 10),
                                fg=COLORS["text_primary"], bg="white",
                                wraplength=360, justify=tk.LEFT)
            msg_label.pack(pady=(15, 10))

            # 分隔线
            sep = ttk.Separator(content, orient=tk.HORIZONTAL)
            sep.pack(fill=tk.X, pady=5)

            # 放松建议
            tip_label = tk.Label(content, text=tip,
                                font=(FONT_FAMILY, 10),
                                fg=COLORS["accent"], bg="white",
                                wraplength=360, justify=tk.LEFT)
            tip_label.pack(pady=10)

            # 按钮区
            btn_frame = tk.Frame(content, bg="white")
            btn_frame.pack(fill=tk.X, pady=(10, 0))

            # "好的，我知道了" 按钮
            ok_btn = tk.Button(
                btn_frame, text="好的，我知道了",
                font=(FONT_FAMILY, 10),
                bg=COLORS["accent"], fg="white",
                relief=tk.FLAT, padx=20, pady=6,
                cursor="hand2",
                command=dialog.destroy
            )
            ok_btn.pack(side=tk.RIGHT)

            # "暂停提醒" 按钮
            pause_btn = tk.Button(
                btn_frame, text="暂停 30 分钟",
                font=(FONT_FAMILY, 10),
                bg=COLORS["border"], fg=COLORS["text_secondary"],
                relief=tk.FLAT, padx=15, pady=6,
                cursor="hand2",
                command=lambda: self._pause_alerts(30, dialog)
            )
            pause_btn.pack(side=tk.RIGHT, padx=(0, 10))

            # 居中显示
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() - 420) // 2
            y = (dialog.winfo_screenheight() - 380) // 2
            dialog.geometry(f"+{x}+{y}")

        except Exception as e:
            debug_print(f"显示预警弹窗失败: {e}")

    def _pause_alerts(self, minutes, dialog):
        """暂停预警指定分钟数"""
        self._last_alert_time = datetime.now() + timedelta(minutes=minutes)
        debug_print(f"预警已暂停 {minutes} 分钟")
        dialog.destroy()

    # ============================================================
    # 设置管理
    # ============================================================

    def set_enabled(self, enabled):
        """启用/禁用预警"""
        self._enabled = enabled
        self._save_settings()

    def set_thresholds(self, high_minutes=None, medium_minutes=None, cooldown_minutes=None):
        """设置预警阈值"""
        if high_minutes is not None:
            self._high_threshold_minutes = high_minutes
        if medium_minutes is not None:
            self._medium_threshold_minutes = medium_minutes
        if cooldown_minutes is not None:
            self._cooldown_minutes = cooldown_minutes
        self._save_settings()

    def get_settings(self):
        """获取当前设置"""
        return {
            "enabled": self._enabled,
            "high_threshold_minutes": self._high_threshold_minutes,
            "medium_threshold_minutes": self._medium_threshold_minutes,
            "cooldown_minutes": self._cooldown_minutes,
        }

    def on_alert(self, callback):
        """注册预警回调"""
        self._on_alert_callbacks.append(callback)

    def _save_settings(self):
        """保存设置到数据库"""
        if self._storage:
            self._storage.save_setting("alert_settings", self.get_settings())

    def _load_settings(self):
        """从数据库加载设置"""
        if self._storage:
            settings = self._storage.get_setting("alert_settings")
            if settings:
                self._enabled = settings.get("enabled", True)
                self._high_threshold_minutes = settings.get("high_threshold_minutes", ALERT_HIGH_STRESS_MINUTES)
                self._medium_threshold_minutes = settings.get("medium_threshold_minutes", ALERT_MEDIUM_STRESS_MINUTES)
                self._cooldown_minutes = settings.get("cooldown_minutes", ALERT_COOLDOWN_MINUTES)

    def reset_state(self):
        """重置预警状态（新的一天时调用）"""
        self._high_stress_start = None
        self._medium_stress_start = None
        self._alert_count = 0
