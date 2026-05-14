import pymysql
import json
from datetime import datetime
from code.longtou.config import Config
from code.longtou.logger import setup_logger

logger = setup_logger(__name__)

class DBManager:
    """MySQL 数据库管理类"""
    
    def __init__(self):
        self.host = Config.DB_HOST
        self.port = Config.DB_PORT
        self.user = Config.DB_USER
        self.password = Config.DB_PASS
        self.database = Config.DB_NAME

    def _get_connection(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

    def save_snapshot(self, date_str, time_slot, data):
        """保存分时快照到数据库"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 尝试插入今日行，如果已存在则忽略
                cursor.execute(
                    "INSERT IGNORE INTO daily_market_snapshots (trade_date) VALUES (%s)",
                    (date_str,)
                )
                
                # 更新对应时间点的 JSON 数据
                field_name = f"data_{time_slot.replace(':', '')}"
                json_data = json.dumps(data, ensure_ascii=False)
                sql = f"UPDATE daily_market_snapshots SET {field_name} = %s WHERE trade_date = %s"
                cursor.execute(sql, (json_data, date_str))
                
            conn.commit()
            logger.info(f"成功保存 {date_str} {time_slot} 的快照数据")
        except Exception as e:
            logger.error(f"保存快照失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_today_snapshots(self, date_str):
        """获取今日已存储的所有快照"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT data_1030, data_1130, data_1430 FROM daily_market_snapshots WHERE trade_date = %s"
                cursor.execute(sql, (date_str,))
                result = cursor.fetchone()
                if result:
                    # 将 JSON 字符串转换回 Python 对象
                    for key in result:
                        if result[key]:
                            result[key] = json.loads(result[key])
                    return result
                return None
        except Exception as e:
            logger.error(f"读取快照失败: {e}")
            return None
        finally:
            conn.close()
            
    def save_summary(self, date_str, summary):
        """保存当日总结"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE daily_market_snapshots SET daily_summary = %s WHERE trade_date = %s"
                cursor.execute(sql, (summary, date_str))
            conn.commit()
        except Exception as e:
            logger.error(f"保存总结失败: {e}")
        finally:
            conn.close()
