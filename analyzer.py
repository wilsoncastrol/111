"""
多模态交互压力数据分析系统 - 压力分析引擎
Stress analysis engine with multimodal feature fusion and 4-level classification.
Uses lightweight local algorithms — no external API calls required.
"""

import time
import collections
import numpy as np
from datetime import datetime
from typing import Optional

from config import (
    STRESS_THRESHOLDS,
    STRESS_SOURCES,
    ANALYSIS_WINDOW,
    get_stress_level,
    get_stress_name,
    logger,
)

# 尝试导入SnowNLP进行中文情感分析（可选）
try:
    from snownlp import SnowNLP

    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False
    logger.warning("snownlp 库未安装，文本情感分析功能不可用")


class StressAnalyzer:
    """
    压力分析引擎
    基于多模态特征融合的轻量级本地分析模型
    将压力分为4个等级：低压力(0)、正常(1)、中等压力(2)、高压力(3)
    """

    # 压力来源识别阈值（特征分数超过此值视为压力来源）
    STRESS_SOURCE_THRESHOLD = 60

    def __init__(self):
        # 历史特征缓冲（用于滑动窗口分析）
        self._history = collections.deque(maxlen=int(ANALYSIS_WINDOW / 5))  # 5秒采集一次

        # 基线特征（用于个性化校准）
        self._baseline = None
        self._baseline_samples = []
        self._baseline_ready = False

        # 权重配置（各模态在压力评估中的权重）
        self.weights = {
            "keyboard_rhythm": 0.20,
            "keyboard_speed": 0.15,
            "mouse_activity": 0.15,
            "scroll_intensity": 0.10,
            "window_switching": 0.15,
            "text_emotion": 0.10,
            "input_pauses": 0.10,
            "wearable": 0.05,  # 预留
        }

        logger.info("压力分析引擎已初始化")

    def analyze(self, snapshot: dict) -> dict:
        """
        执行一次压力分析
        输入: 数据采集快照
        输出: 压力评估结果
        """
        # 添加到历史缓冲
        self._history.append(snapshot)

        # 更新基线（前30个采样点用于建立基线）
        if not self._baseline_ready:
            self._update_baseline(snapshot)

        # 1. 提取各模态的压力特征分数（0-100）
        features = self._extract_features(snapshot)

        # 2. 多模态特征融合 — 加权求和
        stress_score = self._fuse_features(features)

        # 3. 确定压力等级
        stress_level = get_stress_level(stress_score)

        # 4. 识别压力来源
        sources = self._identify_sources(features)

        result = {
            "timestamp": snapshot.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "stress_score": round(stress_score, 1),
            "stress_level": stress_level,
            "stress_name": get_stress_name(stress_level),
            "sources": sources,
            "features": features,
            "baseline_ready": self._baseline_ready,
        }

        logger.debug(f"分析结果: {result['stress_name']}({stress_score:.1f}), 来源: {sources}")
        return result

    def _extract_features(self, snapshot: dict) -> dict:
        """从快照中提取各模态的压力特征分数（0-100）"""
        kb = snapshot.get("keyboard", {})
        ms = snapshot.get("mouse", {})
        win = snapshot.get("window", {})
        txt = snapshot.get("text", {})

        features = {}

        # --- 键盘节奏不规律性 ---
        # 标准差越大，节奏越不规律 → 压力越高
        std_interval = kb.get("std_interval", 0)
        regularity = kb.get("rhythm_regularity", 0.5)
        features["keyboard_rhythm"] = self._normalize(1 - regularity, 0, 1) * 100

        # --- 键盘速度（过快或过慢都可能是压力信号） ---
        key_rate = kb.get("key_rate", 0)
        # 使用U型映射：中间速率压力低，极高或极低压力高
        optimal_rate = self._get_baseline_value("key_rate", 3.0)
        deviation = abs(key_rate - optimal_rate) / max(optimal_rate, 0.1)
        features["keyboard_speed"] = min(deviation * 50, 100)

        # --- 鼠标活动强度 ---
        click_rate = ms.get("click_rate", 0)
        mouse_speed = ms.get("mouse_speed", 0)
        baseline_click = self._get_baseline_value("click_rate", 0.5)
        baseline_speed = self._get_baseline_value("mouse_speed", 300)

        click_score = min(click_rate / max(baseline_click * 2, 0.1) * 50, 100)
        speed_score = min(mouse_speed / max(baseline_speed * 2, 1) * 50, 100)
        features["mouse_activity"] = (click_score + speed_score) / 2

        # --- 滚动强度 ---
        scroll_count = ms.get("scroll_count", 0)
        features["scroll_intensity"] = min(scroll_count / 20 * 100, 100)

        # --- 窗口切换频率 ---
        switch_rate = win.get("switch_rate", 0)
        features["window_switching"] = min(switch_rate / 5 * 100, 100)

        # --- 文本情感（如可用） ---
        features["text_emotion"] = self._analyze_text_emotion(txt)

        # --- 输入停顿分析 ---
        pause_count = txt.get("pause_count", 0)
        avg_pause = txt.get("avg_pause_duration", 0)
        # 频繁长停顿可能表示犹豫/焦虑
        features["input_pauses"] = min(pause_count * avg_pause / 10 * 100, 100)

        # --- 可穿戴设备数据（预留，当前返回中性值） ---
        features["wearable"] = 50  # 中性值

        # 确保所有值在0-100之间
        for key in features:
            features[key] = round(max(0, min(100, features[key])), 1)

        return features

    def _fuse_features(self, features: dict) -> float:
        """多模态特征融合 — 加权求和"""
        score = 0.0
        total_weight = 0.0

        for key, weight in self.weights.items():
            if key in features:
                score += features[key] * weight
                total_weight += weight

        # 归一化
        if total_weight > 0:
            score = score / total_weight

        # 结合历史趋势进行平滑（指数加权移动平均）
        if len(self._history) > 1:
            score = self._smooth_score(score)

        return max(0, min(100, score))

    def _smooth_score(self, current_score: float, alpha: float = 0.3) -> float:
        """使用指数加权移动平均平滑压力评分"""
        # alpha越大，当前值的权重越高（响应更快）
        if hasattr(self, "_last_score"):
            smoothed = alpha * current_score + (1 - alpha) * self._last_score
        else:
            smoothed = current_score
        self._last_score = smoothed
        return smoothed

    def _identify_sources(self, features: dict) -> dict:
        """识别压力的潜在来源"""
        sources = {}
        threshold = self.STRESS_SOURCE_THRESHOLD

        # 任务过载：键盘速度高 + 鼠标活动高
        if features.get("keyboard_speed", 0) > threshold and features.get("mouse_activity", 0) > threshold:
            sources["task_overload"] = STRESS_SOURCES["task_overload"]

        # 情绪负面：文本情感分数高
        if features.get("text_emotion", 0) > threshold:
            sources["negative_emotion"] = STRESS_SOURCES["negative_emotion"]

        # 节奏过快：键盘节奏不规律 + 速度快
        if features.get("keyboard_rhythm", 0) > threshold and features.get("keyboard_speed", 0) > 50:
            sources["fast_pace"] = STRESS_SOURCES["fast_pace"]

        # 频繁切换
        if features.get("window_switching", 0) > threshold:
            sources["frequent_switching"] = STRESS_SOURCES["frequent_switching"]

        # 长时间工作（基于历史数据长度）
        if len(self._history) >= self._history.maxlen:
            sources["long_session"] = STRESS_SOURCES["long_session"]

        return sources

    def _analyze_text_emotion(self, text_features: dict) -> float:
        """分析文本情感（返回0-100的压力分数）"""
        # 当前简化实现：基于停顿模式推断
        # 未来可集成SnowNLP进行中文情感分析
        pause_count = text_features.get("pause_count", 0)
        avg_pause = text_features.get("avg_pause_duration", 0)

        # 频繁停顿可能暗示消极情绪
        emotion_score = min(pause_count * 10 + avg_pause * 5, 100)
        return emotion_score

    def _update_baseline(self, snapshot: dict):
        """更新个性化基线（采集前30个样本建立基线）"""
        self._baseline_samples.append(snapshot)

        if len(self._baseline_samples) >= 30:
            # 计算各特征的基线值
            self._baseline = {
                "key_rate": np.mean([s["keyboard"]["key_rate"] for s in self._baseline_samples]),
                "click_rate": np.mean([s["mouse"]["click_rate"] for s in self._baseline_samples]),
                "mouse_speed": np.mean([s["mouse"]["mouse_speed"] for s in self._baseline_samples]),
                "scroll_count": np.mean([s["mouse"]["scroll_count"] for s in self._baseline_samples]),
                "switch_rate": np.mean([s["window"]["switch_rate"] for s in self._baseline_samples]),
            }
            self._baseline_ready = True
            logger.info(f"个性化基线已建立: {self._baseline}")

    def _get_baseline_value(self, key: str, default: float) -> float:
        """获取基线值，未就绪时返回默认值"""
        if self._baseline and key in self._baseline:
            return self._baseline[key]
        return default

    @staticmethod
    def _normalize(value: float, min_val: float, max_val: float) -> float:
        """将值归一化到0-1范围"""
        if max_val == min_val:
            return 0.5
        return max(0, min(1, (value - min_val) / (max_val - min_val)))

    def get_trend(self, records: list) -> dict:
        """
        分析压力趋势
        输入: 压力记录列表
        输出: 趋势统计信息
        """
        if not records:
            return {"trend": "无数据", "avg_score": 0, "max_score": 0, "min_score": 0}

        scores = [r["stress_score"] if isinstance(r, dict) else r for r in records]
        avg_score = np.mean(scores)

        # 简单趋势判断：比较前半段和后半段的平均值
        mid = len(scores) // 2
        if mid > 0:
            first_half = np.mean(scores[:mid])
            second_half = np.mean(scores[mid:])
            diff = second_half - first_half

            if diff > 5:
                trend = "上升 ↑"
            elif diff < -5:
                trend = "下降 ↓"
            else:
                trend = "平稳 →"
        else:
            trend = "数据不足"

        return {
            "trend": trend,
            "avg_score": round(float(avg_score), 1),
            "max_score": round(float(max(scores)), 1),
            "min_score": round(float(min(scores)), 1),
        }

    def get_baseline_status(self) -> dict:
        """获取基线建立状态（公共接口）"""
        return {
            "ready": self._baseline_ready,
            "sample_count": len(self._baseline_samples),
            "target_count": 30,
        }

    def reset(self):
        """重置分析器状态"""
        self._history.clear()
        self._baseline = None
        self._baseline_samples = []
        self._baseline_ready = False
        if hasattr(self, "_last_score"):
            del self._last_score
        logger.info("分析引擎已重置")
