import json
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

# Path awareness
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from wencai_api import WencaiAPI, parse_num
import pywencai

class MarketCapPreferenceAcquisition:
    """
    传感器模块：市值偏好。支持解耦与标准五列表格化。
    """
    def __init__(self, target_date: str):
        self.target_date = target_date
        self.target_day_str = target_date.replace("-", "")
        self.json_path = f"tmp/data_cache/{self.target_date}.json"
        self.api = WencaiAPI()
        self.data = self._load_existing_data()

    def _load_existing_data(self) -> Dict:
        if os.path.exists(self.json_path):
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {self.target_date: {"modules": {}}}

    def fetch_skillhub(self) -> Optional[Dict]:
        print(f"   [SkillHub] 正在采集市值分布...")
        return self._fetch_all("skillhub")

    def fetch_direct(self) -> Optional[Dict]:
        print(f"   [Direct] 正在采集市值分布...")
        return self._fetch_all("direct")

    def _fetch_all(self, mode: str) -> Optional[Dict]:
        buckets = [(0,10,"b1"),(10,50,"b2"),(50,100,"b3"),(100,300,"b4"),(300,1000,"b5"),(1000,100000,"b6")]
        res = {}
        for low, high, key in buckets:
            q = f"{self.target_day_str}总市值在{low}到{high}亿之间的上涨股票数量，下跌股票数量"
            row = self._fetch_row(q, mode)
            res[key] = self._calculate_ratios(row)
        return res

    def _fetch_row(self, query: str, mode: str) -> Dict:
        if mode == "skillhub":
            r = self.api.query(query)
            return r.get("datas", [{}])[0] if r.get("datas") else {}
        else:
            r = pywencai.get(query=query, loop=True)
            if isinstance(r, pd.DataFrame) and not r.empty: return r.iloc[0].to_dict()
            return r if isinstance(r, dict) else {}

    def _calculate_ratios(self, row: Dict) -> Dict:
        up = parse_num(next((v for k,v in row.items() if "上涨" in k), 0))
        down = parse_num(next((v for k,v in row.items() if "下跌" in k), 0))
        total = up + down
        up_r = round(up / total * 100, 2) if total else 0.0
        return {"up": int(up), "down": int(down), "up_r": f"{up_r:.2f}%", "down_r": f"{(100.0-up_r):.2f}%" if total else "0.00%"}

    def _save(self):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

def run_mcap_module(target_date: str, channel: str = "auto"):
    ma = MarketCapPreferenceAcquisition(target_date)
    module_key = "mcap_preference"
    if ma.data.get(target_date, {}).get("modules", {}).get(module_key, {}).get("metadata", {}).get("status") == "final":
        print(f"-> [模块: {module_key}] 已存在最终数据。")
        return
    
    results = None
    if channel == "skillhub": results = ma.fetch_skillhub()
    elif channel == "direct": results = ma.fetch_direct()
    else:
        results = ma.fetch_skillhub()
        if not results: results = ma.fetch_direct()

    if results:
        is_complete = all(results[k]["up"]+results[k]["down"]>0 for k in results)
        is_post = target_date < datetime.now().strftime("%Y-%m-%d") or datetime.now().strftime("%H:%M") > "15:05"
        if target_date not in ma.data: ma.data[target_date] = {"modules": {}}
        ma.data[target_date]["modules"][module_key] = {
            "metadata": {"source": channel, "status": "final" if (is_post and is_complete) else "realtime", "integrity": "complete" if is_complete else "partial", "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            "data": results
        }
        ma._save()
        print(f"   模块 {module_key} 已归档。")
    return results

if __name__ == "__main__":
    run_mcap_module("2026-05-11")
