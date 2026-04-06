"""
config.py - 全局配置与常量定义
多模态交互压力数据分析系统

包含：
- 数据采集参数
- 压力等级定义
- 界面配置
- 存储路径
- 调试开关
"""

import os
import sys
import platform

# ============================================================
# 调试模式 - 开发时设置为 True，可在控制台看到详细日志
# ============================================================
DEBUG = True

def debug_print(*args, **kwargs):
    """调试输出，仅在 DEBUG 模式下打印"""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

# ============================================================
# 应用信息
# ============================================================
APP_NAME = "多模态交互压力数据分析系统"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Stress Monitor Team"

# ============================================================
# 路径配置
# ============================================================
# 应用数据根目录（跨平台）
if platform.system() == "Windows":
    APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "StressMonitor")
elif platform.system() == "Darwin":
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "StressMonitor")
else:
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".stress_monitor")

# 数据库文件
DB_PATH = os.path.join(APP_DATA_DIR, "stress_data.db")
# 导出目录
EXPORT_DIR = os.path.join(APP_DATA_DIR, "exports")
# 备份目录
BACKUP_DIR = os.path.join(APP_DATA_DIR, "backups")
# 加密密钥文件
KEY_FILE = os.path.join(APP_DATA_DIR, ".keyfile")

# 确保目录存在
for d in [APP_DATA_DIR, EXPORT_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# 数据采集配置
# ============================================================
# 采集间隔（秒）—— 每隔多少秒汇总一次特征
COLLECTION_INTERVAL = 60

# 键盘采集
KEYBOARD_ENABLED = True

# 鼠标采集
MOUSE_ENABLED = True

# 窗口切换检测间隔（秒）
WINDOW_CHECK_INTERVAL = 5

# 文本情绪分析 —— 基于本地关键词词典
TEXT_ANALYSIS_ENABLED = True

# ============================================================
# 压力等级定义
# ============================================================
STRESS_LEVELS = {
    0: {"name": "低压力",   "color": "#4CAF50", "emoji": "😊", "description": "放松状态，工作节奏平稳"},
    1: {"name": "正常",     "color": "#2196F3", "emoji": "🙂", "description": "正常工作状态，压力适中"},
    2: {"name": "中等压力", "color": "#FF9800", "emoji": "😐", "description": "压力有所上升，建议适当休息"},
    3: {"name": "高压力",   "color": "#F44336", "emoji": "😰", "description": "压力较高，建议立即休息"},
}

# 压力来源标签
STRESS_SOURCES = {
    "task_overload":    "任务过载",
    "negative_emotion": "情绪负面",
    "fast_pace":        "节奏过快",
    "long_duration":    "持续工作时间过长",
    "frequent_switch":  "频繁切换任务",
}

# ============================================================
# 分析引擎参数
# ============================================================
# 各特征权重（总和为1.0）
FEATURE_WEIGHTS = {
    "keyboard_speed":     0.15,  # 键盘输入速度
    "keyboard_rhythm":    0.10,  # 键盘节奏变异
    "mouse_click_freq":   0.10,  # 鼠标点击频率
    "mouse_move_speed":   0.10,  # 鼠标移动速度
    "mouse_scroll_freq":  0.05,  # 滚动频率
    "window_switch_freq": 0.15,  # 窗口切换频率
    "text_sentiment":     0.15,  # 文本情绪得分
    "typing_pause":       0.10,  # 输入停顿模式
    "work_duration":      0.10,  # 连续工作时长
}

# 压力阈值（0-100分数映射到等级）
STRESS_THRESHOLDS = {
    "low":    (0, 25),     # 0-25: 低压力
    "normal": (25, 50),    # 25-50: 正常
    "medium": (50, 75),    # 50-75: 中等压力
    "high":   (75, 100),   # 75-100: 高压力
}

# ============================================================
# 预警配置
# ============================================================
# 连续高压力多少分钟触发预警
ALERT_HIGH_STRESS_MINUTES = 15
# 连续中等压力多少分钟触发预警
ALERT_MEDIUM_STRESS_MINUTES = 30
# 预警冷却时间（分钟）—— 两次预警之间的最小间隔
ALERT_COOLDOWN_MINUTES = 10

# ============================================================
# 可穿戴设备接口（预留）
# ============================================================
WEARABLE_ENABLED = False
WEARABLE_HEART_RATE_WEIGHT = 0.0   # 预留权重
WEARABLE_GSR_WEIGHT = 0.0          # 预留权重（皮电）

# ============================================================
# 界面配置
# ============================================================
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600

# 配色方案
COLORS = {
    "bg":           "#F5F5F5",
    "sidebar_bg":   "#2C3E50",
    "sidebar_fg":   "#ECF0F1",
    "sidebar_sel":  "#34495E",
    "card_bg":      "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
    "accent":       "#3498DB",
    "success":      "#27AE60",
    "warning":      "#F39C12",
    "danger":       "#E74C3C",
    "border":       "#E0E0E0",
}

# 字体配置
if platform.system() == "Windows":
    FONT_FAMILY = "Microsoft YaHei"
elif platform.system() == "Darwin":
    FONT_FAMILY = "PingFang SC"
else:
    FONT_FAMILY = "Noto Sans CJK SC"

FONT_FALLBACK = "Arial"

# ============================================================
# 本地情感词典（简化版 —— 用于离线文本情绪分析）
# ============================================================
NEGATIVE_WORDS = [
    "烦", "累", "崩溃", "头疼", "焦虑", "紧张", "压力", "难受", "烦躁",
    "生气", "愤怒", "沮丧", "失望", "无聊", "疲惫", "讨厌", "恼火",
    "抓狂", "绝望", "痛苦", "忧虑", "不安", "郁闷", "憋屈", "受够",
    "stupid", "angry", "stress", "tired", "exhausted", "frustrated",
    "anxious", "overwhelmed", "hate", "terrible", "awful", "damn",
    "deadline", "urgent", "asap", "emergency", "crisis",
]

POSITIVE_WORDS = [
    "开心", "愉快", "轻松", "棒", "太好了", "不错", "满意", "顺利",
    "完美", "舒服", "高兴", "快乐", "感谢", "谢谢", "哈哈", "加油",
    "good", "great", "nice", "happy", "wonderful", "excellent",
    "awesome", "perfect", "thanks", "love", "enjoy", "relax",
]

# ============================================================
# 放松建议库
# ============================================================
RELAXATION_TIPS = [
    "💡 建议站起来活动一下，走动 5 分钟",
    "💡 尝试做几次深呼吸：吸气 4 秒，保持 4 秒，呼气 4 秒",
    "💡 闭上眼睛休息 2 分钟，让大脑放松一下",
    "💡 看看窗外远处的景物，缓解眼部疲劳",
    "💡 喝一杯水，保持身体水分充足",
    "💡 做一组简单的颈部拉伸运动",
    "💡 听一首自己喜欢的轻音乐",
    "💡 和同事简单聊几句，换换心情",
    "💡 尝试使用番茄工作法：专注 25 分钟，休息 5 分钟",
    "💡 记录下当前让你感到压力的事情，写下来可以帮助理清思路",
]

debug_print(f"配置加载完成 | 数据目录: {APP_DATA_DIR}")
