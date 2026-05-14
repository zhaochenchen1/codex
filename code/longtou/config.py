import os
from code.longtou.logger import setup_logger

logger = setup_logger(__name__)

class Config:
    """配置加载类"""
    
    # MySQL 配置
    DB_HOST = "localhost"
    DB_PORT = 3306
    DB_USER = "root"
    DB_PASS = "7605168839"
    DB_NAME = "wencai"
    
    # 钉钉配置
    DINGTALK_WEBHOOK = ""
    DINGTALK_SECRET = ""

    @classmethod
    def load(cls):
        """从文件加载配置"""
        # 加载 MySQL 配置
        mysql_path = "config/mysql.md"
        if os.path.exists(mysql_path):
            with open(mysql_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'url：' in line:
                        url_part = line.split('：')[1].strip()
                        cls.DB_HOST = url_part.split(':')[0]
                        cls.DB_PORT = int(url_part.split(':')[1])
                    if 'database:' in line:
                        cls.DB_NAME = line.split(':')[1].strip()
                    if 'user:' in line:
                        cls.DB_USER = line.split(':')[1].strip()
                    if 'pass:' in line:
                        cls.DB_PASS = line.split(':')[1].strip()
            logger.info("MySQL 配置加载成功")

        # 加载钉钉配置
        ding_path = "code/his/null.txt"
        if os.path.exists(ding_path):
            with open(ding_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'ddpushurl=' in line:
                        cls.DINGTALK_WEBHOOK = line.split('ddpushurl=')[1].strip()
                    if 'ddsecret=' in line:
                        cls.DINGTALK_SECRET = line.split('ddsecret=')[1].strip()
            logger.info("钉钉配置加载成功")

Config.load()
