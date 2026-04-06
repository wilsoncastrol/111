"""
storage.py - 数据存储模块
多模态交互压力数据分析系统

功能：
- 本地 SQLite 数据库存储
- 加密存储支持（可选）
- 历史数据查询
- Excel 报告导出
- 数据备份与清除
- 所有数据仅在本地存储
"""

import os
import json
import sqlite3
import shutil
from datetime import datetime, timedelta

from config import (
    debug_print, DB_PATH, EXPORT_DIR, BACKUP_DIR,
    STRESS_LEVELS, STRESS_SOURCES,
)

# 尝试导入 pandas（Excel 导出）
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    debug_print("警告: pandas 未安装，Excel导出功能不可用")


class StorageManager:
    """
    本地数据存储管理器

    使用 SQLite 存储压力分析数据，支持：
    - 写入分析结果
    - 按时间范围查询
    - 汇总统计
    - Excel 导出
    - 数据备份/清除
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_db()
        debug_print(f"StorageManager 初始化完成 | DB: {self.db_path}")

    # ============================================================
    # 数据库初始化
    # ============================================================

    def _init_db(self):
        """创建数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 压力记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stress_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                stress_score REAL NOT NULL,
                stress_level INTEGER NOT NULL,
                stress_level_name TEXT,
                stress_sources TEXT,
                feature_scores TEXT,
                text_sentiment REAL,
                keyboard_speed REAL,
                mouse_click_freq REAL,
                mouse_move_speed REAL,
                mouse_scroll_freq REAL,
                window_switch_freq REAL,
                typing_pause_ratio REAL,
                work_duration REAL,
                key_count INTEGER,
                click_count INTEGER,
                heart_rate REAL,
                gsr_value REAL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 预警记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                stress_level INTEGER NOT NULL,
                message TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 用户设置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stress_timestamp
            ON stress_records(timestamp)
        """)

        conn.commit()
        conn.close()

    # ============================================================
    # 写入数据
    # ============================================================

    def save_result(self, result):
        """保存分析结果到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            raw = result.get("raw_data", {})
            timestamp = result["timestamp"]
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO stress_records (
                    timestamp, stress_score, stress_level, stress_level_name,
                    stress_sources, feature_scores, text_sentiment,
                    keyboard_speed, mouse_click_freq, mouse_move_speed,
                    mouse_scroll_freq, window_switch_freq, typing_pause_ratio,
                    work_duration, key_count, click_count, heart_rate, gsr_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                result.get("stress_score", 0),
                result.get("stress_level", 0),
                result.get("stress_level_name", ""),
                json.dumps(result.get("stress_sources", []), ensure_ascii=False),
                json.dumps(result.get("feature_scores", {})),
                result.get("text_sentiment", 0.5),
                raw.get("keyboard_speed", 0),
                raw.get("mouse_click_freq", 0),
                raw.get("mouse_move_speed", 0),
                raw.get("mouse_scroll_freq", 0),
                raw.get("window_switch_freq", 0),
                raw.get("typing_pause_ratio", 0),
                raw.get("work_duration", 0),
                raw.get("key_count", 0),
                raw.get("click_count", 0),
                raw.get("heart_rate"),
                raw.get("gsr_value"),
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            debug_print(f"保存数据失败: {e}")

    def save_alert(self, stress_level, message):
        """保存预警记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alert_records (timestamp, stress_level, message)
                VALUES (?, ?, ?)
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), stress_level, message))
            conn.commit()
            conn.close()
        except Exception as e:
            debug_print(f"保存预警记录失败: {e}")

    # ============================================================
    # 查询数据
    # ============================================================

    def get_records(self, start_time=None, end_time=None, limit=1000):
        """查询压力记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if start_time and end_time:
                if isinstance(start_time, datetime):
                    start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(end_time, datetime):
                    end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                    SELECT * FROM stress_records
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (start_time, end_time, limit))
            else:
                cursor.execute("""
                    SELECT * FROM stress_records
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                record = dict(row)
                # 解析 JSON 字段
                try:
                    record["stress_sources"] = json.loads(record.get("stress_sources", "[]"))
                except (json.JSONDecodeError, TypeError):
                    record["stress_sources"] = []
                try:
                    record["feature_scores"] = json.loads(record.get("feature_scores", "{}"))
                except (json.JSONDecodeError, TypeError):
                    record["feature_scores"] = {}
                results.append(record)

            return results

        except Exception as e:
            debug_print(f"查询数据失败: {e}")
            return []

    def get_today_records(self):
        """获取今日记录"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_records(
            start_time=f"{today} 00:00:00",
            end_time=f"{today} 23:59:59"
        )

    def get_records_by_period(self, period="day"):
        """按周期获取记录: day/week/month"""
        now = datetime.now()
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now - timedelta(days=30)

        return self.get_records(start_time=start, end_time=now)

    def get_daily_summary(self, days=30):
        """获取每日汇总数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT
                    date(timestamp) as date,
                    AVG(stress_score) as avg_score,
                    MAX(stress_score) as max_score,
                    MIN(stress_score) as min_score,
                    COUNT(*) as record_count
                FROM stress_records
                WHERE date(timestamp) >= ?
                GROUP BY date(timestamp)
                ORDER BY date ASC
            """, (start_date,))

            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "date": row[0],
                    "avg_score": round(row[1], 1),
                    "max_score": round(row[2], 1),
                    "min_score": round(row[3], 1),
                    "record_count": row[4],
                }
                for row in rows
            ]

        except Exception as e:
            debug_print(f"获取每日汇总失败: {e}")
            return []

    def get_hourly_summary(self, date=None):
        """获取指定日期的每小时汇总"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT
                    strftime('%H', timestamp) as hour,
                    AVG(stress_score) as avg_score,
                    COUNT(*) as record_count
                FROM stress_records
                WHERE date(timestamp) = ?
                GROUP BY strftime('%H', timestamp)
                ORDER BY hour ASC
            """, (date,))

            rows = cursor.fetchall()
            conn.close()

            return [
                {
                    "hour": int(row[0]),
                    "avg_score": round(row[1], 1),
                    "record_count": row[2],
                }
                for row in rows
            ]

        except Exception as e:
            debug_print(f"获取每小时汇总失败: {e}")
            return []

    def get_record_count(self):
        """获取总记录数"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stress_records")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    # ============================================================
    # Excel 导出
    # ============================================================

    def export_to_excel(self, start_time=None, end_time=None, filename=None):
        """
        导出数据到 Excel 文件

        返回: 导出文件的完整路径，失败返回 None
        """
        if not PANDAS_AVAILABLE:
            debug_print("pandas 未安装，无法导出 Excel")
            return None

        records = self.get_records(start_time=start_time, end_time=end_time, limit=10000)
        if not records:
            debug_print("没有可导出的数据")
            return None

        try:
            # 构建 DataFrame
            data = []
            for r in records:
                sources = r.get("stress_sources", [])
                if isinstance(sources, list):
                    source_names = [STRESS_SOURCES.get(s, s) for s in sources]
                else:
                    source_names = []

                data.append({
                    "时间": r.get("timestamp", ""),
                    "压力分数": r.get("stress_score", 0),
                    "压力等级": r.get("stress_level_name", ""),
                    "压力来源": "、".join(source_names),
                    "键盘速度(键/分)": r.get("keyboard_speed", 0),
                    "鼠标点击(次/分)": r.get("mouse_click_freq", 0),
                    "鼠标速度(像素/秒)": r.get("mouse_move_speed", 0),
                    "窗口切换(次/分)": r.get("window_switch_freq", 0),
                    "工作时长(分钟)": r.get("work_duration", 0),
                    "文本情绪": r.get("text_sentiment", 0),
                })

            df = pd.DataFrame(data)

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"压力分析报告_{timestamp}.xlsx"

            filepath = os.path.join(EXPORT_DIR, filename)
            df.to_excel(filepath, index=False, sheet_name="压力数据")

            debug_print(f"数据已导出到: {filepath}")
            return filepath

        except Exception as e:
            debug_print(f"Excel 导出失败: {e}")
            return None

    # ============================================================
    # 备份与清除
    # ============================================================

    def backup_database(self):
        """备份数据库文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"stress_data_backup_{timestamp}.db")
            shutil.copy2(self.db_path, backup_path)
            debug_print(f"数据库已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            debug_print(f"备份失败: {e}")
            return None

    def clear_all_data(self):
        """清除所有数据（危险操作！）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stress_records")
            cursor.execute("DELETE FROM alert_records")
            conn.commit()
            conn.close()
            debug_print("所有数据已清除")
            return True
        except Exception as e:
            debug_print(f"清除数据失败: {e}")
            return False

    def clear_old_data(self, days=90):
        """清除指定天数之前的旧数据"""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stress_records WHERE date(timestamp) < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            debug_print(f"已清除 {deleted} 条 {days} 天前的旧数据")
            return deleted
        except Exception as e:
            debug_print(f"清除旧数据失败: {e}")
            return 0

    # ============================================================
    # 用户设置
    # ============================================================

    def save_setting(self, key, value):
        """保存用户设置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_settings (key, value, updated_at)
                VALUES (?, ?, datetime('now', 'localtime'))
            """, (key, json.dumps(value, ensure_ascii=False)))
            conn.commit()
            conn.close()
        except Exception as e:
            debug_print(f"保存设置失败: {e}")

    def get_setting(self, key, default=None):
        """获取用户设置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
            return default
        except Exception:
            return default

    def get_db_size(self):
        """获取数据库文件大小（KB）"""
        try:
            return round(os.path.getsize(self.db_path) / 1024, 1)
        except Exception:
            return 0
