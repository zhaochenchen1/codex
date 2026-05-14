import os
import sys
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from wencai_api import WencaiAPI, parse_num

class MarketPerception:
    def __init__(self):
        self.api = WencaiAPI()
        self.results = {}

    def get_funds_and_sentiment(self):
        """
        Segment 1: Funds & Sentiment
        Retrieves data for Shanghai, Shenzhen, ChiNext, and STAR Market indices.
        """
        print("Processing Section 1: Funds & Sentiment...")
        indices = {
            "沪市": "上证指数",
            "深市": "深证成指",
            "创业板": "创业板指",
            "科创板": "科创50"
        }
        
        # Combined query to save tokens/calls
        query_str = "，".join(indices.values()) + "今日的收盘价，昨日收盘价，今日最高价，今日最低价，今日开盘价，上涨家数，下跌家数，今日成交额，昨日成交额"
        resp = self.api.query(query_str)
        
        # Check for success (either success=True or status_code=0)
        is_success = resp.get("success") or resp.get("status_code") == 0
        if not is_success:
            print(f"Error fetching index data: {resp}")
            return
        
        datas = resp.get("datas", [])
        processed_data = {}
        
        for name_key, index_name in indices.items():
            # Find the record for this index
            record = next((d for d in datas if d.get("指数简称") == index_name or index_name in d.get("指数简称", "")), None)
            if not record:
                print(f"Warning: Could not find data for {index_name}")
                continue
            
            keys = list(record.keys())
            date_keys = sorted(list(set([k.split("[")[1].split("]")[0] for k in keys if "[" in k and "]" in k])), reverse=True)
            t_day = date_keys[0] if date_keys else ""
            y_day = date_keys[1] if len(date_keys) > 1 else ""
            
            # Use fallback for today if no date keys found (though they should be there)
            t_close = parse_num(record.get(f"收盘价[{t_day}]") if t_day else record.get("最新价"))
            y_close = parse_num(record.get(f"收盘价[{y_day}]") if y_day else record.get("昨日收盘价"))
            t_high = parse_num(record.get(f"最高价[{t_day}]"))
            t_low = parse_num(record.get(f"最低价[{t_day}]"))
            t_open = parse_num(record.get(f"开盘价[{t_day}]"))
            
            up_count = parse_num(record.get(f"上涨家数[{t_day}]"))
            down_count = parse_num(record.get(f"下跌家数[{t_day}]"))
            total_count = up_count + down_count
            
            t_volume = parse_num(record.get(f"成交额[{t_day}]"))
            y_volume = parse_num(record.get(f"成交额[{y_day}]"))
            
            # Calculations
            metrics = {
                "收盘点数": t_close,
                "开盘涨跌幅": round((t_open - y_close) / y_close * 100, 2) if y_close else 0,
                "收盘涨跌幅": round((t_close - y_close) / y_close * 100, 2) if y_close else 0,
                "最高点涨跌幅": round((t_high - y_close) / y_close * 100, 2) if y_close else 0,
                "最低点涨跌幅": round((t_low - y_close) / y_close * 100, 2) if y_close else 0,
                "上涨家数": int(up_count),
                "下跌家数": int(down_count),
                "上涨比例": round(up_count / total_count * 100, 2) if total_count else 0,
                "下跌比例": round(down_count / total_count * 100, 2) if total_count else 0,
                "成交额": t_volume,
                "昨日成交额": y_volume,
                "成交额变化金额": t_volume - y_volume,
                "成交额增长率": round((t_volume - y_volume) / y_volume * 100, 2) if y_volume else 0
            }
            processed_data[name_key] = metrics
            
        self.results["funds_sentiment"] = processed_data
        return processed_data

    def get_sectors(self):
        """
        Segment 2: Sectors
        Retrieves top 20 gainers/losers, top 10 inflow/outflow, and counter-trend sectors.
        """
        print("Processing Section 2: Sectors...")
        
        # 1. Gainers
        resp_gain = self.api.query("今日涨幅前二十的板块，板块涨跌幅", limit=20)
        gainers = []
        if resp_gain.get("status_code") == 0 or resp_gain.get("success"):
            for d in resp_gain.get("datas", []):
                gainers.append({
                    "name": d.get("指数简称"),
                    "pct": parse_num(d.get("最新涨跌幅:前复权") or next((v for k,v in d.items() if "涨跌幅" in k), 0))
                })
        
        # 2. Losers
        resp_loss = self.api.query("今日跌幅前二十的板块，板块涨跌幅", limit=20)
        losers = []
        if resp_loss.get("status_code") == 0 or resp_loss.get("success"):
            for d in resp_loss.get("datas", []):
                losers.append({
                    "name": d.get("指数简称"),
                    "pct": parse_num(d.get("最新涨跌幅:前复权") or next((v for k,v in d.items() if "涨跌幅" in k), 0))
                })

        # 3. Inflow
        resp_inflow = self.api.query("行业板块，今日资金流向，资金净流入额从高到低排名前10", limit=10)
        inflow = []
        if resp_inflow.get("status_code") == 0 or resp_inflow.get("success"):
            for d in resp_inflow.get("datas", []):
                inflow.append({
                    "name": d.get("指数简称"),
                    "amount": parse_num(next((v for k,v in d.items() if "资金净流入" in k or "资金流入" in k), 0)) / 100000000.0 # to 亿
                })

        # 4. Outflow
        resp_outflow = self.api.query("行业板块，今日资金流向，资金净流入额从低到高排名前10", limit=10)
        outflow = []
        if resp_outflow.get("status_code") == 0 or resp_outflow.get("success"):
            for d in resp_outflow.get("datas", []):
                outflow.append({
                    "name": d.get("指数简称"),
                    "amount": parse_num(next((v for k,v in d.items() if "资金净流入" in k or "资金流入" in k), 0)) / 100000000.0 # to 亿
                })
        
        # 5. Counter-trend
        sh_pct = self.results.get("funds_sentiment", {}).get("沪市", {}).get("收盘涨跌幅", 0)
        
        if sh_pct >= 0:
            pct_target = losers
            flow_target = outflow
        else:
            pct_target = gainers
            flow_target = inflow
            
        theme_mapping = {
            "半导体产业链": ["半导体", "芯片", "光刻", "集成电路", "封测", "材料", "设备"],
            "AI产业链": ["人工智能", "算力", "数据", "光模块", "CPO", "模型", "液冷", "传媒", "游戏"],
            "新能源/新材料": ["锂电", "光伏", "风电", "储能", "电池", "材料", "电网"],
            "大消费": ["食品", "饮料", "旅游", "酒店", "家电", "零售", "医药"],
            "资源/红利": ["银行", "电力", "石油", "煤炭", "中字头", "资源", "黄金", "有色"],
            "新质生产力/机器人": ["机器人", "减速器", "伺服", "低空", "飞行", "航天", "军工"]
        }
        
        def merge_to_themes(sector_list):
            merged = {}
            for sector in sector_list:
                name = sector["name"]
                found_theme = False
                for theme, keywords in theme_mapping.items():
                    if any(k in name for k in keywords):
                        if theme not in merged: merged[theme] = []
                        merged[theme].append(name)
                        found_theme = True
                        break
                if not found_theme:
                    if "其他" not in merged: merged["其他"] = []
                    merged["其他"].append(name)
            return merged

        self.results["sectors"] = {
            "gainers": gainers,
            "losers": losers,
            "inflow": inflow,
            "outflow": outflow,
            "counter_trend_pct": merge_to_themes(pct_target),
            "counter_trend_flow": merge_to_themes(flow_target)
        }
        return self.results["sectors"]

    def get_index_preference(self):
        """
        Segment 3: Index Preference
        Ranks indices based on weighted score.
        """
        print("Processing Section 3: Index Preference...")
        
        # 1. Fetch 1-year high
        indices = {
            "沪市": "上证指数",
            "深市": "深证成指",
            "创业板": "创业板指",
            "科创板": "科创50"
        }
        query_str = "，".join(indices.values()) + "近一年的最高点"
        resp = self.api.query(query_str)
        
        year_highs = {}
        if resp.get("status_code") == 0 or resp.get("success"):
            for d in resp.get("datas", []):
                name = d.get("指数简称")
                high = parse_num(next((v for k,v in d.items() if "最高价最大值" in k or "最高点" in k), 0))
                # Map back to my keys
                key = next((k for k, v in indices.items() if v == name or v in name), None)
                if key:
                    year_highs[key] = high
                    
        # 2. Combine with previous data
        sentiment = self.results.get("funds_sentiment", {})
        pref_data = []
        for key in indices.keys():
            s = sentiment.get(key, {})
            high = year_highs.get(key, 0)
            curr = s.get("收盘点数", 0)
            pos = (curr / high * 100) if high else 0
            pref_data.append({
                "name": key,
                "pct": s.get("收盘涨跌幅", 0),
                "vol_growth": s.get("成交额增长率", 0),
                "position": pos
            })
            
        # 3. Ranking
        df = pd.DataFrame(pref_data)
        # Use rank(ascending=True) so larger values get larger ranks (1 to 4)
        df['rank_pct'] = df['pct'].rank(method='min')
        df['rank_vol'] = df['vol_growth'].rank(method='min')
        # Position: lower is better (ascending=False in rank means lower value gets higher rank)
        df['rank_pos'] = df['position'].rank(method='min', ascending=False)
        
        df['final_score'] = df['rank_pct'] * 0.4 + df['rank_vol'] * 0.4 + df['rank_pos'] * 0.2
        df = df.sort_values(by='final_score', ascending=False)
        
        self.results["index_preference"] = df.to_dict(orient='records')
        return self.results["index_preference"]

    def get_price_preference(self):
        """
        Segment 4: Price Preference
        Retrieves advancing/declining counts for different price buckets.
        """
        print("Processing Section 4: Price Preference...")
        buckets = [
            (0, 10), (10, 100), (100, 300), (300, 500), (500, 2000)
        ]
        
        results = []
        # Non-ST
        for low, high in buckets:
            query = f"非ST，股价在{low}到{high}元之间，今日上涨家数，今日下跌家数"
            resp = self.api.query(query)
            if resp.get("status_code") == 0 or resp.get("success"):
                data = resp.get("datas", [{}])[0]
                up = parse_num(next((v for k,v in data.items() if "上涨" in k), 0))
                down = parse_num(next((v for k,v in data.items() if "下跌" in k), 0))
                total = up + down
                results.append({
                    "type": "非ST",
                    "bucket": f"({low}, {high}]",
                    "up": int(up),
                    "down": int(down),
                    "up_ratio": round(up / total * 100, 2) if total else 0,
                    "down_ratio": round(down / total * 100, 2) if total else 0
                })
        
        # ST
        query = "ST股，今日上涨家数，今日下跌家数"
        resp = self.api.query(query)
        if resp.get("status_code") == 0 or resp.get("success"):
            data = resp.get("datas", [{}])[0]
            up = parse_num(next((v for k,v in data.items() if "上涨" in k), 0))
            down = parse_num(next((v for k,v in data.items() if "下跌" in k), 0))
            total = up + down
            results.append({
                "type": "ST",
                "bucket": "All",
                "up": int(up),
                "down": int(down),
                "up_ratio": round(up / total * 100, 2) if total else 0,
                "down_ratio": round(down / total * 100, 2) if total else 0
            })
            
        self.results["price_preference"] = results
        return results

    def get_market_cap_preference(self):
        """
        Segment 5: Market Cap Preference
        Retrieves advancing/declining counts for different market cap buckets.
        """
        print("Processing Section 5: Market Cap Preference...")
        buckets = [
            (0, 10), (10, 50), (50, 100), (100, 300), (300, 1000), (1000, 100000)
        ]
        
        results = []
        for low, high in buckets:
            query = f"总市值在{low}到{high}亿之间，今日上涨股票数量，今日下跌股票数量"
            resp = self.api.query(query)
            if resp.get("status_code") == 0 or resp.get("success"):
                data = resp.get("datas", [{}])[0]
                up = parse_num(next((v for k,v in data.items() if "上涨" in k), 0))
                down = parse_num(next((v for k,v in data.items() if "下跌" in k), 0))
                total = up + down
                results.append({
                    "bucket": f"({low}, {high}] 亿",
                    "up": int(up),
                    "down": int(down),
                    "up_ratio": round(up / total * 100, 2) if total else 0,
                    "down_ratio": round(down / total * 100, 2) if total else 0
                })
            
        self.results["market_cap_preference"] = results
        return results

    def run_all(self):
        self.get_funds_and_sentiment()
        self.get_sectors()
        self.get_index_preference()
        self.get_price_preference()
        self.get_market_cap_preference()
        
        print("\n" + "="*50)
        print("MARKET PERCEPTION REPORT")
        print("="*50)
        
        print("\nSection 1: Funds & Sentiment")
        cols = ["收盘点数", "收盘涨跌幅", "成交额", "昨日成交额", "成交额增长率", "上涨比例"]
        print(pd.DataFrame(self.results["funds_sentiment"]).T[cols])
        
        print("\nSection 2: Sectors Analysis")
        print("--- Top Gainers ---")
        print(pd.DataFrame(self.results["sectors"]["gainers"]).head(10))
        print("--- Top Inflow (亿) ---")
        print(pd.DataFrame(self.results["sectors"]["inflow"]).head(10))
        
        print("\n--- Counter-trend Themes (Price) ---")
        for theme, sectors in self.results["sectors"]["counter_trend_pct"].items():
            print(f"- {theme}: {', '.join(sectors)}")
            
        print("\n--- Counter-trend Themes (Flow) ---")
        for theme, sectors in self.results["sectors"]["counter_trend_flow"].items():
            print(f"- {theme}: {', '.join(sectors)}")
            
        print("\nSection 3: Index Preference")
        pref_df = pd.DataFrame(self.results["index_preference"])[['name', 'pct', 'vol_growth', 'position', 'final_score']]
        print(pref_df.to_string(index=False))
        
        print("\nSection 4: Price Preference")
        print(pd.DataFrame(self.results["price_preference"]).to_string(index=False))
        
        print("\nSection 5: Market Cap Preference")
        print(pd.DataFrame(self.results["market_cap_preference"]).to_string(index=False))

if __name__ == "__main__":
    mp = MarketPerception()
    mp.run_all()
