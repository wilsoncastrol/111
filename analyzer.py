"""
analyzer.py - 压力分析引擎
多模态交互压力数据分析系统

功能：
- 多模态特征归一化与融合
- 基于加权规则的压力评分（0-100）
- 压力等级分类（4级）
- 压力来源识别
- 本地文本情绪分析
- 完全离线运行，无需外部API
"""

import statistics
from datetime import datetime, timedelta

from config import (
    debug_print, FEATURE_WEIGHTS, STRESS_THRESHOLDS,
    STRESS_LEVELS, STRESS_SOURCES,
    NEGATIVE_WORDS, POSITIVE_WORDS,
    WEARABLE_ENABLED, WEARABLE_HEART_RATE_WEIGHT, WEARABLE_GSR_WEIGHT,
)


class StressAnalyzer:
    """
    压力分析引擎

    工作流程：
    1. 接收采集器的原始特征数据
    2. 对每个特征进行归一化（映射到 0-1）
    3. 进行文本情绪分析
    4. 按权重加权融合得到综合压力分数（0-100）
    5. 映射到压力等级（低/正常/中/高）
    6. 识别压力来源
    """

    def __init__(self):
        # 特征基线（用于归一化，会随使用自适应更新）
        self._baselines = {
            "keyboard_speed":     {"min": 0, "max": 200, "mean": 80},
            "keyboard_rhythm_cv": {"min": 0, "max": 1.0, "mean": 0.3},
            "mouse_click_freq":   {"min": 0, "max": 80,  "mean": 20},
            "mouse_move_speed":   {"min": 0, "max": 600, "mean": 150},
            "mouse_scroll_freq":  {"min": 0, "max": 40,  "mean": 10},
            "window_switch_freq": {"min": 0, "max": 15,  "mean": 3},
            "typing_pause":       {"min": 0, "max": 0.5, "mean": 0.1},
            "work_duration":      {"min": 0, "max": 180, "mean": 45},
        }

        # 分析结果历史
        self._results_history = []

        debug_print("StressAnalyzer 初始化完成")

    # ============================================================
    # 核心分析
    # ============================================================

    def analyze(self, raw_data):
        """
        分析一组原始采集数据，返回压力评估结果

        参数:
            raw_data: dict, 来自 DataCollector.collect_period_data() 的数据

        返回:
            dict: {
                "timestamp": datetime,
                "stress_score": float (0-100),
                "stress_level": int (0-3),
                "stress_level_name": str,
                "stress_sources": list[str],
                "feature_scores": dict,
                "text_sentiment": float,
                "raw_data": dict,
            }
        """
        if not raw_data:
            return self._empty_result()

        # 1. 特征归一化
        feature_scores = self._normalize_features(raw_data)

        # 2. 文本情绪分析
        text_sentiment = self._analyze_text_sentiment(raw_data.get("text_content", ""))
        feature_scores["text_sentiment"] = text_sentiment

        # 3. 可穿戴设备数据（如果有的话）
        if WEARABLE_ENABLED and raw_data.get("heart_rate") is not None:
            hr_score = self._normalize_heart_rate(raw_data["heart_rate"])
            feature_scores["heart_rate"] = hr_score

        # 4. 加权融合
        stress_score = self._weighted_fusion(feature_scores)

        # 5. 映射到等级
        stress_level = self._score_to_level(stress_score)

        # 6. 识别压力来源
        stress_sources = self._identify_sources(feature_scores, raw_data)

        result = {
            "timestamp": raw_data.get("timestamp", datetime.now()),
            "stress_score": round(stress_score, 1),
            "stress_level": stress_level,
            "stress_level_name": STRESS_LEVELS[stress_level]["name"],
            "stress_level_color": STRESS_LEVELS[stress_level]["color"],
            "stress_level_emoji": STRESS_LEVELS[stress_level]["emoji"],
            "stress_sources": stress_sources,
            "feature_scores": feature_scores,
            "text_sentiment": round(text_sentiment, 3),
            "raw_data": raw_data,
        }

        self._results_history.append(result)

        debug_print(f"分析结果: score={stress_score:.1f}, "
                   f"level={STRESS_LEVELS[stress_level]['name']}, "
                   f"sources={[STRESS_SOURCES.get(s, s) for s in stress_sources]}")

        return result

    # ============================================================
    # 特征归一化
    # ============================================================

    def _normalize_features(self, raw_data):
        """将原始特征值归一化到 0-1 范围"""
        scores = {}

        # 键盘输入速度 —— 越快压力越大（有上限）
        kb_speed = raw_data.get("keyboard_speed", 0)
        scores["keyboard_speed"] = self._normalize(
            kb_speed,
            self._baselines["keyboard_speed"]["min"],
            self._baselines["keyboard_speed"]["max"]
        )

        # 键盘节奏变异系数 —— 越不规律压力越大
        kb_rhythm = raw_data.get("keyboard_rhythm_cv", 0)
        scores["keyboard_rhythm"] = self._normalize(
            kb_rhythm,
            self._baselines["keyboard_rhythm_cv"]["min"],
            self._baselines["keyboard_rhythm_cv"]["max"]
        )

        # 鼠标点击频率 —— 越频繁压力越大
        click_freq = raw_data.get("mouse_click_freq", 0)
        scores["mouse_click_freq"] = self._normalize(
            click_freq,
            self._baselines["mouse_click_freq"]["min"],
            self._baselines["mouse_click_freq"]["max"]
        )

        # 鼠标移动速度 —— 越快压力越大
        move_speed = raw_data.get("mouse_move_speed", 0)
        scores["mouse_move_speed"] = self._normalize(
            move_speed,
            self._baselines["mouse_move_speed"]["min"],
            self._baselines["mouse_move_speed"]["max"]
        )

        # 滚动频率
        scroll_freq = raw_data.get("mouse_scroll_freq", 0)
        scores["mouse_scroll_freq"] = self._normalize(
            scroll_freq,
            self._baselines["mouse_scroll_freq"]["min"],
            self._baselines["mouse_scroll_freq"]["max"]
        )

        # 窗口切换频率 —— 越频繁表示任务切换越多
        win_freq = raw_data.get("window_switch_freq", 0)
        scores["window_switch_freq"] = self._normalize(
            win_freq,
            self._baselines["window_switch_freq"]["min"],
            self._baselines["window_switch_freq"]["max"]
        )

        # 输入停顿比例 —— 停顿多可能是在思考，也可能是疲劳
        pause_ratio = raw_data.get("typing_pause_ratio", 0)
        scores["typing_pause"] = self._normalize(
            pause_ratio,
            self._baselines["typing_pause"]["min"],
            self._baselines["typing_pause"]["max"]
        )

        # 连续工作时长 —— 越长压力越大
        work_dur = raw_data.get("work_duration", 0)
        scores["work_duration"] = self._normalize(
            work_dur,
            self._baselines["work_duration"]["min"],
            self._baselines["work_duration"]["max"]
        )

        return scores

    @staticmethod
    def _normalize(value, min_val, max_val):
        """线性归一化到 0-1"""
        if max_val <= min_val:
            return 0.0
        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    # ============================================================
    # 文本情绪分析（本地）
    # ============================================================

    def _analyze_text_sentiment(self, text):
        """
        基于本地关键词词典的情绪分析

        返回值范围：0.0（积极）到 1.0（消极）
        0.5 表示中性

        注意：仅在本地运行，不调用任何外部API
        """
        if not text or len(text.strip()) < 3:
            return 0.5  # 无文本时返回中性

        text_lower = text.lower()
        neg_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
        pos_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)

        total = neg_count + pos_count
        if total == 0:
            return 0.5

        # 负面词占比越高，分数越高（表示压力越大）
        sentiment = neg_count / total

        debug_print(f"文本情绪分析: neg={neg_count}, pos={pos_count}, sentiment={sentiment:.3f}")
        return sentiment

    # ============================================================
    # 可穿戴设备数据处理（预留）
    # ============================================================

    @staticmethod
    def _normalize_heart_rate(hr):
        """
        归一化心率值

        正常静息心率：60-100 BPM
        超过 100 表示紧张，越高压力越大
        """
        if hr < 60:
            return 0.0
        elif hr > 120:
            return 1.0
        else:
            return (hr - 60) / 60.0

    # ============================================================
    # 加权融合
    # ============================================================

    def _weighted_fusion(self, feature_scores):
        """
        按权重融合各特征得分，得到综合压力分数（0-100）
        """
        total_score = 0.0
        total_weight = 0.0

        for feature, weight in FEATURE_WEIGHTS.items():
            if feature in feature_scores:
                total_score += feature_scores[feature] * weight
                total_weight += weight

        # 归一化到 0-100
        if total_weight > 0:
            stress_score = (total_score / total_weight) * 100
        else:
            stress_score = 0.0

        return max(0.0, min(100.0, stress_score))

    # ============================================================
    # 等级映射
    # ============================================================

    @staticmethod
    def _score_to_level(score):
        """将压力分数映射到等级"""
        if score < STRESS_THRESHOLDS["low"][1]:
            return 0  # 低压力
        elif score < STRESS_THRESHOLDS["normal"][1]:
            return 1  # 正常
        elif score < STRESS_THRESHOLDS["medium"][1]:
            return 2  # 中等压力
        else:
            return 3  # 高压力

    # ============================================================
    # 压力来源识别
    # ============================================================

    def _identify_sources(self, feature_scores, raw_data):
        """识别压力的潜在来源"""
        sources = []

        # 任务过载：键盘速度高 + 鼠标频繁 + 窗口切换多
        if (feature_scores.get("keyboard_speed", 0) > 0.7 and
            feature_scores.get("mouse_click_freq", 0) > 0.6):
            sources.append("task_overload")

        # 情绪负面：文本情绪消极
        if feature_scores.get("text_sentiment", 0.5) > 0.65:
            sources.append("negative_emotion")

        # 节奏过快：输入速度异常高
        if (feature_scores.get("keyboard_speed", 0) > 0.8 or
            feature_scores.get("mouse_move_speed", 0) > 0.8):
            sources.append("fast_pace")

        # 持续工作时间过长
        if feature_scores.get("work_duration", 0) > 0.7:
            sources.append("long_duration")

        # 频繁切换任务
        if feature_scores.get("window_switch_freq", 0) > 0.7:
            sources.append("frequent_switch")

        return sources

    # ============================================================
    # 趋势分析
    # ============================================================

    def get_trend(self, period_minutes=60):
        """
        获取指定时间段的压力趋势

        返回:
            dict: {
                "average": float,
                "min": float,
                "max": float,
                "trend": str ("上升"/"下降"/"平稳"),
                "scores": list[float],
                "timestamps": list[datetime],
            }
        """
        cutoff = datetime.now() - timedelta(minutes=period_minutes)
        recent = [r for r in self._results_history
                  if r["timestamp"] >= cutoff]

        if not recent:
            return {
                "average": 0, "min": 0, "max": 0,
                "trend": "无数据", "scores": [], "timestamps": [],
            }

        scores = [r["stress_score"] for r in recent]
        timestamps = [r["timestamp"] for r in recent]

        avg = statistics.mean(scores)
        trend = "平稳"

        if len(scores) >= 3:
            first_half = statistics.mean(scores[:len(scores)//2])
            second_half = statistics.mean(scores[len(scores)//2:])
            diff = second_half - first_half
            if diff > 5:
                trend = "上升"
            elif diff < -5:
                trend = "下降"

        return {
            "average": round(avg, 1),
            "min": round(min(scores), 1),
            "max": round(max(scores), 1),
            "trend": trend,
            "scores": scores,
            "timestamps": timestamps,
        }

    def get_results_history(self):
        """获取所有分析结果历史"""
        return list(self._results_history)

    def get_latest_result(self):
        """获取最近一次分析结果"""
        if self._results_history:
            return self._results_history[-1]
        return self._empty_result()

    @staticmethod
    def _empty_result():
        """返回空结果"""
        return {
            "timestamp": datetime.now(),
            "stress_score": 0,
            "stress_level": 0,
            "stress_level_name": "低压力",
            "stress_level_color": "#4CAF50",
            "stress_level_emoji": "😊",
            "stress_sources": [],
            "feature_scores": {},
            "text_sentiment": 0.5,
            "raw_data": {},
        }

    # ============================================================
    # 各模态贡献占比（用于可视化）
    # ============================================================

    def get_modality_contributions(self, result=None):
        """
        计算各模态数据对压力评分的贡献占比

        返回 dict: {模态名称: 贡献百分比}
        """
        if result is None:
            result = self.get_latest_result()

        feature_scores = result.get("feature_scores", {})
        if not feature_scores:
            return {}

        contributions = {}
        total = 0

        modality_map = {
            "键盘行为": ["keyboard_speed", "keyboard_rhythm"],
            "鼠标行为": ["mouse_click_freq", "mouse_move_speed", "mouse_scroll_freq"],
            "窗口切换": ["window_switch_freq"],
            "文本情绪": ["text_sentiment"],
            "输入节奏": ["typing_pause"],
            "工作时长": ["work_duration"],
        }

        for modality, features in modality_map.items():
            score = 0
            weight = 0
            for f in features:
                if f in feature_scores and f in FEATURE_WEIGHTS:
                    score += feature_scores[f] * FEATURE_WEIGHTS[f]
                    weight += FEATURE_WEIGHTS[f]
            contributions[modality] = score
            total += score

        # 转换为百分比
        if total > 0:
            for k in contributions:
                contributions[k] = round(contributions[k] / total * 100, 1)

        return contributions
