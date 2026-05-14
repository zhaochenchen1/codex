import os
import logging
import pandas as pd
import pywencai
import akshare as ak
import requests
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from notifier import DingTalkNotifier
from wencai_strategy import DateManager

# 强制直连
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['ALL_PROXY'] = ''
os.environ['NO_PROXY'] = '*'
requests.utils.get_environ_proxies = lambda url: {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConceptMirrorPipeline:
    def __init__(self):
        self.notifier = DingTalkNotifier()
        self.blacklist = {
            '融资融券', '深股通', '沪股通', '标普大盘', 'MSCI', '富时罗素', '转融通', '填权', 
            '昨日涨停', '含可转债', '地方国资改革', '国企改革', '央企国企改革', '壳资源',
            '证金持股', '中央汇金持股', '举牌', '股权转让', '破净股', '创业板重组松绑',
            '近期强势股', '已获批筹', '预盈预增', '送转预期', '小盘股', '中盘股', '大盘股',
            '新股与次新股', '沪证券', '深证券', 'a股', '高送转', '均线空头', '中特估',
            '参股银行', '参股券商', '人工智能', '互联网+', '破净资产', '昨日涨停', '华为概念'
        }

    @staticmethod
    def get_dates():
        df = ak.tool_trade_date_hist_sina()
        trade_days = df['trade_date'].tolist()
        today = datetime.now().date()
        past_days = [d for d in trade_days if d <= today]
        sorted_days = sorted(past_days, reverse=True)
        return sorted_days[0], sorted_days[1]

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def fetch_limit_ups(self, date_str):
        query = f"{date_str}涨停，非ST，非新三板，所属概念，{date_str}首次涨停时间"
        logger.info(f"正在查询问财: {query}")
        return pywencai.get(query=query, loop=True)

    def find_col(self, df, keywords):
        for col in df.columns:
            if all(k in str(col) for k in keywords): return col
        return None

    def get_exploded_df(self, df, date_str):
        if df is None or df.empty: return pd.DataFrame(), []
        col_name = self.find_col(df, ['股票简称'])
        col_concept = self.find_col(df, ['所属概念'])
        col_time = self.find_col(df, ['首次涨停时间', date_str]) or self.find_col(df, ['首次涨停时间'])
        
        raw_list = []
        for _, row in df.iterrows():
            concepts = str(row[col_concept]).split(';')
            for cp in concepts:
                cp = cp.strip()
                if cp and cp != 'None' and cp not in self.blacklist:
                    raw_list.append({'concept': cp, 'name': row[col_name], 'time': row[col_time] or '未知'})
        return pd.DataFrame(raw_list), df[col_name].unique().tolist()

    def run(self):
        try:
            # 1. 交易日判定
            if not DateManager.is_trade_day():
                logger.info("当前非 A 股交易日，脚本跳过执行。")
                return

            t_0_dt, t_1_dt = self.get_dates()
            t_0, t_1 = t_0_dt.strftime('%Y%m%d'), t_1_dt.strftime('%Y%m%d')
            
            raw_yest = self.fetch_limit_ups(t_1)
            raw_today = self.fetch_limit_ups(t_0)
            
            exp_yest, pool_yest = self.get_exploded_df(raw_yest, t_1)
            exp_today, pool_today = self.get_exploded_df(raw_today, t_0)
            
            if exp_yest.empty or exp_today.empty: 
                logger.error("数据不足，无法对比")
                return

            # 段落 1: 昨日领涨 Top 15 (延续性)
            top_15_yest = exp_yest.groupby('concept').size().sort_values(ascending=False).head(15).index.tolist()
            md = f"### 📊 段落1《昨日领涨板块数据》\n"
            md += f"**基准日**: {t_1}\n\n"
            for i, concept in enumerate(top_15_yest, 1):
                gy = exp_yest[exp_yest['concept'] == concept].sort_values(by='time')
                gt = exp_today[exp_today['concept'] == concept].sort_values(by='time')
                
                md += f"{i}. {concept} (昨日：{len(gy)}家，今日：{len(gt)}家)\n"
                md += f" - ├ 昨日领涨: `{gy.iloc[0]['name']}` ({gy.iloc[0]['time']})\n"
                md += f" - └ 今日领涨: {gt.iloc[0]['name'] + ' (' + gt.iloc[0]['time'] + ')' if not gt.empty else '今日无涨停'}\n\n"

            # 段落 2: 今日领涨 Top 15 (底蕴挖掘)
            top_15_today = exp_today.groupby('concept').size().sort_values(ascending=False).head(15).index.tolist()
            md += f"### 🚀 段落2《今日领涨板块数据》\n"
            md += f"**实时日**: {t_0}\n\n"
            for i, concept in enumerate(top_15_today, 1):
                gt = exp_today[exp_today['concept'] == concept].sort_values(by='time')
                gy = exp_yest[exp_yest['concept'] == concept].sort_values(by='time')
                
                md += f"{i}. {concept} (昨日：{len(gy)}家，今日：{len(gt)}家)\n"
                md += f" - ├ 今日领涨: `{gt.iloc[0]['name']}` ({gt.iloc[0]['time']})\n"
                md += f" - └ 昨日领涨: {gy.iloc[0]['name'] + ' (' + gy.iloc[0]['time'] + ')' if not gy.empty else '昨日未涨停'}\n\n"

            # 跨界总结计算
            y_cross_3 = exp_yest[exp_yest['concept'].isin(top_15_yest)].groupby('name').size()
            list_yest_3 = y_cross_3[y_cross_3 >= 3].index.tolist()
            
            t_cross_3 = exp_today[exp_today['concept'].isin(top_15_today)].groupby('name').size()
            list_today_3 = t_cross_3[t_cross_3 >= 3].index.tolist()
            
            super_dragon = list(set(list_yest_3) & set(list_today_3))

            md += "---\n"
            md += f"**💡 今日跨3概念龙**: {', '.join([f'`{n}`' for n in list_today_3]) if list_today_3 else '无'}\n"
            md += f"**💎 超级总结《连续两日核心跨界龙》**\n"
            md += f" > {('、'.join([f'**{n}**' for n in super_dragon])) if super_dragon else '今日暂无核心共振灵魂标的'}\n\n"
            md += f"> (规则：单股在当日 TOP 15 板块中跨 3 个以上核心概念)"

            self.notifier.send_markdown(f"镜像热点对比-{t_0}", md)
            logger.info("推送成功")
            
        except Exception as e:
            logger.error(f"运行失败: {e}", exc_info=True)

import schedule
import time

def main():
    pipeline = ConceptMirrorPipeline()
    
    # 立即测试模式
    if os.environ.get('TEST_MODE') == 'true':
        logger.info("执行单次手动测试...")
        pipeline.run()
        return

    # 设定定时任务
    schedule.every().day.at("10:30").do(pipeline.run)
    schedule.every().day.at("11:30").do(pipeline.run)
    schedule.every().day.at("14:30").do(pipeline.run)

    logger.info("板块镜像监控调度启动，等待定时触发 (10:30, 11:30, 14:30)...")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
