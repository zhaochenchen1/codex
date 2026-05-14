import json
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import akshare as ak

# Ensure path awareness
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from wencai_api import WencaiAPI, parse_num
import pywencai

def get_prev_trading_day(date_str: str) -> str:
    """获取指定日期的上一个交易日 (基于 akshare)"""
    try:
        df = ak.tool_trade_date_hist_sina()
        trade_days = df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist()
        if date_str in trade_days:
            idx = trade_days.index(date_str)
            if idx > 0:
                return trade_days[idx-1].replace("-", "")
    except: pass
    d = datetime.strptime(date_str, "%Y-%m-%d")
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5: prev -= timedelta(days=1)
    return prev.strftime("%Y%m%d")

class SentimentSensorBase:
    def __init__(self, target_date: str):
        self.target_date = target_date
        self.target_day_str = target_date.replace("-", "")
        self.prev_day_str = get_prev_trading_day(target_date)
        self.json_path = f"tmp/data_cache/{self.target_date}.json"
        self.indices = {"000001.SH": "sh", "399001.SZ": "sz", "399006.SZ": "cyb", "000688.SH": "kcb"}
        self.idx_names = {"000001.SH": "上证指数", "399001.SZ": "深证成指", "399006.SZ": "创业板指", "000688.SH": "科创50"}

    def _load_json(self) -> Dict:
        if os.path.exists(self.json_path):
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {self.target_date: {"modules": {}}}

    def _save_json(self, data: Dict):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _calculate_metrics(self, t_row: Dict, y_row: Dict) -> Dict:
        def val(d, k): return float(d.get(k, 0))
        t_close, y_close = val(t_row, 'close'), val(y_row, 'close')
        t_open, t_high, t_low = val(t_row, 'open'), val(t_row, 'high'), val(t_row, 'low')
        up, down = val(t_row, 'up'), val(t_row, 'down')
        t_vol, y_vol = val(t_row, 'volume'), val(y_row, 'volume')
        
        total = up + down
        def fmt_pct(v, b):
            if b == 0: return "--"
            p = (v - b) / b * 100
            return f"{p:+.2f}%"

        return {
            "open_pct": fmt_pct(t_open, y_close),
            "close_pct": fmt_pct(t_close, y_close),
            "high_pct": fmt_pct(t_high, y_close),
            "low_pct": fmt_pct(t_low, y_close),
            "close_pt": round(t_close, 2), "up_count": int(up), "down_count": int(down),
            "up_ratio": f"{round(up/total*100, 2)}%" if total else "--",
            "down_ratio": f"{round(down/total*100, 2)}%" if total else "--",
            "volume": round(t_vol/1e8, 2), "vol_chg": round((t_vol-y_vol)/1e8, 2),
            "vol_growth": fmt_pct(t_vol, y_vol)
        }

class SentimentSensorSkillHub(SentimentSensorBase):
    def fetch(self) -> Optional[Dict]:
        print(f"   [SkillHub] 正在请求结构化数据...")
        try:
            api = WencaiAPI()
            q = "，".join(self.idx_names.values()) + f"在{self.target_day_str}的收盘价，昨日收盘价，开盘价，最高价，最低价，上涨家数，下跌家数，成交额，昨日成交额"
            resp = api.query(q)
            if not resp.get("success"): return None
            
            results = {}
            datas = resp.get("datas", [])
            for code, key in self.indices.items():
                name = self.idx_names[code]
                row = next((d for d in datas if name in d.get("指数简称", "") or name in d.get("指数代码", "")), None)
                if not row: continue
                
                def f(r, ks, d): return parse_num(next((r[c] for c in r if any(k in str(c) for k in ks) and (d in str(c) or "昨日" in str(c) or "[" not in str(c))), 0))
                
                t_std = {'open': f(row, ["开盘"], self.target_day_str), 'high': f(row, ["最高"], self.target_day_str), 'low': f(row, ["最低"], self.target_day_str), 'close': f(row, ["收盘"], self.target_day_str), 'volume': f(row, ["成交额"], self.target_day_str), 'up': f(row, ["上涨"], self.target_day_str), 'down': f(row, ["下跌"], self.target_day_str)}
                y_std = {'close': f(row, ["收盘"], "昨日"), 'volume': f(row, ["成交额"], "昨日")}
                results[key] = self._calculate_metrics(t_std, y_std)
            return results
        except Exception as e:
            print(f"      SkillHub 失败: {e}")
            return None

class SentimentSensorDirect(SentimentSensorBase):
    def fetch(self) -> Optional[Dict]:
        print(f"   [Direct] 正在执行爬虫补位 (万亿校准型)...")
        results = {}
        for code, key in self.indices.items():
            name = self.idx_names[code]
            # 强制过滤非指数行
            q = f"指数简称=={name} {self.target_day_str} 收盘价，开盘价，最高价，最低价，成交额"
            res = pywencai.get(query=q, loop=True)
            df = res if isinstance(res, pd.DataFrame) else (pd.DataFrame([res]) if isinstance(res, dict) else pd.DataFrame())
            if '股票代码' in df.columns: df = df[df['股票代码'].isna()]
            if df.empty: continue
            row = df.iloc[0].to_dict()

            y_q = f"指数简称=={name} {self.prev_day_str} 收盘价，成交额"
            y_res = pywencai.get(query=y_q, loop=True)
            y_df = y_res if isinstance(y_res, pd.DataFrame) else (pd.DataFrame([y_res]) if isinstance(y_res, dict) else pd.DataFrame())
            if '股票代码' in y_df.columns: y_df = y_df[y_df['股票代码'].isna()]
            y_row = y_df.iloc[0].to_dict() if not y_df.empty else None
            
            def find(r, ks): return parse_num(next((r[c] for c in r if any(k in str(c) for k in ks)), 0))
            t_std = {'open': find(row, ["开盘"]), 'high': find(row, ["最高"]), 'low': find(row, ["最低"]), 'close': find(row, ["收盘"]), 'volume': find(row, ["成交额"]), 'up': 0, 'down': 0}
            y_std = {'close': find(y_row, ["收盘"]) if y_row else t_std['close'], 'volume': find(y_row, ["成交额"]) if y_row else 0}
            results[key] = self._calculate_metrics(t_std, y_std)
        return results

def run_sentiment_module(target_date: str, channel: str = "auto"):
    sensor_sh = SentimentSensorSkillHub(target_date)
    sensor_dr = SentimentSensorDirect(target_date)
    
    full_data = sensor_sh._load_json()
    module_key = "funds_sentiment"
    
    results = None
    if channel == "skillhub":
        results = sensor_sh.fetch()
    elif channel == "direct":
        results = sensor_dr.fetch()
    else:
        results = sensor_sh.fetch()
        if not results or len(results) < 4:
            print("   SkillHub 不足，切换 Direct 补位...")
            results = sensor_dr.fetch()

    if results:
        integrity = "complete" if len(results) >= 4 and all(v.get("volume", 0) > 100 for v in results.values()) else "partial"
        is_post = target_date < datetime.now().strftime("%Y-%m-%d") or datetime.now().strftime("%H:%M") > "15:05"
        
        if target_date not in full_data: full_data[target_date] = {"modules": {}}
        full_data[target_date]["modules"][module_key] = {
            "metadata": {"source": channel, "status": "final" if (is_post and integrity == "complete") else "realtime", "integrity": integrity, "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            "data": results
        }
        sensor_sh._save_json(full_data)
        print(f"   模块 {module_key} 归档完成。")
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--channel", default="auto")
    args = parser.parse_args()
    run_sentiment_module(args.date, args.channel)
