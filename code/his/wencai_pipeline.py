import os
import json
import logging
import pandas as pd
import pywencai
import schedule
import time
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from notifier import DingTalkNotifier

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

class WencaiDragonPipeline:
    """
    A-股龙头股自动化脱水与筛选管线
    """
    
    def __init__(self):
        self.query = "连续涨停天数>0, 涨跌幅, 换手率, 成交额, 股票简称, 行业"
        # 核心字段映射表（处理问财动态字段名）
        self.field_map = {
            '股票代码': 'code',
            '股票简称': 'name',
            '最新价': 'price',
            '涨跌幅': 'pct_chg',
            '连续涨停天数': 'limit_up_days',
            '成交额': 'amount',
            '换手率': 'turnover_rate',
            '所属同花顺行业': 'industry'
        }

    # ==========================================
    # 1. Fetch Layer (数据拉取)
    # ==========================================
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(f"Retrying Wencai API... Attempt {retry_state.attempt_number}")
    )
    def fetch_data(self) -> pd.DataFrame:
        """从问财接口抓取原始数据"""
        df = pywencai.get(query=self.query, loop=True)
        if df is None or df.empty:
            raise ValueError("Empty data returned from pywencai")
        return df

    # ==========================================
    # 2. Clean & Audit Layer (脱水与清洗)
    # ==========================================
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据瘦身与类型标准化"""
        # 识别问财动态生成的列名 (例如 "连续涨停天数[20231027]")
        cleaned_cols = {}
        for col in df.columns:
            for key, val in self.field_map.items():
                if key in col:
                    cleaned_cols[col] = val
        
        # 仅保留命中映射的列
        df = df[list(cleaned_cols.keys())].rename(columns=cleaned_cols)
        
        # 向量化清洗：处理百分比和数值转换
        def to_numeric(series):
            return pd.to_numeric(series.astype(str).str.replace('%', '').str.replace('None', '0'), errors='coerce').fillna(0)

        numeric_fields = ['price', 'pct_chg', 'limit_up_days', 'amount', 'turnover_rate']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = to_numeric(df[field])

        # 归一化代码格式 (e.g., 000001.SZ)
        if 'code' in df.columns:
            df['code'] = df['code'].astype(str)
            
        return df.dropna(subset=['code', 'name'])

    # ==========================================
    # 3. Routing & Sort Layer (路由与精排)
    # ==========================================
    def rank_stocks(self, df: pd.DataFrame) -> dict:
        """
        核心排序逻辑：
        1. 空间龙：按连续涨停天数降序
        2. 容量中军：大成交额 + 高换手 (筛选成交额 > 10亿)
        """
        # 提取空间龙 (Space Dragon)
        space_dragons = df.sort_values(by='limit_up_days', ascending=False).head(5)
        
        # 提取容量中军 (Volume Leader)
        # 过滤成交额（单位通常为元，需根据返回调整，此处假设为元，过滤大于10亿）
        volume_leaders = df[df['amount'] > 10**9].sort_values(
            by=['amount', 'turnover_rate'], 
            ascending=[False, False]
        ).head(5)

        return {
            "space_dragons": space_dragons.to_dict(orient='records'),
            "volume_leaders": volume_leaders.to_dict(orient='records'),
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ==========================================
    # 4. Export Layer (输出)
    # ==========================================
    def export(self, data: dict):
        """格式化输出并推送至钉钉"""
        report_time = data['update_time']
        print(f"\n{'='*20} A股每日龙头脱水报告 ({report_time}) {'='*20}")
        
        md_content = f"### 🐉 A股每日龙头脱水报告\n**更新时间**: {report_time}\n\n"
        
        print("\n[ 空间龙 Top 5 ] (连板高度核心)")
        md_content += "#### 🚀 空间龙 Top 5 (连板核心)\n"
        for i, s in enumerate(data['space_dragons'], 1):
            line = f"{i}. {s['name']} ({s['code']}) | {int(s['limit_up_days'])}连板 | 涨幅: {s['pct_chg']:.2f}%"
            print(line)
            md_content += f"- {line}\n"

        print("\n[ 容量中军 Top 5 ] (大资金战场)")
        md_content += "\n#### 💰 容量中军 Top 5 (大资金战场)\n"
        for i, s in enumerate(data['volume_leaders'], 1):
            amount_str = f"{s['amount']/10**8:.2f}亿"
            line = f"{i}. {s['name']} ({s['code']}) | 成交: {amount_str} | 换手: {s['turnover_rate']:.2f}%"
            print(line)
            md_content += f"- {line}\n"
        
        # 执行推送
        try:
            notifier = DingTalkNotifier()
            notifier.send_markdown("龙头股脱水报告", md_content)
        except Exception as e:
            logger.error(f"Notification error: {e}")

    def run_pipeline(self):
        """单次执行流程"""
        try:
            logger.info("Starting pipeline execution...")
            raw_df = self.fetch_data()
            clean_df = self.clean_data(raw_df)
            results = self.rank_stocks(clean_df)
            self.export(results)
            logger.info("Pipeline executed successfully.")
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}", exc_info=True)

def main():
    pipeline = WencaiDragonPipeline()
    
    # 设定每日 15:30 自动执行
    schedule.every().day.at("15:30").do(pipeline.run_pipeline)
    
    # 首次立即启动测试
    pipeline.run_pipeline()
    
    # 如果是 CI 或测试环境，可以通过环境变量跳过无限循环
    if os.environ.get('TEST_MODE') == 'true':
        return

    logger.info("Scheduler started. Waiting for next run...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
