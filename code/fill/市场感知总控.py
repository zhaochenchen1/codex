import json
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

# Ensure path awareness
sys.path.append(os.path.dirname(__file__))

# Import modular sensor run functions
from 资金情绪获取 import run_sentiment_module
from 板块题材获取 import run_sector_module
from 指数偏好获取 import run_preference_module
from 股价偏好获取 import run_price_module
from 市值偏好获取 import run_mcap_module

class MarketPerceptionOrchestrator:
    """
    市场感知总控：协调 5 大传感器模块，执行增量获取与统一归档。
    """
    def __init__(self, target_date: str, channel: str = "auto"):
        self.target_date = target_date
        self.channel = channel
        self.json_path = f"tmp/data_cache/{self.target_date}.json"
        self.md_path = f"tmp/{self.target_date}.md"

    def run_all(self):
        print(f"=== 市场感知自动化流水线: {self.target_date} (渠道: {self.channel}) ===")
        
        # 1. 执行模块 (按顺序)
        run_sentiment_module(self.target_date, self.channel)
        run_sector_module(self.target_date, self.channel)
        run_preference_module(self.target_date, self.channel)
        run_price_module(self.target_date, self.channel)
        run_mcap_module(self.target_date, self.channel)
        
        # 2. 合成 MD 报告
        self.generate_report()

    def generate_report(self):
        if not os.path.exists(self.json_path):
            print(f"   警告: 找不到 JSON 文件 {self.json_path}")
            return
            
        with open(self.json_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            
        day_data = raw.get(self.target_date, {})
        mods = day_data.get("modules", {})
        md = f"# 市场感知报告 ({self.target_date})\n\n"
        
        # --- Section 1: Sentiment ---
        md += "## 一、 资金 & 情绪\n"
        if "funds_sentiment" in mods:
            d = mods["funds_sentiment"]["data"]
            md += "| 板块 | 开盘涨跌 | 收盘涨跌 | 最高涨跌 | 最低涨跌 | 收盘点数 | 上涨家数 | 上涨比例 | 下跌家数 | 下跌比例 | 成交额 (亿) | 成交额变化 (亿) | 成交额增长率 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            for k, name in [("sh", "沪市"), ("sz", "深市"), ("cyb", "创业板"), ("kcb", "科创板")]:
                v = d.get(k, {})
                md += f"| **{name}** | {v.get('open_pct','--')} | {v.get('close_pct','--')} | {v.get('high_pct','--')} | {v.get('low_pct','--')} | {v.get('close_pt',0)} | {v.get('up_count',0)} | {v.get('up_ratio','--')} | {v.get('down_count',0)} | {v.get('down_ratio','--')} | {v.get('volume',0)} | {v.get('vol_chg',0)} | {v.get('vol_growth','--')} |\n"
            md += "\n> [待复盘: 请指令 AI 填充此处]\n\n"
        else: md += "> [待获取]\n\n"

        # --- Section 2: Sectors ---
        md += "## 二、 板块题材\n"
        if "sectors" in mods:
            d = mods["sectors"]["data"]
            for k, title in [("gainers", "1、涨幅前二十"), ("losers", "2、跌幅前二十"), ("inflow", "3、资金流入前十"), ("outflow", "4、资金流出前十")]:
                md += f"#### {title}\n"
                items = d.get(k, [])
                if items:
                    header = "| 排名 | 板块名称 | " + ("涨跌幅 |" if "gain" in k or "loss" in k else "资金 (亿) |")
                    md += header + "\n| :--- | :--- | :--- |\n"
                    for i, item in enumerate(items):
                        md += f"| {i+1} | {item['name']} | {item['val']} |\n"
                else: md += "无数据\n"
                md += "\n"
            md += "#### 5、逆势板块分析\n"
            for ct in d.get("counter_trend", []):
                md += f"- **{ct['theme']}**: {', '.join(ct['list'])}\n"
            md += "\n> [待复盘: 请指令 AI 填充此处]\n\n"
        else: md += "> [待获取]\n\n"

        # --- Section 3: Preference ---
        md += "## 三、 沪深创业科创偏好\n"
        if "index_preference" in mods:
            d = mods["index_preference"]["data"]
            md += "#### 1、 指数维度数据对比\n| 指数 | 涨跌幅 | 成交额增长率 | 一年内位置 |\n| :--- | :--- | :--- | :--- |\n"
            for row in d.get("dimensions", []):
                md += f"| {row['name']} | {row['pct_str']} | {row['vol_growth_str']} | {row['position_str']} |\n"
            md += "\n#### 2、 综合评分排名\n| 排名 | 指数名称 | 综合评分 | 状态 |\n| :--- | :--- | :--- | :--- |\n"
            for item in d.get("ranking", []):
                md += f"| {item['rank']} | {item['name']} | {item['score']} | {item['status']} |\n"
            md += "\n> [待复盘: 请指令 AI 填充此处]\n\n"
        else: md += "> [待获取]\n\n"

        # --- Section 4: Price ---
        md += "## 四、 股价偏好\n"
        if "price_preference" in mods:
            res = mods["price_preference"]["data"]
            trans_p = {"b1": "(0, 10] 元", "b2": "(10, 100] 元", "b3": "(100, 300] 元", "b4": "(300, 500] 元", "b5": "(500, 2000] 元", "st": "ST 股全体"}
            md += "| 股价区间 | 上涨家数 | 下跌家数 | 上涨比例 | 下跌比例 |\n| :--- | :--- | :--- | :--- | :--- |\n"
            for k_id in ["b1", "b2", "b3", "b4", "b5", "st"]:
                val = res.get(k_id, {})
                md += f"| {trans_p.get(k_id, k_id)} | {val.get('up',0)} | {val.get('down',0)} | {val.get('up_r','--')} | {val.get('down_r','--')} |\n"
            md += "\n"
        else: md += "> [待获取]\n\n"

        # --- Section 5: MCap ---
        md += "## 五、 市值偏好\n"
        if "mcap_preference" in mods:
            res = mods["mcap_preference"]["data"]
            trans_m = {"b1": "(0, 10] 亿", "b2": "(10, 50] 亿", "b3": "(50, 100] 亿", "b4": "(100, 300] 亿", "b5": "(300, 1000] 亿", "b6": "1000 亿以上"}
            md += "| 市值区间 (亿) | 上涨数量 | 下跌数量 | 上涨比例 | 下跌比例 |\n| :--- | :--- | :--- | :--- | :--- |\n"
            for k_id in ["b1", "b2", "b3", "b4", "b5", "b6"]:
                val = res.get(k_id, {})
                md += f"| {trans_m.get(k_id, k_id)} | {val.get('up',0)} | {val.get('down',0)} | {val.get('up_r','--')} | {val.get('down_r','--')} |\n"
            md += "\n"
        else: md += "> [待获取]\n\n"

        with open(self.md_path, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"=== 统一报告已更新: {self.md_path} ===")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Target date YYYY-MM-DD")
    parser.add_argument("--channel", default="auto", choices=["auto", "skillhub", "direct"])
    args = parser.parse_args()
    
    MarketPerceptionOrchestrator(args.date, args.channel).run_all()
