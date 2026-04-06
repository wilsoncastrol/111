"""
collector.py - 数据采集模块
多模态交互压力数据分析系统

功能：
- 后台静默采集键盘输入节奏
- 采集鼠标点击/移动/滚动频率
- 检测窗口切换频率
- 采集文本输入（仅本地分析，不外传）
- 预留可穿戴设备数据接口
- 支持用户手动启停

所有数据仅在本地处理，绝不上传任何云端。
"""

import time
import threading
import collections
import statistics
from datetime import datetime

from config import (
    debug_print, COLLECTION_INTERVAL, KEYBOARD_ENABLED,
    MOUSE_ENABLED, WINDOW_CHECK_INTERVAL, TEXT_ANALYSIS_ENABLED,
    WEARABLE_ENABLED,
)

# 尝试导入 pynput（键盘鼠标监听）
try:
    from pynput import keyboard, mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    debug_print("警告: pynput 未安装，将使用模拟数据模式")

# 尝试导入 psutil（窗口检测）
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    debug_print("警告: psutil 未安装，窗口切换检测不可用")


class DataCollector:
    """
    多模态数据采集器

    采集维度：
    1. 键盘：按键次数、按键间隔时间序列、输入文本片段
    2. 鼠标：点击次数、移动距离、移动速度、滚动次数
    3. 窗口：活动窗口名称变化次数
    4. 文本：本地输入的文本片段（用于情绪分析）
    5. 可穿戴：预留心率、皮电接口
    """

    def __init__(self):
        # 采集状态
        self._running = False
        self._lock = threading.Lock()

        # ----- 键盘数据 -----
        self._key_count = 0                   # 当前周期按键总数
        self._key_timestamps = []             # 按键时间戳（用于计算节奏）
        self._text_buffer = []                # 输入的文字片段（仅用于本地情绪分析）

        # ----- 鼠标数据 -----
        self._click_count = 0                 # 点击次数
        self._move_distance = 0.0             # 鼠标移动距离（像素）
        self._last_mouse_pos = None           # 上次鼠标位置
        self._scroll_count = 0                # 滚动次数

        # ----- 窗口数据 -----
        self._window_switches = 0             # 窗口切换次数
        self._last_window = None              # 上次活动窗口名称
        self._window_thread = None

        # ----- 可穿戴设备数据（预留） -----
        self._heart_rate = None               # 心率 BPM
        self._gsr_value = None                # 皮电值

        # ----- 连续工作时长 -----
        self._work_start_time = None          # 本次连续工作开始时间
        self._idle_threshold = 120            # 超过120秒无操作视为休息

        # ----- pynput 监听器 -----
        self._keyboard_listener = None
        self._mouse_listener = None

        # ----- 历史数据（用于平滑） -----
        self._history = collections.deque(maxlen=60)  # 保留最近60个周期

        debug_print("DataCollector 初始化完成")

    # ============================================================
    # 启停控制
    # ============================================================

    def start(self):
        """启动数据采集"""
        if self._running:
            debug_print("采集器已在运行中")
            return

        self._running = True
        self._work_start_time = datetime.now()
        self._reset_period_data()

        # 启动键盘监听
        if KEYBOARD_ENABLED and PYNPUT_AVAILABLE:
            try:
                self._keyboard_listener = keyboard.Listener(
                    on_press=self._on_key_press,
                    on_release=self._on_key_release
                )
                self._keyboard_listener.daemon = True
                self._keyboard_listener.start()
                debug_print("键盘监听已启动")
            except Exception as e:
                debug_print(f"键盘监听启动失败: {e}")

        # 启动鼠标监听
        if MOUSE_ENABLED and PYNPUT_AVAILABLE:
            try:
                self._mouse_listener = mouse.Listener(
                    on_click=self._on_mouse_click,
                    on_move=self._on_mouse_move,
                    on_scroll=self._on_mouse_scroll
                )
                self._mouse_listener.daemon = True
                self._mouse_listener.start()
                debug_print("鼠标监听已启动")
            except Exception as e:
                debug_print(f"鼠标监听启动失败: {e}")

        # 启动窗口切换检测线程
        if PSUTIL_AVAILABLE:
            self._window_thread = threading.Thread(target=self._window_monitor, daemon=True)
            self._window_thread.start()
            debug_print("窗口监控线程已启动")

        debug_print("数据采集已启动")

    def stop(self):
        """停止数据采集"""
        self._running = False

        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

        debug_print("数据采集已停止")

    @property
    def is_running(self):
        return self._running

    # ============================================================
    # 键盘事件回调
    # ============================================================

    def _on_key_press(self, key):
        """键盘按下事件 —— 仅记录时间戳和统计信息，不记录具体按键内容"""
        if not self._running:
            return

        with self._lock:
            self._key_count += 1
            self._key_timestamps.append(time.time())

            # 只对可打印字符记录到文本缓冲（用于本地情绪分析）
            if TEXT_ANALYSIS_ENABLED:
                try:
                    if hasattr(key, 'char') and key.char:
                        self._text_buffer.append(key.char)
                    elif key == keyboard.Key.space:
                        self._text_buffer.append(' ')
                    elif key == keyboard.Key.enter:
                        self._text_buffer.append('\n')
                except AttributeError:
                    pass

    def _on_key_release(self, key):
        """键盘释放事件（当前未使用，预留扩展）"""
        pass

    # ============================================================
    # 鼠标事件回调
    # ============================================================

    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击事件"""
        if not self._running or not pressed:
            return

        with self._lock:
            self._click_count += 1

    def _on_mouse_move(self, x, y):
        """鼠标移动事件"""
        if not self._running:
            return

        with self._lock:
            if self._last_mouse_pos:
                dx = x - self._last_mouse_pos[0]
                dy = y - self._last_mouse_pos[1]
                self._move_distance += (dx**2 + dy**2) ** 0.5
            self._last_mouse_pos = (x, y)

    def _on_mouse_scroll(self, x, y, dx, dy):
        """鼠标滚动事件"""
        if not self._running:
            return

        with self._lock:
            self._scroll_count += abs(dy)

    # ============================================================
    # 窗口监控
    # ============================================================

    def _window_monitor(self):
        """后台线程：定期检查活动窗口变化"""
        while self._running:
            try:
                current_window = self._get_active_window()
                if current_window and current_window != self._last_window:
                    with self._lock:
                        if self._last_window is not None:
                            self._window_switches += 1
                        self._last_window = current_window
            except Exception as e:
                debug_print(f"窗口检测异常: {e}")

            time.sleep(WINDOW_CHECK_INTERVAL)

    def _get_active_window(self):
        """获取当前活动窗口名称（跨平台）"""
        try:
            import subprocess
            if __import__("platform").system() == "Windows":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
            elif __import__("platform").system() == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
            else:
                # Linux: 使用 xdotool
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
        except Exception:
            return None

    # ============================================================
    # 可穿戴设备接口（预留）
    # ============================================================

    def update_wearable_data(self, heart_rate=None, gsr=None):
        """
        更新可穿戴设备数据

        预留接口：当用户连接可穿戴设备时，调用此方法传入生理数据。
        参数：
            heart_rate: 心率（BPM），正常范围 60-100
            gsr: 皮电值（微西门子），越高表示越紧张
        """
        with self._lock:
            if heart_rate is not None:
                self._heart_rate = heart_rate
            if gsr is not None:
                self._gsr_value = gsr
        debug_print(f"可穿戴数据更新: HR={heart_rate}, GSR={gsr}")

    # ============================================================
    # 数据收集与汇总
    # ============================================================

    def collect_period_data(self):
        """
        收集当前周期的特征数据并重置计数器

        返回字典包含所有采集到的原始特征数据
        """
        with self._lock:
            now = datetime.now()

            # 键盘特征
            key_intervals = []
            if len(self._key_timestamps) > 1:
                for i in range(1, len(self._key_timestamps)):
                    interval = self._key_timestamps[i] - self._key_timestamps[i-1]
                    if interval < 5.0:  # 过滤超过5秒的间隔（可能是暂停）
                        key_intervals.append(interval)

            keyboard_speed = self._key_count / (COLLECTION_INTERVAL / 60.0)  # 按键/分钟
            keyboard_rhythm_cv = 0.0
            typing_pause_ratio = 0.0

            if key_intervals:
                mean_interval = statistics.mean(key_intervals)
                if mean_interval > 0:
                    std_interval = statistics.stdev(key_intervals) if len(key_intervals) > 1 else 0
                    keyboard_rhythm_cv = std_interval / mean_interval  # 变异系数
                # 停顿比例（间隔 > 2秒的占比）
                pauses = [i for i in key_intervals if i > 2.0]
                typing_pause_ratio = len(pauses) / len(key_intervals) if key_intervals else 0

            # 鼠标特征
            mouse_click_freq = self._click_count / (COLLECTION_INTERVAL / 60.0)  # 点击/分钟
            mouse_move_speed = self._move_distance / COLLECTION_INTERVAL  # 像素/秒
            mouse_scroll_freq = self._scroll_count / (COLLECTION_INTERVAL / 60.0)  # 滚动/分钟

            # 窗口特征
            window_switch_freq = self._window_switches / (COLLECTION_INTERVAL / 60.0)  # 切换/分钟

            # 文本情绪
            text_content = ''.join(self._text_buffer)

            # 连续工作时长（分钟）
            work_duration = 0
            if self._work_start_time:
                work_duration = (now - self._work_start_time).total_seconds() / 60.0

            # 可穿戴数据
            heart_rate = self._heart_rate
            gsr_value = self._gsr_value

            # 组装数据
            data = {
                "timestamp": now,
                "keyboard_speed": round(keyboard_speed, 2),
                "keyboard_rhythm_cv": round(keyboard_rhythm_cv, 4),
                "typing_pause_ratio": round(typing_pause_ratio, 4),
                "mouse_click_freq": round(mouse_click_freq, 2),
                "mouse_move_speed": round(mouse_move_speed, 2),
                "mouse_scroll_freq": round(mouse_scroll_freq, 2),
                "window_switch_freq": round(window_switch_freq, 2),
                "text_content": text_content,
                "work_duration": round(work_duration, 1),
                "key_count": self._key_count,
                "click_count": self._click_count,
                "scroll_count": self._scroll_count,
                "window_switches": self._window_switches,
                # 可穿戴设备数据（预留）
                "heart_rate": heart_rate,
                "gsr_value": gsr_value,
            }

            # 保存到历史
            self._history.append(data)

            # 重置当前周期计数器
            self._reset_period_data()

            debug_print(f"周期数据采集完成: keys={data['key_count']}, "
                       f"clicks={data['click_count']}, "
                       f"scrolls={data['scroll_count']}, "
                       f"win_switch={data['window_switches']}, "
                       f"kb_speed={data['keyboard_speed']}")

            return data

    def _reset_period_data(self):
        """重置当前采集周期的计数器"""
        self._key_count = 0
        self._key_timestamps = []
        self._text_buffer = []
        self._click_count = 0
        self._move_distance = 0.0
        self._scroll_count = 0
        self._window_switches = 0

    def get_history(self):
        """获取历史采集数据"""
        return list(self._history)

    # ============================================================
    # 模拟数据（无 pynput 环境下使用）
    # ============================================================

    def generate_simulated_data(self):
        """
        生成模拟数据用于演示和测试

        在没有 pynput 可用的环境下（如服务器、CI），使用此方法
        """
        import random
        now = datetime.now()
        hour = now.hour

        # 根据时间模拟不同的工作状态
        if 9 <= hour < 12:    # 上午：正常工作
            base_activity = 0.6
        elif 12 <= hour < 14:  # 午休：低活动
            base_activity = 0.2
        elif 14 <= hour < 17:  # 下午：逐渐增加
            base_activity = 0.5 + (hour - 14) * 0.1
        elif 17 <= hour < 19:  # 加班：高压
            base_activity = 0.8
        else:
            base_activity = 0.1

        noise = random.uniform(-0.15, 0.15)
        activity = max(0.0, min(1.0, base_activity + noise))

        # 根据活动程度生成模拟特征
        work_duration = random.uniform(10, 120) if activity > 0.1 else 0

        data = {
            "timestamp": now,
            "keyboard_speed": round(random.uniform(20, 200) * activity, 2),
            "keyboard_rhythm_cv": round(random.uniform(0.1, 0.8) * activity, 4),
            "typing_pause_ratio": round(random.uniform(0.0, 0.5) * (1 - activity + 0.2), 4),
            "mouse_click_freq": round(random.uniform(5, 60) * activity, 2),
            "mouse_move_speed": round(random.uniform(50, 500) * activity, 2),
            "mouse_scroll_freq": round(random.uniform(2, 30) * activity, 2),
            "window_switch_freq": round(random.uniform(0, 10) * activity, 2),
            "text_content": "",
            "work_duration": round(work_duration, 1),
            "key_count": int(random.uniform(20, 200) * activity),
            "click_count": int(random.uniform(5, 60) * activity),
            "scroll_count": int(random.uniform(2, 30) * activity),
            "window_switches": int(random.uniform(0, 10) * activity),
            "heart_rate": None,
            "gsr_value": None,
        }

        self._history.append(data)
        return data
