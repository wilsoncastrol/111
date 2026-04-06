"""
多模态交互压力数据分析系统 - 可视化模块
Matplotlib-based chart components for stress data visualization.
Supports Chinese display and embedding in Tkinter.
"""

import io
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # 非交互后端，适合嵌入Tkinter

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from datetime import datetime, timedelta

# FigureCanvasTkAgg 依赖 tkinter，延迟导入以支持无GUI环境
FigureCanvasTkAgg = None

def _get_figure_canvas_tkagg():
    """延迟导入 FigureCanvasTkAgg（仅在GUI模式下需要）"""
    global FigureCanvasTkAgg
    if FigureCanvasTkAgg is None:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as _FigureCanvasTkAgg
        FigureCanvasTkAgg = _FigureCanvasTkAgg
    return FigureCanvasTkAgg

from config import (
    STRESS_LEVELS,
    CHART_COLORS,
    FONT_FAMILY,
    FONT_FALLBACKS,
    logger,
)

# 配置中文字体
def _setup_chinese_font():
    """尝试设置中文字体"""
    import matplotlib.font_manager as fm
    available_fonts = [f.name for f in fm.fontManager.ttflist]

    for font in [FONT_FAMILY] + FONT_FALLBACKS:
        if font in available_fonts:
            plt.rcParams["font.sans-serif"] = [font]
            plt.rcParams["axes.unicode_minus"] = False
            logger.debug(f"使用中文字体: {font}")
            return font

    # 未找到中文字体，使用默认字体
    plt.rcParams["axes.unicode_minus"] = False
    logger.warning("未找到中文字体，图表中文可能无法正常显示")
    return None


_setup_chinese_font()


class StressVisualizer:
    """压力数据可视化组件"""

    def __init__(self):
        self.fig_size = (8, 4)
        self.dpi = 100
        logger.info("可视化组件已初始化")

    def create_realtime_gauge(self, score: float, level: int) -> Figure:
        """
        创建实时压力仪表盘（半圆仪表）
        score: 当前压力评分 (0-100)
        level: 压力等级 (0-3)
        """
        fig, ax = plt.subplots(figsize=(4, 2.5), subplot_kw={"projection": "polar"})

        # 半圆仪表配置
        theta_range = np.linspace(np.pi, 0, 100)

        # 绘制背景色带（四个等级区域）
        level_colors = [STRESS_LEVELS[i]["color"] for i in range(4)]
        boundaries = [0, 25, 50, 75, 100]

        for i in range(4):
            start_idx = boundaries[i]
            end_idx = boundaries[i + 1]
            theta_seg = theta_range[start_idx:end_idx]
            ax.fill_between(theta_seg, 0.6, 1.0, color=level_colors[i], alpha=0.3)

        # 绘制指针
        needle_angle = np.pi - (score / 100) * np.pi
        ax.plot([needle_angle, needle_angle], [0, 0.85], color="#333333", linewidth=2.5)
        ax.plot(needle_angle, 0.85, "o", color=STRESS_LEVELS[level]["color"], markersize=8)

        # 配置
        ax.set_ylim(0, 1.1)
        ax.set_thetamin(0)
        ax.set_thetamax(180)
        ax.set_yticklabels([])
        ax.set_xticklabels([])
        ax.spines["polar"].set_visible(False)
        ax.grid(False)

        # 标签
        fig.text(0.5, 0.15, f"{score:.0f}", ha="center", va="center",
                 fontsize=28, fontweight="bold", color=STRESS_LEVELS[level]["color"])
        fig.text(0.5, 0.02, STRESS_LEVELS[level]["name"], ha="center", va="center",
                 fontsize=14, color=STRESS_LEVELS[level]["color"])

        fig.patch.set_facecolor("white")
        fig.tight_layout(pad=0.5)
        return fig

    def create_trend_chart(self, df: pd.DataFrame, period: str = "day") -> Figure:
        """
        创建压力趋势折线图
        df: 包含timestamp和stress_score列的DataFrame
        period: 'day', 'week', 'month'
        """
        fig, ax = plt.subplots(figsize=self.fig_size, dpi=self.dpi)

        if df.empty:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=16, color="#999999", transform=ax.transAxes)
            fig.tight_layout()
            return fig

        # 确保timestamp是datetime类型
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # 绘制压力评分曲线
        ax.plot(df["timestamp"], df["stress_score"],
                color=CHART_COLORS["primary"], linewidth=1.5, alpha=0.8)

        # 填充区域颜色（根据压力等级）
        for level_id, level_info in STRESS_LEVELS.items():
            lower = [0, 25, 50, 75][level_id]
            upper = [25, 50, 75, 100][level_id]
            ax.axhspan(lower, upper, alpha=0.08, color=level_info["color"])

        # 添加等级分界线
        for threshold in [25, 50, 75]:
            ax.axhline(y=threshold, color="#CCCCCC", linestyle="--", linewidth=0.5)

        # 时间轴格式
        if period == "day":
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.set_xlabel("时间")
        elif period == "week":
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax.set_xlabel("日期")
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax.set_xlabel("日期")

        ax.set_ylabel("压力评分")
        ax.set_ylim(0, 100)
        ax.set_title(f"压力趋势 - {'今日' if period == 'day' else '本周' if period == 'week' else '本月'}")

        # 样式
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.autofmt_xdate()
        fig.tight_layout()
        return fig

    def create_modality_contribution(self, features: dict) -> Figure:
        """
        创建各模态贡献度雷达图
        features: 各模态的压力特征分数
        """
        fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={"projection": "polar"})

        # 选择要展示的模态
        display_labels = {
            "keyboard_rhythm": "键盘节奏",
            "keyboard_speed": "键盘速度",
            "mouse_activity": "鼠标活动",
            "scroll_intensity": "滚动强度",
            "window_switching": "窗口切换",
            "text_emotion": "文本情绪",
            "input_pauses": "输入停顿",
        }

        labels = []
        values = []
        for key, label in display_labels.items():
            if key in features:
                labels.append(label)
                values.append(features[key])

        if not values:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#999999", transform=ax.transAxes)
            return fig

        # 雷达图
        N = len(labels)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        values_plot = values + [values[0]]
        angles += [angles[0]]

        ax.plot(angles, values_plot, "o-", linewidth=1.5, color=CHART_COLORS["primary"])
        ax.fill(angles, values_plot, alpha=0.15, color=CHART_COLORS["primary"])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylim(0, 100)
        ax.set_title("模态贡献度", pad=20)
        fig.tight_layout()
        return fig

    def create_distribution_chart(self, df: pd.DataFrame) -> Figure:
        """
        创建压力等级分布饼图
        """
        fig, ax = plt.subplots(figsize=(4, 3.5), dpi=self.dpi)

        if df.empty:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#999999", transform=ax.transAxes)
            return fig

        # 统计各等级占比
        level_counts = df["stress_level"].value_counts().sort_index()
        labels = [STRESS_LEVELS[i]["name"] for i in level_counts.index]
        colors = [STRESS_LEVELS[i]["color"] for i in level_counts.index]
        sizes = level_counts.values

        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct="%1.1f%%",
            startangle=90, pctdistance=0.75
        )

        for text in autotexts:
            text.set_fontsize(10)
            text.set_fontweight("bold")

        ax.set_title("压力等级分布")
        fig.tight_layout()
        return fig

    def create_daily_bar_chart(self, df: pd.DataFrame) -> Figure:
        """
        创建每日平均压力柱状图
        """
        fig, ax = plt.subplots(figsize=self.fig_size, dpi=self.dpi)

        if df.empty:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#999999", transform=ax.transAxes)
            return fig

        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # 按日汇总
        df["date"] = df["timestamp"].dt.date
        daily = df.groupby("date")["stress_score"].mean().reset_index()

        # 根据分数给每个柱子着色
        colors = []
        for score in daily["stress_score"]:
            if score < 25:
                colors.append(STRESS_LEVELS[0]["color"])
            elif score < 50:
                colors.append(STRESS_LEVELS[1]["color"])
            elif score < 75:
                colors.append(STRESS_LEVELS[2]["color"])
            else:
                colors.append(STRESS_LEVELS[3]["color"])

        bars = ax.bar(range(len(daily)), daily["stress_score"], color=colors, alpha=0.8)

        ax.set_xticks(range(len(daily)))
        ax.set_xticklabels([str(d) for d in daily["date"]], rotation=45, fontsize=8)
        ax.set_ylabel("平均压力评分")
        ax.set_ylim(0, 100)
        ax.set_title("每日压力概况")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        fig.tight_layout()
        return fig

    @staticmethod
    def embed_in_tk(fig: Figure, parent_widget):
        """将Matplotlib图表嵌入Tkinter窗口"""
        canvas_class = _get_figure_canvas_tkagg()
        canvas = canvas_class(fig, master=parent_widget)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return canvas

    @staticmethod
    def update_canvas(canvas, new_fig: Figure):
        """更新已嵌入的图表"""
        canvas.figure = new_fig
        canvas.draw()

    @staticmethod
    def close_figure(fig: Figure):
        """安全关闭图表，释放内存"""
        plt.close(fig)
