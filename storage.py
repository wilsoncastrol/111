"""
多模态交互压力数据分析系统 - 本地SQLite存储模块
Local SQLite storage with optional encryption for collected data and analysis results.
"""

import sqlite3
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import (
    DB_PATH,
    BACKUP_DIR,
    ENCRYPTION_ENABLED,
    logger,
)

# 尝试导入加密库（可选）
try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography 库未安装，数据加密功能不可用")


class StorageManager:
    """本地数据存储管理器，使用SQLite + 可选加密"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._cipher = None

        if ENCRYPTION_ENABLED and CRYPTO_AVAILABLE:
            self._init_encryption()

        self._connect()
        self._create_tables()
        logger.info(f"存储管理器已初始化，数据库: {self.db_path}")

    def _init_encryption(self):
        """初始化加密器（首次运行时生成密钥并保存）"""
        key_path = os.path.join(os.path.dirname(self.db_path), ".encryption_key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(key)
            # 设置文件权限为仅所有者可读写
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass  # Windows可能不支持
        self._cipher = Fernet(key)
        logger.debug("数据加密已启用")

    def _encrypt(self, data: str) -> str:
        """加密字符串数据"""
        if self._cipher:
            return self._cipher.encrypt(data.encode("utf-8")).decode("utf-8")
        return data

    def _decrypt(self, data: str) -> str:
        """解密字符串数据"""
        if self._cipher:
            try:
                return self._cipher.decrypt(data.encode("utf-8")).decode("utf-8")
            except Exception:
                logger.warning("数据解密失败，可能是未加密的旧数据")
                return data
        return data

    def _connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # 启用WAL模式提高并发性能
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()

        # 原始采集数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                data_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 压力分析结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stress_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                stress_score REAL NOT NULL,
                stress_level INTEGER NOT NULL,
                sources_json TEXT,
                features_json TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 预警记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
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
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_data_timestamp
            ON raw_data(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stress_records_timestamp
            ON stress_records(timestamp)
        """)

        self.conn.commit()
        logger.debug("数据库表已创建/验证")

    # ==================== 原始数据操作 ====================

    def save_raw_data(self, data_type: str, data: dict):
        """保存原始采集数据"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_json = json.dumps(data, ensure_ascii=False)

        if self._cipher:
            data_json = self._encrypt(data_json)

        self.conn.execute(
            "INSERT INTO raw_data (timestamp, data_type, data_json) VALUES (?, ?, ?)",
            (timestamp, data_type, data_json),
        )
        self.conn.commit()

    def get_raw_data(self, data_type: str = None, hours: int = 24) -> list:
        """获取原始数据"""
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        if data_type:
            rows = self.conn.execute(
                "SELECT * FROM raw_data WHERE data_type = ? AND timestamp >= ? ORDER BY timestamp",
                (data_type, since),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM raw_data WHERE timestamp >= ? ORDER BY timestamp",
                (since,),
            ).fetchall()

        result = []
        for row in rows:
            data_json = row["data_json"]
            if self._cipher:
                data_json = self._decrypt(data_json)
            result.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "data_type": row["data_type"],
                "data": json.loads(data_json),
            })
        return result

    # ==================== 压力记录操作 ====================

    def save_stress_record(self, score: float, level: int, sources: dict = None, features: dict = None):
        """保存压力分析结果"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sources_json = json.dumps(sources or {}, ensure_ascii=False)
        features_json = json.dumps(features or {}, ensure_ascii=False)

        self.conn.execute(
            "INSERT INTO stress_records (timestamp, stress_score, stress_level, sources_json, features_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (timestamp, score, level, sources_json, features_json),
        )
        self.conn.commit()
        logger.debug(f"已保存压力记录: score={score:.1f}, level={level}")

    def get_stress_records(self, hours: int = 24) -> pd.DataFrame:
        """获取压力记录，返回DataFrame"""
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        df = pd.read_sql_query(
            "SELECT * FROM stress_records WHERE timestamp >= ? ORDER BY timestamp",
            self.conn,
            params=(since,),
            parse_dates=["timestamp"],
        )
        return df

    def get_stress_records_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指定日期范围内的压力记录"""
        df = pd.read_sql_query(
            "SELECT * FROM stress_records WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
            self.conn,
            params=(start_date, end_date + " 23:59:59"),
            parse_dates=["timestamp"],
        )
        return df

    def get_latest_stress(self) -> Optional[dict]:
        """获取最新一条压力记录"""
        row = self.conn.execute(
            "SELECT * FROM stress_records ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            return {
                "timestamp": row["timestamp"],
                "score": row["stress_score"],
                "level": row["stress_level"],
                "sources": json.loads(row["sources_json"]) if row["sources_json"] else {},
                "features": json.loads(row["features_json"]) if row["features_json"] else {},
            }
        return None

    # ==================== 预警记录操作 ====================

    def save_alert(self, alert_type: str, stress_level: int, message: str):
        """保存预警记录"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO alert_records (timestamp, alert_type, stress_level, message) VALUES (?, ?, ?, ?)",
            (timestamp, alert_type, stress_level, message),
        )
        self.conn.commit()

    def get_alerts(self, hours: int = 24) -> list:
        """获取预警记录"""
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.conn.execute(
            "SELECT * FROM alert_records WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ==================== 用户设置操作 ====================

    def save_setting(self, key: str, value):
        """保存用户设置"""
        value_json = json.dumps(value, ensure_ascii=False)
        self.conn.execute(
            "INSERT OR REPLACE INTO user_settings (key, value, updated_at) VALUES (?, ?, datetime('now', 'localtime'))",
            (key, value_json),
        )
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        """获取用户设置"""
        row = self.conn.execute(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row["value"])
        return default

    # ==================== 数据管理 ====================

    def export_to_excel(self, filepath: str, hours: int = 720):
        """导出数据到Excel文件"""
        df = self.get_stress_records(hours=hours)
        if df.empty:
            logger.warning("没有数据可导出")
            return False

        # 格式化列名为中文
        df_export = df.rename(columns={
            "timestamp": "时间",
            "stress_score": "压力评分",
            "stress_level": "压力等级",
        })

        # 添加压力等级中文名称
        from config import STRESS_LEVELS
        level_names = {k: v["name"] for k, v in STRESS_LEVELS.items()}
        df_export["压力等级名称"] = df_export["压力等级"].map(level_names)

        # 选择导出的列
        export_cols = ["时间", "压力评分", "压力等级", "压力等级名称"]
        df_export[export_cols].to_excel(filepath, index=False, engine="openpyxl")

        logger.info(f"数据已导出到: {filepath}")
        return True

    def backup_database(self) -> str:
        """备份数据库"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"stress_data_backup_{timestamp}.db")
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"数据库已备份到: {backup_path}")
        return backup_path

    def clear_data(self, before_date: str = None):
        """清除数据（可指定日期之前的数据）"""
        cursor = self.conn.cursor()
        if before_date:
            cursor.execute("DELETE FROM raw_data WHERE timestamp < ?", (before_date,))
            cursor.execute("DELETE FROM stress_records WHERE timestamp < ?", (before_date,))
            cursor.execute("DELETE FROM alert_records WHERE timestamp < ?", (before_date,))
            logger.info(f"已清除 {before_date} 之前的所有数据")
        else:
            cursor.execute("DELETE FROM raw_data")
            cursor.execute("DELETE FROM stress_records")
            cursor.execute("DELETE FROM alert_records")
            logger.info("已清除所有数据")
        self.conn.commit()
        # 回收空间
        self.conn.execute("VACUUM")

    def get_data_stats(self) -> dict:
        """获取数据库统计信息"""
        stats = {}
        stats["raw_data_count"] = self.conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
        stats["stress_records_count"] = self.conn.execute("SELECT COUNT(*) FROM stress_records").fetchone()[0]
        stats["alert_records_count"] = self.conn.execute("SELECT COUNT(*) FROM alert_records").fetchone()[0]
        stats["db_size_mb"] = os.path.getsize(self.db_path) / (1024 * 1024)

        # 最早和最晚记录时间
        row = self.conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM stress_records").fetchone()
        stats["earliest_record"] = row[0] if row[0] else "无记录"
        stats["latest_record"] = row[1] if row[1] else "无记录"

        return stats

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.debug("数据库连接已关闭")

    def __del__(self):
        self.close()
