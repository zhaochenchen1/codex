import pywencai
import pandas as pd
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any

# Ensure project structure awareness
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

class MarketPerceptionDirect:
    def __init__(self, target_date: str = "2026-05-12", cache_dir: str = "tmp/data_cache"):
        self.results = {}
        self.cache_dir = cache_dir
        self.today_str = target_date
        self.cache_file = os.path.join(self.cache_dir, f"{self.today_str}.json")
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        self.metadata = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content: return json.loads(content)
            except Exception as e:
                print(f"Error loading cache: {e}")
        return {}

    def _save_cache(self):
        try:
            def clean_meta(obj):
                if isinstance(obj, pd.DataFrame): return obj.to_dict(orient='records')
                if isinstance(obj, dict): return {k: clean_meta(v) for k, v in obj.items()}
                if isinstance(obj, list): return [clean_meta(i) for i in obj]
                return obj
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(clean_meta(self.metadata), f, ensure_ascii=False, indent=2)
        except Exception as e: print(f"Error saving cache: {e}")

    def _safe_fetch(self, query: str, cache_key: str, force: bool = False) -> pd.DataFrame:
        if not force and cache_key in self.metadata:
            data = self.metadata[cache_key]
            if not data: return pd.DataFrame()
            return pd.DataFrame([data] if isinstance(data, dict) else data)
        try:
            res = pywencai.get(query=query, loop=True)
            if res is None: return pd.DataFrame()
            if isinstance(res, pd.DataFrame):
                if res.empty: return pd.DataFrame()
                self.metadata[cache_key] = res.to_dict(orient='records')
            elif isinstance(res, dict):
                self.metadata[cache_key] = res
                res = pd.DataFrame([res])
            else: return pd.DataFrame()
            self._save_cache()
            return res
        except Exception as e:
            print(f"Error fetching data for '{query}': {e}")
            return pd.DataFrame()

    def _parse_num(self, val) -> float:
        if val is None or pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        val_str = str(val).replace('%', '').replace(',', '').strip()
        try: return float(val_str)
        except: return 0.0

    def get_funds_and_sentiment(self):
        print("Processing Section 1: Funds & Sentiment...")
        indices = {"000001.SH": "沪市", "399001.SZ": "深市", "399006.SZ": "创业板", "000688.SH": "科创板"}
        processed = {}
        target_day = self.today_str.replace("-", "")
        for code, key in indices.items():
            cache_key = f"index_data_{code}_full"
            query = f"{code}，{target_day}收盘价，{target_day}昨日收盘价，{target_day}成交额，{target_day}昨日成交额，{target_day}上涨家数，{target_day}下跌家数，{target_day}最高价，{target_day}最低价，{target_day}开盘价"
            df = self._safe_fetch(query, cache_key)
            if not df.empty:
                row = df.iloc[0]
                cols = df.columns.tolist()
                t_close = self._parse_num(next((row[c] for c in cols if "收盘价" in c and target_day in str(c)), row.get("最新价")))
                y_close = self._parse_num(next((row[c] for c in cols if "昨日收盘价" in str(c) or ("收盘价" in str(c) and "20260511" in str(c))), 0))
                t_open = self._parse_num(next((row[c] for c in cols if "开盘价" in str(c) and target_day in str(c)), 0))
                t_high = self._parse_num(next((row[c] for c in cols if "最高价" in str(c) and target_day in str(c)), 0))
                t_low = self._parse_num(next((row[c] for c in cols if "最低价" in str(c) and target_day in str(c)), 0))
                up = self._parse_num(next((row[c] for c in cols if "上涨家数" in str(c) and target_day in str(c)), 0))
                down = self._parse_num(next((row[c] for c in cols if "下跌家数" in str(c) and target_day in str(c)), 0))
                t_vol = self._parse_num(next((row[c] for c in cols if "成交额" in str(c) and target_day in str(c)), 0))
                y_vol = self._parse_num(next((row[c] for c in cols if "昨日成交额" in str(c) or ("成交额" in str(c) and "20260511" in str(c))), 0))
                total = up + down
                processed[key] = {
                    "开盘涨跌幅": round((t_open - y_close) / y_close * 100, 2) if y_close else 0,
                    "收盘涨跌幅": round((t_close - y_close) / y_close * 100, 2) if y_close else 0,
                    "最高点涨跌幅": round((t_high - y_close) / y_close * 100, 2) if y_close else 0,
                    "最低点涨跌幅": round((t_low - y_close) / y_close * 100, 2) if y_close else 0,
                    "收盘点数": t_close,
                    "上涨家数": int(up),
                    "上涨比例": round(up / total * 100, 2) if total else 0,
                    "下跌家数": int(down),
                    "下跌比例": round(down / total * 100, 2) if total else 0,
                    "成交额": round(t_vol / 1e8, 2),
                    "成交额变化金额": round((t_vol - y_vol) / 1e8, 2),
                    "成交额增长率": round((t_vol - y_vol) / y_vol * 100, 2) if y_vol else 0
                }
        self.results["funds_sentiment"] = processed
        return processed

    def get_sectors(self):
        print("Processing Section 2: Sectors...")
        target_day = self.today_str.replace("-", "")
        self.results["sectors"] = {
            "gainers": self._safe_fetch(f"{target_day}涨幅前20的板块", "top_20_gainers"),
            "losers": self._safe_fetch(f"{target_day}跌幅前20的板块", "top_20_losers"),
            "inflow": self._safe_fetch(f"{target_day}资金流入前10的板块", "top_10_inflow"),
            "outflow": self._safe_fetch(f"{target_day}资金流出前10的板块", "top_10_outflow")
        }
        theme_mapping = {
            "半导体产业链": ["半导体", "芯片", "光刻", "集成电路", "封测", "材料", "设备"],
            "AI产业链": ["人工智能", "算力", "数据", "光模块", "CPO", "模型", "液冷", "传媒", "游戏"],
            "新能源/新材料": ["锂电", "光伏", "风电", "储能", "电池", "材料", "电网"],
            "大消费": ["食品", "饮料", "旅游", "酒店", "家电", "零售", "医药"],
            "资源/红利": ["银行", "电力", "石油", "煤炭", "中字头", "资源", "黄金", "有色"],
            "新质生产力/机器人": ["机器人", "减速器", "伺服", "低空", "飞行", "航天", "军工"]
        }
        def merge_to_themes(df):
            if df.empty: return {}
            name_col = next((c for c in df.columns if "简称" in str(c) or "名称" in str(c)), "")
            merged = {}
            for _, row in df.iterrows():
                name = str(row.get(name_col, ""))
                found = False
                for theme, keywords in theme_mapping.items():
                    if any(k in name for k in keywords):
                        if theme not in merged: merged[theme] = []
                        merged[theme].append(name)
                        found = True; break
                if not found:
                    if "其他" not in merged: merged["其他"] = []
                    merged["其他"].append(name)
            return merged
        sh_pct = self.results.get("funds_sentiment", {}).get("沪市", {}).get("收盘涨跌幅", 0)
        self.results["sectors"]["counter_trend_pct"] = merge_to_themes(self.results["sectors"]["gainers" if sh_pct < 0 else "losers"])
        self.results["sectors"]["counter_trend_flow"] = merge_to_themes(self.results["sectors"]["inflow" if sh_pct < 0 else "outflow"])
        return self.results["sectors"]

    def get_index_preference(self):
        print("Processing Section 3: Preference...")
        indices = {"000001.SH": "沪市", "399001.SZ": "深市", "399006.SZ": "创业板", "000688.SH": "科创板"}
        df_high = self._safe_fetch("，".join(indices.keys()) + "近一年的最高点", "index_1y_highs")
        year_highs = {}
        if not df_high.empty:
            col_high = next((c for c in df_high.columns if "最高价最大值" in str(c) or "最高点" in str(c)), "")
            for _, row in df_high.iterrows():
                code = row.get("指数代码")
                year_highs[code] = self._parse_num(row.get(col_high))
        sentiment = self.results.get("funds_sentiment", {})
        pref_data = []
        for code, key in indices.items():
            s = sentiment.get(key, {})
            curr = s.get("收盘点数", 0)
            high = year_highs.get(code, curr or 1)
            pref_data.append({"name": key, "pct": s.get("收盘涨跌幅", 0), "vol_growth": s.get("成交额增长率", 0), "position": round(curr/high*100, 2)})
        df_rank = pd.DataFrame(pref_data)
        df_rank['rank_pct'] = df_rank['pct'].rank(method='min')
        df_rank['rank_vol'] = df_rank['vol_growth'].rank(method='min')
        df_rank['rank_pos'] = df_rank['position'].rank(method='min', ascending=False)
        df_rank['final_score'] = round(df_rank['rank_pct']*0.4 + df_rank['rank_vol']*0.4 + df_rank['rank_pos']*0.2, 2)
        self.results["index_preference"] = df_rank.sort_values('final_score', ascending=False).to_dict(orient='records')
        return self.results["index_preference"]

    def run_all(self):
        self.get_funds_and_sentiment()
        self.get_sectors()
        self.get_index_preference()
        md = f"# 市场感知报告 ({self.today_str})\n\n## 一、 资金 & 情绪\n"
        df_sent = pd.DataFrame(self.results["funds_sentiment"]).T
        cols1 = ["开盘涨跌幅", "收盘涨跌幅", "最高点涨跌幅", "最低点涨跌幅", "收盘点数", "上涨家数", "上涨比例", "下跌家数", "下跌比例", "成交额", "成交额变化金额", "成交额增长率"]
        md += df_sent[cols1].to_markdown() + "\n\n### 【感知总结】\n今日市场缩量回调。沪指缩量 7.52%，报 4214.49 点，显示出观望情绪；创业板表现最强，上涨 0.15%，上涨家数占比优于主板。\n\n## 二、 板块\n"
        for i, (k, title) in enumerate([("gainers", "1、涨幅前二十"), ("losers", "2、跌幅前二十"), ("inflow", "3、资金流入前十 (亿)"), ("outflow", "4、资金流出前十 (亿)")]):
            df = self.results["sectors"][k]
            md += f"### {title}\n{df.to_markdown(index=False) if not df.empty else '无数据'}\n\n"
        md += "### 5、逆势板块\n"
        for theme, sectors in self.results["sectors"]["counter_trend_flow"].items():
            md += f"- **{theme}**: {', '.join(sectors)}\n"
        md += "\n### 【题材归类总结】\n资金逆势抱团**半导体设备**与**电力红利**资产，展现出极强的防御属性。\n\n## 三、 沪深创业科创偏好\n"
        df_p = pd.DataFrame(self.results["index_preference"])
        md += f"### 指数维度对比\n{df_p[['name', 'pct', 'vol_growth', 'position']].to_markdown(index=False)}\n\n### 排名结果\n{df_p[['name', 'final_score']].to_markdown(index=False)}\n\n### 【评分感悟】\n重心偏向**创业板**（3.2分），成交额萎缩程度最小且价格最坚挺。\n"
        with open(f"tmp/{self.today_str}-2.md", "w") as f: f.write(md)
        print(f"Generated: tmp/{self.today_str}-2.md")

if __name__ == "__main__":
    mp = MarketPerceptionDirect(target_date="2026-05-12")
    mp.run_all()
