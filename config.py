"""
多模态交互压力数据分析系统 - 全局配置模块
Global configuration and constants for the Multimodal Interaction Stress Analysis System.
"""

import os
import logging

# ==================== 基本路径配置 ====================
# 应用数据目录（用户主目录下）
APP_NAME = "StressAnalyzer"
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")
DB_PATH = os.path.join(APP_DATA_DIR, "stress_data.db")
LOG_PATH = os.path.join(APP_DATA_DIR, "app.log")
BACKUP_DIR = os.path.join(APP_DATA_DIR, "backups")

# 确保目录存在
os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# ==================== 日志配置 ====================
DEBUG_MODE = True
LOG_LEVEL = logging.DEBUG if DEBUG_MODE else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(APP_NAME)

# ==================== 数据采集配置 ====================
# 采集间隔（秒）
COLLECTION_INTERVAL = 5  # 每5秒采集一次特征快照
# 键盘缓冲区大小
KEYBOARD_BUFFER_SIZE = 100
# 鼠标采样率（事件/秒）
MOUSE_SAMPLE_RATE = 10

# ==================== 压力分析配置 ====================
# 压力等级定义
STRESS_LEVELS = {
    0: {"name": "低压力", "color": "#4CAF50", "en": "Low"},
    1: {"name": "正常", "color": "#2196F3", "en": "Normal"},
    2: {"name": "中等压力", "color": "#FF9800", "en": "Moderate"},
    3: {"name": "高压力", "color": "#F44336", "en": "High"},
}

# 压力来源标签
STRESS_SOURCES = {
    "task_overload": "任务过载",
    "negative_emotion": "情绪负面",
    "fast_pace": "节奏过快",
    "long_session": "长时间工作",
    "frequent_switching": "频繁切换",
}

# 分析窗口（秒）- 用于计算滑动窗口特征
ANALYSIS_WINDOW = 300  # 5分钟

# 压力等级阈值（基于综合评分 0-100）
STRESS_THRESHOLDS = {
    "low": 25,       # 0-25: 低压力
    "normal": 50,    # 25-50: 正常
    "moderate": 75,  # 50-75: 中等压力
    # 75-100: 高压力
}

# ==================== 预警配置 ====================
# 高压力持续时间阈值（秒）
HIGH_STRESS_DURATION_THRESHOLD = 1800  # 30分钟
# 预警冷却时间（秒）- 避免频繁弹窗
ALERT_COOLDOWN = 600  # 10分钟
# 建议休息时长（分钟）
SUGGESTED_BREAK_DURATION = 15

# ==================== 可视化配置 ====================
# 图表颜色方案
CHART_COLORS = {
    "primary": "#2196F3",
    "secondary": "#FF9800",
    "success": "#4CAF50",
    "danger": "#F44336",
    "background": "#FAFAFA",
    "text": "#333333",
}

# 中文字体配置（Matplotlib）
FONT_FAMILY = "SimHei"  # 黑体，Windows常用
FONT_FALLBACKS = ["Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]

# ==================== 界面配置 ====================
WINDOW_TITLE = "多模态交互压力数据分析系统"
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 650
THEME_BG = "#F5F5F5"
THEME_FG = "#333333"
THEME_ACCENT = "#2196F3"

# ==================== 数据加密配置 ====================
# 加密密钥（实际使用时应从安全存储获取或由用户设置）
ENCRYPTION_ENABLED = True

# ==================== 可穿戴设备接口配置（预留） ====================
WEARABLE_ENABLED = False
WEARABLE_DEVICE_TYPES = ["heart_rate", "skin_conductance"]
WEARABLE_SAMPLE_RATE = 1  # Hz

# ==================== 导出配置 ====================
EXPORT_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
EXPORT_FILENAME_TEMPLATE = "stress_report_{date}.xlsx"


def get_stress_level(score: float) -> int:
    """根据压力评分返回压力等级（0-3）"""
    if score < STRESS_THRESHOLDS["low"]:
        return 0
    elif score < STRESS_THRESHOLDS["normal"]:
        return 1
    elif score < STRESS_THRESHOLDS["moderate"]:
        return 2
    else:
        return 3


def get_stress_name(level: int) -> str:
    """获取压力等级的中文名称"""
    return STRESS_LEVELS.get(level, {}).get("name", "未知")


def get_stress_color(level: int) -> str:
    """获取压力等级对应的颜色"""
    return STRESS_LEVELS.get(level, {}).get("color", "#999999")


if DEBUG_MODE:
    logger.debug("配置模块已加载，调试模式已开启")
    logger.debug(f"数据目录: {APP_DATA_DIR}")
    logger.debug(f"数据库路径: {DB_PATH}")
