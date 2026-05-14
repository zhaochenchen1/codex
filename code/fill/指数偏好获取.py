import json
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

# Ensure path awareness
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from wencai_api import WencaiAPI, parse_num
import pywencai

class PreferenceScoring:
    """
    传感器模块：指数偏好评分。支持双渠道类解耦与准入红线逻辑。
    """
    def __init__(self, target_date: str):
        self.target_date = target_date
        self.target_day_str = target_date.replace("-", "")
        self.json_path = f"tmp/data_cache/{self.target_date}.json"
        self.api = WencaiAPI()
        self.data = self._load_existing_data()

    def _load_existing_data(self) -> Dict:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {self.target_date: {"modules": {}}}

    def fetch_skillhub(self) -> Optional[Dict]:
        print(f"   [SkillHub] 正在计算评分...")
        return self._calculate()

    def fetch_direct(self) -> Optional[Dict]:
        print(f"   [Direct] 正在计算评分 (通过爬虫补位最高点)...")
        # Direct scoring can still work if high points are found via pywencai
        return self._calculate()

    def _calculate(self) -> Optional[Dict]:
        sentiment_mod = self.data.get(self.target_date, {}).get("modules", {}).get("funds_sentiment", {})
        if sentiment_mod.get("metadata", {}).get("integrity") != "complete":
            print("   熔断: 资金情绪数据不完整。")
            return None
            
        sentiment_data = sentiment_mod.get("data", {})
        indices = {"000001.SH": "sh", "399001.SZ": "sz", "399006.SZ": "cyb", "000688.SH": "kcb"}
        idx_full_names = {"sh": "上证指数", "sz": "深证成指", "cyb": "创业板指", "kcb": "科创50"}
        
        # Fetch 1y High
        q_high = "，".join(idx_full_names.values()) + f"在{self.target_day_str}最近一年的最高点"
        res_high = self.api.query(q_high)
        year_highs = {d.get("指数简称"): parse_num(next((v for k,v in d.items() if "最高" in k), 0)) for d in res_high.get("datas", [])}

        dims = []
        for k, name in {"sh": "沪市", "sz": "深市", "cyb": "创业板", "kcb": "科创板"}.items():
            s = sentiment_data.get(k, {})
            curr_pt = s.get("close_pt", 0)
            high_pt = year_highs.get(idx_full_names[k], curr_pt or 1)
            pos_val = round(curr_pt / high_pt * 100, 2)
            dims.append({
                "name": name, "pct": parse_num(s.get("close_pct", "0%")), 
                "vol_growth": parse_num(s.get("vol_growth", "0%")), "position": pos_val,
                "pct_str": s.get("close_pct"), "vol_growth_str": s.get("vol_growth"), "position_str": f"{pos_val}%"
            })
        
        df = pd.DataFrame(dims)
        df['rank_pct'] = df['pct'].rank(method='min')
        df['rank_vol'] = df['vol_growth'].rank(method='min')
        df['rank_pos'] = df['position'].rank(method='min', ascending=False)
        df['score'] = round(df['rank_pct']*0.4 + df['rank_vol']*0.4 + df['rank_pos']*0.2, 2)
        
        ranking = []
        status_map = {1: "强偏好", 2: "偏好", 3: "中性", 4: "弱偏好"}
        for i, (_, row) in enumerate(df.sort_values('score', ascending=False).iterrows()):
            ranking.append({"rank": i+1, "name": row['name'], "score": row['score'], "status": status_map.get(i+1, "中性")})

        return {"dimensions": dims, "ranking": ranking, "summary": f"当前偏好方向: {ranking[0]['name']}"}

    def _save(self):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

def run_preference_module(target_date: str, channel: str = "auto"):
    ps = PreferenceScoring(target_date)
    module_key = "index_preference"
    
    if ps.data.get(target_date, {}).get("modules", {}).get(module_key, {}).get("metadata", {}).get("status") == "final":
        print(f"-> [模块: {module_key}] 已存在最终数据。")
        return
        
    results = ps.fetch_skillhub()
    if results:
        is_post = target_date < datetime.now().strftime("%Y-%m-%d") or datetime.now().strftime("%H:%M") > "15:05"
        if target_date not in ps.data: ps.data[target_date] = {"modules": {}}
        ps.data[target_date]["modules"][module_key] = {
            "metadata": {"source": "skillhub", "status": "final" if is_post else "realtime", "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            "data": results
        }
        ps._save()
        print(f"   模块 {module_key} 已归档。")
    return results

if __name__ == "__main__":
    run_preference_module("2026-05-11")
