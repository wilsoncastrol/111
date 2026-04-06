"""
多模态交互压力数据分析系统 - 预警干预模块
Alert and intervention system for high stress detection.
"""

import time
import threading
from datetime import datetime
from typing import Optional, Callable

from config import (
    HIGH_STRESS_DURATION_THRESHOLD,
    ALERT_COOLDOWN,
    SUGGESTED_BREAK_DURATION,
    STRESS_LEVELS,
    get_stress_name,
    logger,
)


# 放松建议库
RELAXATION_TIPS = [
    "🧘 试试深呼吸：吸气4秒 → 屏息4秒 → 呼气6秒，重复5次",
    "👀 眼睛休息：每20分钟看20英尺(6米)外的物体20秒",
    "🚶 起身活动：站起来走动2-3分钟，伸展一下身体",
    "💧 补充水分：喝一杯温水，保持身体水分充足",
    "🎵 听听音乐：播放一首舒缓的音乐，放松心情",
    "✋ 手部拉伸：轻轻握拳再张开，重复10次，缓解手部疲劳",
    "🌿 转移注意力：看看窗外的绿色植物，让眼睛和大脑都休息一下",
    "😊 微笑练习：对自己微笑30秒，释放正面荷尔蒙",
    "📝 写下感受：用2分钟写下当前的想法和感受，释放压力",
    "⏰ 番茄工作法：工作25分钟后休息5分钟，保持高效节奏",
]


class AlertManager:
    """
    预警干预管理器
    监测持续高压力状态，在合适时机提供温和提醒和建议
    """

    def __init__(self):
        # 高压力持续计时
        self._high_stress_start: Optional[float] = None
        self._high_stress_duration: float = 0

        # 上次预警时间（避免频繁弹窗）
        self._last_alert_time: float = 0

        # 预警回调函数
        self._alert_callback: Optional[Callable] = None

        # 用户自定义规则
        self._custom_rules = {
            "high_stress_threshold": HIGH_STRESS_DURATION_THRESHOLD,
            "alert_cooldown": ALERT_COOLDOWN,
            "break_duration": SUGGESTED_BREAK_DURATION,
            "enabled": True,
        }

        # 放松建议索引
        self._tip_index = 0

        # 预警历史
        self._alert_history = []

        logger.info("预警管理器已初始化")

    def set_alert_callback(self, callback: Callable):
        """设置预警回调函数（通常是显示弹窗的函数）"""
        self._alert_callback = callback

    def update_rules(self, rules: dict):
        """更新自定义预警规则"""
        self._custom_rules.update(rules)
        logger.info(f"预警规则已更新: {self._custom_rules}")

    def get_rules(self) -> dict:
        """获取当前预警规则"""
        return self._custom_rules.copy()

    def check_stress(self, stress_level: int, stress_score: float) -> Optional[dict]:
        """
        检查当前压力状态，必要时触发预警
        返回预警信息或None
        """
        if not self._custom_rules.get("enabled", True):
            return None

        current_time = time.time()

        # 高压力状态追踪
        if stress_level >= 3:  # 高压力
            if self._high_stress_start is None:
                self._high_stress_start = current_time
                logger.debug("检测到高压力状态开始")

            self._high_stress_duration = current_time - self._high_stress_start

            # 检查是否需要触发预警
            threshold = self._custom_rules.get("high_stress_threshold", HIGH_STRESS_DURATION_THRESHOLD)
            cooldown = self._custom_rules.get("alert_cooldown", ALERT_COOLDOWN)

            if (self._high_stress_duration >= threshold
                    and current_time - self._last_alert_time >= cooldown):
                return self._trigger_alert(stress_level, stress_score, "high_stress_duration")

        elif stress_level >= 2:  # 中等压力
            # 中等压力时，重置高压力计时但保留关注
            if self._high_stress_start is not None:
                # 如果之前是高压力，现在降到中等，重置计时
                self._high_stress_start = None
                self._high_stress_duration = 0

        else:
            # 低压力/正常，完全重置
            self._high_stress_start = None
            self._high_stress_duration = 0

        return None

    def _trigger_alert(self, stress_level: int, stress_score: float, alert_type: str) -> dict:
        """触发一次预警"""
        self._last_alert_time = time.time()

        # 获取放松建议
        tip = self._get_next_tip()
        break_mins = self._custom_rules.get("break_duration", SUGGESTED_BREAK_DURATION)

        duration_mins = int(self._high_stress_duration / 60)

        alert = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": alert_type,
            "level": stress_level,
            "score": stress_score,
            "duration_minutes": duration_mins,
            "title": "⚠️ 压力提醒",
            "message": (
                f"您已持续处于高压力状态 {duration_mins} 分钟。\n"
                f"当前压力评分: {stress_score:.0f}/100\n\n"
                f"建议休息 {break_mins} 分钟。\n\n"
                f"💡 放松小贴士:\n{tip}"
            ),
            "tip": tip,
        }

        self._alert_history.append(alert)
        logger.info(f"触发压力预警: 持续{duration_mins}分钟, 评分{stress_score:.1f}")

        # 调用回调函数
        if self._alert_callback:
            try:
                self._alert_callback(alert)
            except Exception as e:
                logger.error(f"预警回调执行失败: {e}")

        return alert

    def _get_next_tip(self) -> str:
        """轮流返回放松建议"""
        tip = RELAXATION_TIPS[self._tip_index % len(RELAXATION_TIPS)]
        self._tip_index += 1
        return tip

    def get_status(self) -> dict:
        """获取预警系统当前状态"""
        return {
            "enabled": self._custom_rules.get("enabled", True),
            "high_stress_active": self._high_stress_start is not None,
            "high_stress_duration": round(self._high_stress_duration / 60, 1),  # 分钟
            "total_alerts": len(self._alert_history),
            "last_alert_time": datetime.fromtimestamp(self._last_alert_time).strftime(
                "%Y-%m-%d %H:%M:%S") if self._last_alert_time > 0 else "无",
        }

    def get_alert_history(self) -> list:
        """获取预警历史"""
        return self._alert_history.copy()

    def reset(self):
        """重置预警状态"""
        self._high_stress_start = None
        self._high_stress_duration = 0
        self._last_alert_time = 0
        self._alert_history.clear()
        self._tip_index = 0
        logger.info("预警管理器已重置")
