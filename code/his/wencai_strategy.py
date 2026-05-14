import os
import logging
import pandas as pd
import pywencai
import akshare as ak
import schedule
import time
import requests
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from notifier import DingTalkNotifier

# 强制禁用代理
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['ALL_PROXY'] = ''
os.environ['NO_PROXY'] = '*'
requests.utils.get_environ_proxies = lambda url: {}

# 配置日志
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler("log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DateManager:
    """A股交易日管理"""
    @staticmethod
    def get_trading_days(count=5):
        try:
            df = ak.tool_trade_date_hist_sina()
            trade_days = df['trade_date'].tolist()
            today = datetime.now().date()
            past_trade_days = [d for d in trade_days if d <= today]
            return sorted(past_trade_days, reverse=True)[:count]
        except Exception as e:
            logger.error(f"获取交易日失败: {e}")
            return []

    @staticmethod
    def is_trade_day():
        try:
            today = datetime.now().date()
            df = ak.tool_trade_date_hist_sina()
            return today in df['trade_date'].values
        except:
            return False

class DataFetcher:
    """问财专用抓取层"""
    def __init__(self):
        self.notifier = DingTalkNotifier()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def wencai_query(self, query: str):
        logger.info(f"正在查询问财: {query}")
        df = pywencai.get(query=query, loop=True)
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def find_col(self, df, keywords):
        """在动态列名中查找匹配的列"""
        for col in df.columns:
            if all(k in str(col) for k in keywords):
                return col
        return None

    def to_num(self, val):
        """安全转换数值"""
        if pd.isna(val): return 0.0
        try:
            return float(str(val).replace('%', '').replace('None', '0'))
        except:
            return 0.0

class QuantumDragon:
    def __init__(self):
        self.fetcher = DataFetcher()
        self.notifier = DingTalkNotifier()

    def task_sniper(self):
        """任务一：The Sniper - 纯问财实时监控"""
        if not DateManager.is_trade_day(): return
        days = DateManager.get_trading_days(2)
        if len(days) < 2: return
        t_0, t_1 = days[0], days[1]
        
        # 优化查询词，显式要求返回指定日期的 5日均线
        q = f"{t_1.strftime('%Y%m%d')}涨停，连续涨停天数>=2，非ST，非退市，今日最低价，最新价，{t_1.strftime('%Y%m%d')}的5日均线"
        df = self.fetcher.wencai_query(q)
        if df.empty:
            logger.info("Sniper 选股池为空")
            return

        col_name = self.fetcher.find_col(df, ['股票简称'])
        col_code = self.fetcher.find_col(df, ['股票代码'])
        col_cur = self.fetcher.find_col(df, ['最新价']) or self.fetcher.find_col(df, ['收盘价', t_0.strftime('%Y%m%d')])
        col_low = self.fetcher.find_col(df, ['最低价', t_0.strftime('%Y%m%d')])
        col_ma5 = self.fetcher.find_col(df, ['5日均线', t_1.strftime('%Y%m%d')])

        if not all([col_cur, col_low, col_ma5]):
            logger.error(f"Sniper 字段匹配失败，原始列名: {df.columns.tolist()}")
            return

        findings = []
        for _, row in df.iterrows():
            name, code = row[col_name], row[col_code]
            cur = self.fetcher.to_num(row[col_cur])
            low = self.fetcher.to_num(row[col_low])
            ma5 = self.fetcher.to_num(row[col_ma5])
            
            if ma5 == 0: continue
            cond1 = (low >= ma5 * 0.99 and 0 <= (cur/ma5-1) <= 0.03)
            cond2 = (low < ma5 and cur >= ma5)
            
            if cond1 or cond2:
                res_type = "支撑位" if cond1 else "金针探底"
                findings.append(f"- **{name}** ({code}) | {res_type} | 现价:{cur} | MA5:{ma5:.2f}")

        if findings:
            msg = f"### 🐉 Sniper 实时低吸预警 (纯问财)\n\n" + "\n".join(findings)
            self.notifier.send_markdown("Sniper 预警", msg)
            logger.info("Sniper 发现机会并已推送")
        else:
            logger.info("Sniper 今日暂无信号")

    def task_auditor(self):
        """任务二：The Auditor - 纯问财回测验证"""
        if not DateManager.is_trade_day(): return
        days = DateManager.get_trading_days(3)
        if len(days) < 3: return
        t_0, t_1, t_2 = days[0], days[1], days[2]
        
        q = f"{t_2.strftime('%Y%m%d')}涨停，连续涨停天数>=2，非ST，非退市，{t_1.strftime('%Y%m%d')}最低价，{t_1.strftime('%Y%m%d')}收盘价，{t_2.strftime('%Y%m%d')}的5日均线，今日最高价，最新价"
        df = self.fetcher.wencai_query(q)
        if df.empty: return

        col_name = self.fetcher.find_col(df, ['股票简称'])
        col_t1_low = self.fetcher.find_col(df, [t_1.strftime('%Y%m%d'), '最低价'])
        col_t1_close = self.fetcher.find_col(df, [t_1.strftime('%Y%m%d'), '收盘价'])
        col_t2_ma5 = self.fetcher.find_col(df, [t_2.strftime('%Y%m%d'), '5日均线'])
        col_t0_high = self.fetcher.find_col(df, ['最高价'])
        col_t0_cur = self.fetcher.find_col(df, ['最新价']) or self.fetcher.find_col(df, ['收盘价', t_0.strftime('%Y%m%d')])

        if not all([col_t1_low, col_t1_close, col_t2_ma5]):
            logger.error(f"Auditor 字段匹配失败，原始列名: {df.columns.tolist()}")
            return

        results = []
        for _, row in df.iterrows():
            name = row[col_name]
            low_t1 = self.fetcher.to_num(row[col_t1_low])
            close_t1 = self.fetcher.to_num(row[col_t1_close])
            ma5_t2 = self.fetcher.to_num(row[col_t2_ma5])
            high_t0 = self.fetcher.to_num(row[col_t0_high])
            cur_t0 = self.fetcher.to_num(row[col_t0_cur])

            if ma5_t2 == 0: continue
            if low_t1 <= ma5_t2 * 1.01 and close_t1 >= ma5_t2:
                results.append(f"- **{name}**: 极限 {((high_t0/ma5_t2)-1)*100:.2f}% | 当前 {((cur_t0/ma5_t2)-1)*100:.2f}%")

        if results:
            msg = f"### 📊 Auditor 回测报告 (纯问财)\n\n" + "\n".join(results)
            self.notifier.send_markdown("Auditor 回测", msg)
            logger.info("Auditor 报告已推送")

def main():
    dragon = QuantumDragon()
    if os.environ.get('TEST_MODE') == 'true':
        dragon.task_sniper()
        dragon.task_auditor()
        return
    schedule.every().monday.to.friday.at("09:35").do(dragon.task_sniper)
    schedule.every().monday.to.friday.at("13:30").do(dragon.task_auditor)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
