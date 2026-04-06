"""
多模态交互压力数据分析系统 - 后台数据采集模块
Background data collection for keyboard, mouse, and window activity.
All data is collected locally and never transmitted externally.
"""

import threading
import time
import collections
from datetime import datetime
from typing import Optional, Callable

import numpy as np

from config import (
    COLLECTION_INTERVAL,
    KEYBOARD_BUFFER_SIZE,
    logger,
)

# 尝试导入pynput（键盘/鼠标监听）
try:
    from pynput import keyboard, mouse

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput 库未安装，将使用模拟数据模式")


class DataCollector:
    """
    后台数据采集器
    采集键盘输入节奏、鼠标活动、窗口切换等行为特征
    所有数据仅在本地处理，不外传。
    """

    def __init__(self):
        self.is_running = False
        self._lock = threading.Lock()

        # 键盘数据缓冲
        self._key_timestamps = collections.deque(maxlen=KEYBOARD_BUFFER_SIZE)
        self._key_intervals = collections.deque(maxlen=KEYBOARD_BUFFER_SIZE)
        self._key_count = 0
        self._last_key_time: Optional[float] = None

        # 鼠标数据缓冲
        self._click_timestamps = collections.deque(maxlen=200)
        self._mouse_positions = collections.deque(maxlen=200)
        self._scroll_count = 0
        self._click_count = 0
        self._mouse_distance = 0.0
        self._last_mouse_pos = None

        # 窗口切换计数（简化实现）
        self._window_switch_count = 0

        # 文本缓冲（用于情感分析）
        self._text_buffer = []
        self._input_pauses = collections.deque(maxlen=50)

        # 监听器引用
        self._keyboard_listener = None
        self._mouse_listener = None

        # 采集线程
        self._collection_thread: Optional[threading.Thread] = None
        self._snapshot_callback: Optional[Callable] = None

        # 上次快照时间
        self._last_snapshot_time = time.time()

        logger.info("数据采集器已初始化")

    def start(self, snapshot_callback: Callable = None):
        """启动数据采集"""
        if self.is_running:
            logger.warning("采集器已在运行中")
            return

        self.is_running = True
        self._snapshot_callback = snapshot_callback
        self._last_snapshot_time = time.time()

        # 启动键盘监听
        if PYNPUT_AVAILABLE:
            self._start_keyboard_listener()
            self._start_mouse_listener()
        else:
            logger.info("使用模拟数据模式（pynput不可用）")

        # 启动定时采集线程
        self._collection_thread = threading.Thread(
            target=self._collection_loop, daemon=True, name="DataCollector"
        )
        self._collection_thread.start()

        logger.info("数据采集已启动")

    def stop(self):
        """停止数据采集"""
        self.is_running = False

        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

        logger.info("数据采集已停止")

    def _start_keyboard_listener(self):
        """启动键盘事件监听"""
        def on_press(key):
            if not self.is_running:
                return False
            current_time = time.time()
            with self._lock:
                self._key_count += 1
                self._key_timestamps.append(current_time)

                # 计算按键间隔
                if self._last_key_time is not None:
                    interval = current_time - self._last_key_time
                    self._key_intervals.append(interval)

                    # 检测输入停顿（超过2秒视为停顿）
                    if interval > 2.0:
                        self._input_pauses.append(interval)

                self._last_key_time = current_time

        self._keyboard_listener = keyboard.Listener(on_press=on_press)
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()
        logger.debug("键盘监听已启动")

    def _start_mouse_listener(self):
        """启动鼠标事件监听"""
        def on_move(x, y):
            if not self.is_running:
                return
            with self._lock:
                if self._last_mouse_pos:
                    dx = x - self._last_mouse_pos[0]
                    dy = y - self._last_mouse_pos[1]
                    self._mouse_distance += (dx ** 2 + dy ** 2) ** 0.5
                self._last_mouse_pos = (x, y)
                self._mouse_positions.append((x, y, time.time()))

        def on_click(x, y, button, pressed):
            if not self.is_running:
                return
            if pressed:
                with self._lock:
                    self._click_count += 1
                    self._click_timestamps.append(time.time())

        def on_scroll(x, y, dx, dy):
            if not self.is_running:
                return
            with self._lock:
                self._scroll_count += 1

        self._mouse_listener = mouse.Listener(
            on_move=on_move, on_click=on_click, on_scroll=on_scroll
        )
        self._mouse_listener.daemon = True
        self._mouse_listener.start()
        logger.debug("鼠标监听已启动")

    def _collection_loop(self):
        """定时采集循环 - 每隔COLLECTION_INTERVAL秒生成一个数据快照"""
        while self.is_running:
            time.sleep(COLLECTION_INTERVAL)
            if not self.is_running:
                break

            snapshot = self.take_snapshot()
            if self._snapshot_callback:
                try:
                    self._snapshot_callback(snapshot)
                except Exception as e:
                    logger.error(f"快照回调执行失败: {e}")

    def take_snapshot(self) -> dict:
        """
        生成当前时间窗口的数据快照
        返回包含各类行为特征的字典
        """
        current_time = time.time()
        elapsed = current_time - self._last_snapshot_time

        with self._lock:
            snapshot = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "elapsed_seconds": round(elapsed, 2),
                "keyboard": self._get_keyboard_features(elapsed),
                "mouse": self._get_mouse_features(elapsed),
                "window": self._get_window_features(elapsed),
                "text": self._get_text_features(),
            }

            # 重置计数器
            self._reset_counters()
            self._last_snapshot_time = current_time

        logger.debug(f"数据快照: keys={snapshot['keyboard']['key_rate']:.1f}/s, "
                     f"clicks={snapshot['mouse']['click_rate']:.1f}/s")
        return snapshot

    def _get_keyboard_features(self, elapsed: float) -> dict:
        """提取键盘行为特征"""
        key_rate = self._key_count / max(elapsed, 0.1)

        # 按键间隔统计
        intervals = list(self._key_intervals)
        if intervals:
            avg_interval = np.mean(intervals)
            std_interval = np.std(intervals)
            rhythm_regularity = 1.0 / (1.0 + std_interval) if std_interval > 0 else 1.0
        else:
            avg_interval = 0.0
            std_interval = 0.0
            rhythm_regularity = 0.0

        return {
            "key_count": self._key_count,
            "key_rate": round(key_rate, 2),  # 按键/秒
            "avg_interval": round(avg_interval, 4),
            "std_interval": round(std_interval, 4),
            "rhythm_regularity": round(rhythm_regularity, 4),
        }

    def _get_mouse_features(self, elapsed: float) -> dict:
        """提取鼠标行为特征"""
        click_rate = self._click_count / max(elapsed, 0.1)
        mouse_speed = self._mouse_distance / max(elapsed, 0.1)

        return {
            "click_count": self._click_count,
            "click_rate": round(click_rate, 2),  # 点击/秒
            "scroll_count": self._scroll_count,
            "mouse_distance": round(self._mouse_distance, 1),  # 像素
            "mouse_speed": round(mouse_speed, 1),  # 像素/秒
        }

    def _get_window_features(self, elapsed: float) -> dict:
        """提取窗口切换特征"""
        switch_rate = self._window_switch_count / max(elapsed / 60, 0.01)  # 次/分钟
        return {
            "switch_count": self._window_switch_count,
            "switch_rate": round(switch_rate, 2),
        }

    def _get_text_features(self) -> dict:
        """提取文本输入特征"""
        pauses = list(self._input_pauses)
        if pauses:
            avg_pause = np.mean(pauses)
            pause_count = len(pauses)
        else:
            avg_pause = 0.0
            pause_count = 0

        return {
            "pause_count": pause_count,
            "avg_pause_duration": round(avg_pause, 2),
            "text_buffer_size": len(self._text_buffer),
        }

    def _reset_counters(self):
        """重置周期性计数器（保留缓冲区用于趋势分析）"""
        self._key_count = 0
        self._click_count = 0
        self._scroll_count = 0
        self._mouse_distance = 0.0
        self._window_switch_count = 0
        self._text_buffer.clear()
        self._input_pauses.clear()

    def simulate_data(self) -> dict:
        """
        模拟数据（用于测试/演示，当pynput不可用时）
        生成接近真实分布的模拟行为数据
        """
        import random
        import numpy as np

        elapsed = COLLECTION_INTERVAL

        # 模拟不同工作状态
        state = random.choice(["relaxed", "normal", "busy", "stressed"])

        if state == "relaxed":
            key_rate = random.uniform(0.5, 2.0)
            click_rate = random.uniform(0.1, 0.5)
            scroll_count = random.randint(0, 3)
            mouse_speed = random.uniform(50, 200)
            pause_count = random.randint(2, 5)
        elif state == "normal":
            key_rate = random.uniform(2.0, 4.0)
            click_rate = random.uniform(0.3, 1.0)
            scroll_count = random.randint(1, 8)
            mouse_speed = random.uniform(200, 500)
            pause_count = random.randint(1, 3)
        elif state == "busy":
            key_rate = random.uniform(4.0, 7.0)
            click_rate = random.uniform(0.8, 2.0)
            scroll_count = random.randint(5, 15)
            mouse_speed = random.uniform(400, 800)
            pause_count = random.randint(0, 2)
        else:  # stressed
            key_rate = random.uniform(5.0, 10.0)
            click_rate = random.uniform(1.5, 4.0)
            scroll_count = random.randint(8, 25)
            mouse_speed = random.uniform(600, 1200)
            pause_count = random.randint(0, 1)

        key_count = int(key_rate * elapsed)
        # 模拟按键间隔
        if key_count > 1:
            base_interval = 1.0 / key_rate
            intervals = np.random.normal(base_interval, base_interval * 0.3, key_count)
            intervals = np.clip(intervals, 0.02, 5.0)
            avg_interval = float(np.mean(intervals))
            std_interval = float(np.std(intervals))
        else:
            avg_interval = 0.0
            std_interval = 0.0

        rhythm_regularity = 1.0 / (1.0 + std_interval)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": elapsed,
            "keyboard": {
                "key_count": key_count,
                "key_rate": round(key_rate, 2),
                "avg_interval": round(avg_interval, 4),
                "std_interval": round(std_interval, 4),
                "rhythm_regularity": round(rhythm_regularity, 4),
            },
            "mouse": {
                "click_count": int(click_rate * elapsed),
                "click_rate": round(click_rate, 2),
                "scroll_count": scroll_count,
                "mouse_distance": round(mouse_speed * elapsed, 1),
                "mouse_speed": round(mouse_speed, 1),
            },
            "window": {
                "switch_count": random.randint(0, 5 if state in ["busy", "stressed"] else 2),
                "switch_rate": round(random.uniform(0, 3.0), 2),
            },
            "text": {
                "pause_count": pause_count,
                "avg_pause_duration": round(random.uniform(1.0, 5.0), 2),
                "text_buffer_size": 0,
            },
        }

    @property
    def status(self) -> str:
        """获取采集器状态"""
        return "运行中" if self.is_running else "已停止"
