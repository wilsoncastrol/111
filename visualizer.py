"""
visualizer.py - 图表可视化模块
多模态交互压力数据分析系统

功能：
- 压力趋势折线图（日/周/月）
- 各模态贡献占比饼图
- 压力仪表盘
- 每小时压力热力图
- 适配中文显示
- 嵌入 Tkinter 界面
"""

import platform
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("TkAgg")  # 必须在其他 matplotlib 导入前设置

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

from config import debug_print, STRESS_LEVELS, COLORS

# ============================================================
# 中文字体配置
# ============================================================
def setup_chinese_font():
    """配置 Matplotlib 中文字体支持"""
    system = platform.system()

    font_candidates = []
    if system == "Windows":
        font_candidates = ["Microsoft YaHei", "SimHei", "SimSun"]
    elif system == "Darwin":
        font_candidates = ["PingFang SC", "Heiti SC", "STHeiti"]
    else:
        font_candidates = [
            "Noto Sans CJK SC", "WenQuanYi Micro Hei",
            "WenQuanYi Zen Hei", "Droid Sans Fallback",
            "AR PL UMing CN",
        ]

    from matplotlib.font_manager import fontManager
    available = {f.name for f in fontManager.ttflist}

    for font in font_candidates:
        if font in available:
            plt.rcParams["font.sans-serif"] = [font, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            debug_print(f"Matplotlib 中文字体设置为: {font}")
            return font

    # 如果没找到中文字体，尝试使用 DejaVu Sans（可能中文显示为方块）
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    debug_print("警告: 未找到合适的中文字体，中文可能无法正确显示")
    return "DejaVu Sans"


# 初始化中文字体
CHINESE_FONT = setup_chinese_font()

# 统一图表样式
CHART_BG = "#FAFAFA"
CHART_GRID_COLOR = "#E8E8E8"
CHART_COLORS = ["#4CAF50", "#2196F3", "#FF9800", "#F44336"]  # 对应4个压力等级


class ChartFactory:
    """
    图表工厂类

    提供各种图表的创建方法，均返回 (Figure, Canvas) 用于嵌入 Tkinter
    """

    @staticmethod
    def create_trend_chart(parent, records, period="day", figsize=(7, 3)):
        """
        创建压力趋势折线图

        参数:
            parent: Tkinter 父组件
            records: 压力记录列表
            period: "day"/"week"/"month"
            figsize: 图表大小
        """
        fig = Figure(figsize=figsize, dpi=100, facecolor=CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)

        if not records:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#BDBDBD", transform=ax.transAxes)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
        else:
            # 按时间排序（升序）
            sorted_records = sorted(records, key=lambda r: r.get("timestamp", ""))

            timestamps = []
            scores = []
            levels = []
            for r in sorted_records:
                ts = r.get("timestamp", "")
                if isinstance(ts, str):
                    try:
                        ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                timestamps.append(ts)
                scores.append(r.get("stress_score", 0))
                levels.append(r.get("stress_level", 0))

            if timestamps:
                # 绘制填充区域背景（压力等级色带）
                ax.axhspan(0, 25, alpha=0.1, color="#4CAF50")
                ax.axhspan(25, 50, alpha=0.1, color="#2196F3")
                ax.axhspan(50, 75, alpha=0.1, color="#FF9800")
                ax.axhspan(75, 100, alpha=0.1, color="#F44336")

                # 绘制主线
                ax.plot(timestamps, scores, color="#3498DB", linewidth=2,
                       marker="o", markersize=3, alpha=0.9, zorder=3)

                # 渐变填充
                ax.fill_between(timestamps, scores, alpha=0.15, color="#3498DB")

                # 坐标轴设置
                ax.set_ylim(0, 100)
                ax.set_ylabel("压力分数", fontsize=10)
                ax.grid(True, alpha=0.3, color=CHART_GRID_COLOR)

                # 时间轴格式
                if period == "day":
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
                elif period == "week":
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
                else:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))

                fig.autofmt_xdate(rotation=30, ha="right")

                # 等级标签
                ax.set_yticks([12.5, 37.5, 62.5, 87.5])
                ax.set_yticklabels(["低压力", "正常", "中等", "高压力"], fontsize=8)

        fig.tight_layout(pad=1.0)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()

        return fig, canvas

    @staticmethod
    def create_contribution_chart(parent, contributions, figsize=(3.5, 3.5)):
        """
        创建各模态贡献占比饼图

        参数:
            parent: Tkinter 父组件
            contributions: dict {模态名称: 贡献百分比}
        """
        fig = Figure(figsize=figsize, dpi=100, facecolor=CHART_BG)
        ax = fig.add_subplot(111)

        if not contributions or all(v == 0 for v in contributions.values()):
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#BDBDBD", transform=ax.transAxes)
            ax.axis("off")
        else:
            labels = list(contributions.keys())
            sizes = list(contributions.values())

            # 过滤掉 0 值
            nonzero = [(l, s) for l, s in zip(labels, sizes) if s > 0]
            if nonzero:
                labels, sizes = zip(*nonzero)
            else:
                labels, sizes = ["无数据"], [100]

            pie_colors = ["#5C6BC0", "#26A69A", "#FFA726", "#EF5350",
                         "#AB47BC", "#42A5F5", "#66BB6A"]

            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct="%1.0f%%",
                colors=pie_colors[:len(sizes)],
                startangle=90, pctdistance=0.75,
                wedgeprops=dict(width=0.4, edgecolor="white"),
                textprops={"fontsize": 9},
            )

            for autotext in autotexts:
                autotext.set_fontsize(8)
                autotext.set_color("white")

            ax.set_title("各模态贡献占比", fontsize=11, pad=10)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()

        return fig, canvas

    @staticmethod
    def create_gauge_chart(parent, score, level, figsize=(3, 2.5)):
        """
        创建压力仪表盘

        参数:
            parent: Tkinter 父组件
            score: 压力分数 (0-100)
            level: 压力等级 (0-3)
        """
        fig = Figure(figsize=figsize, dpi=100, facecolor=CHART_BG)
        ax = fig.add_subplot(111, polar=True)

        # 仪表盘设置
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)

        # 绘制背景弧
        theta_ranges = [
            (np.linspace(np.pi * 0.75, np.pi * 0.9375, 50), "#4CAF50", 0.3),
            (np.linspace(np.pi * 0.9375, np.pi * 1.125, 50), "#2196F3", 0.3),
            (np.linspace(np.pi * 1.125, np.pi * 1.3125, 50), "#FF9800", 0.3),
            (np.linspace(np.pi * 1.3125, np.pi * 1.5, 50), "#F44336", 0.3),
        ]

        for thetas, color, alpha in theta_ranges:
            ax.fill_between(thetas, 0.6, 1.0, alpha=alpha, color=color)

        # 指针位置
        needle_angle = np.pi * 0.75 + (score / 100) * np.pi * 0.75

        # 绘制指针
        ax.annotate(
            "", xy=(needle_angle, 0.95), xytext=(needle_angle, 0.1),
            arrowprops=dict(arrowstyle="->", color="#333333", lw=2.5)
        )

        # 中心圆
        circle = plt.Circle((0, 0), 0.15, transform=ax.transData,
                            color="white", zorder=5)
        ax.add_patch(circle)

        # 分数文字
        level_info = STRESS_LEVELS.get(level, STRESS_LEVELS[0])
        ax.text(0, -0.35, f"{score:.0f}", ha="center", va="center",
               fontsize=24, fontweight="bold", color=level_info["color"],
               transform=ax.transAxes)
        ax.text(0, -0.50, level_info["name"], ha="center", va="center",
               fontsize=11, color=level_info["color"], transform=ax.transAxes)

        # 隐藏网格和刻度
        ax.set_ylim(0, 1.1)
        ax.set_yticklabels([])
        ax.set_xticklabels([])
        ax.grid(False)
        ax.spines["polar"].set_visible(False)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()

        return fig, canvas

    @staticmethod
    def create_daily_bar_chart(parent, daily_summary, figsize=(7, 3)):
        """
        创建每日压力柱状图

        参数:
            parent: Tkinter 父组件
            daily_summary: 每日汇总数据列表
        """
        fig = Figure(figsize=figsize, dpi=100, facecolor=CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)

        if not daily_summary:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#BDBDBD", transform=ax.transAxes)
            ax.axis("off")
        else:
            dates = [d["date"] for d in daily_summary]
            avg_scores = [d["avg_score"] for d in daily_summary]
            max_scores = [d["max_score"] for d in daily_summary]

            x = range(len(dates))
            width = 0.35

            # 根据分数给柱子上色
            avg_colors = []
            for s in avg_scores:
                if s < 25:
                    avg_colors.append("#4CAF50")
                elif s < 50:
                    avg_colors.append("#2196F3")
                elif s < 75:
                    avg_colors.append("#FF9800")
                else:
                    avg_colors.append("#F44336")

            bars1 = ax.bar([i - width/2 for i in x], avg_scores, width,
                          label="平均压力", color=avg_colors, alpha=0.8)
            bars2 = ax.bar([i + width/2 for i in x], max_scores, width,
                          label="最高压力", color="#E0E0E0", alpha=0.6)

            ax.set_ylim(0, 100)
            ax.set_ylabel("压力分数", fontsize=10)
            ax.set_xticks(list(x))
            # 简化日期标签
            short_dates = [d[-5:] for d in dates]  # "MM-DD"
            ax.set_xticklabels(short_dates, rotation=45, ha="right", fontsize=8)
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(axis="y", alpha=0.3)

        fig.tight_layout(pad=1.0)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()

        return fig, canvas

    @staticmethod
    def create_hourly_chart(parent, hourly_summary, figsize=(7, 3)):
        """
        创建每小时压力分布图

        参数:
            parent: Tkinter 父组件
            hourly_summary: 每小时汇总数据列表
        """
        fig = Figure(figsize=figsize, dpi=100, facecolor=CHART_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(CHART_BG)

        if not hourly_summary:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=14, color="#BDBDBD", transform=ax.transAxes)
            ax.axis("off")
        else:
            hours = [d["hour"] for d in hourly_summary]
            scores = [d["avg_score"] for d in hourly_summary]

            # 完整24小时
            full_hours = list(range(24))
            full_scores = [0] * 24
            for h, s in zip(hours, scores):
                if 0 <= h < 24:
                    full_scores[h] = s

            colors = []
            for s in full_scores:
                if s == 0:
                    colors.append("#E0E0E0")
                elif s < 25:
                    colors.append("#4CAF50")
                elif s < 50:
                    colors.append("#2196F3")
                elif s < 75:
                    colors.append("#FF9800")
                else:
                    colors.append("#F44336")

            ax.bar(full_hours, full_scores, color=colors, alpha=0.8, width=0.8)
            ax.set_ylim(0, 100)
            ax.set_xlabel("小时", fontsize=10)
            ax.set_ylabel("平均压力", fontsize=10)
            ax.set_xticks(range(0, 24, 2))
            ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)], fontsize=8)
            ax.grid(axis="y", alpha=0.3)
            ax.set_title("今日各时段压力分布", fontsize=11)

        fig.tight_layout(pad=1.0)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()

        return fig, canvas

    @staticmethod
    def destroy_chart(fig, canvas):
        """安全销毁图表资源"""
        try:
            canvas.get_tk_widget().destroy()
            plt.close(fig)
        except Exception:
            pass
