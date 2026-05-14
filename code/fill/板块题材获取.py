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

class SectorAcquisition:
    """
    传感器模块：板块题材。应用强约束问句与日期绑定解析策略。
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
        print(f"   [SkillHub] 正在执行日期绑定式板块采集...")
        d_str = self.target_day_str
        
        # 严格按照规范 2.1
        queries = {
            "gainers": f"{d_str} 概念板块涨幅前20",
            "losers": f"{d_str} 行业板块涨跌幅排名从低到高",
            "inflow": f"{d_str} 行业板块资金流入前10",
            "outflow": f"{d_str} 行业板块资金流出前10"
        }
        
        raw_res = {}
        for k, q in queries.items():
            try:
                resp = self.api.query(q, limit=20)
                if resp.get("success") or resp.get("status_code") == 0:
                    raw_res[k] = pd.DataFrame(resp.get("datas", []))
            except: pass
        return self._process_raw(raw_res)

    def fetch_direct(self) -> Optional[Dict]:
        print(f"   [Direct] 正在执行日期绑定式板块采集...")
        d_str = self.target_day_str
        
        queries = {
            "gainers": f"{d_str} 概念板块涨幅前20",
            "losers": f"{d_str} 行业板块涨跌幅排名从低到高",
            "inflow": f"{d_str} 行业板块资金流入前10",
            "outflow": f"{d_str} 行业板块资金流出前10"
        }
        
        raw_res = {}
        for k, q in queries.items():
            try:
                res_dir = pywencai.get(query=q, loop=True)
                if isinstance(res_dir, pd.DataFrame):
                    raw_res[k] = res_dir
                elif isinstance(res_dir, dict):
                    raw_res[k] = pd.DataFrame([res_dir])
            except: pass
        return self._process_raw(raw_res)

    def _process_raw(self, raw_res: Dict[str, pd.DataFrame]) -> Dict:
        processed = {}
        for k in ["gainers", "losers", "inflow", "outflow"]:
            df = raw_res.get(k, pd.DataFrame())
            processed[k] = self._normalize_df(df, "涨跌幅" if "gain" in k or "loss" in k else "资金")
            
        # 逆势分析逻辑
        sentiment_mod = self.data.get(self.target_date, {}).get("modules", {}).get("funds_sentiment", {})
        sh_pct = parse_num(sentiment_mod.get("data", {}).get("sh", {}).get("close_pct", "0%"))
        
        target_list = processed["losers"] if sh_pct >= 0 else processed["gainers"]
        processed["counter_trend"] = self._merge_to_themes(target_list)
        return processed

    def _normalize_df(self, df: pd.DataFrame, type_key: str) -> List[Dict]:
        if df.empty: return []
        cols = df.columns.tolist()
        
        name_col = next((c for c in cols if any(kw in str(c) for kw in ["简称", "名称"])), None)
        if not name_col: return []

        normalized = []
        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            val = self._get_best_val(row, cols, type_key)
            
            # 格式化
            if type_key == "涨跌幅":
                val_str = f"{round(val, 2):+}%"
            else:
                val_str = round(val / 1e8, 2)
            
            normalized.append({"name": name, "val": val_str})
        return normalized

    def _get_best_val(self, row: pd.Series, cols: List[str], type_key: str) -> float:
        """
        日期绑定优先解析策略
        """
        target_day = self.target_day_str
        # 1. 优先找带日期的指标
        for c in cols:
            if target_day in str(c) and type_key in str(c):
                v = parse_num(row[c])
                if v != 0: return v
        # 2. 其次找非“最新”的指标
        for c in cols:
            if type_key in str(c) and "最新" not in str(c):
                v = parse_num(row[c])
                if v != 0: return v
        # 3. 最后兜底
        for c in cols:
            if type_key in str(c):
                return parse_num(row[c])
        return 0.0

    def _merge_to_themes(self, sector_list: List[Dict]) -> List[Dict]:
        theme_map = {
            "半导体产业链": ["半导体", "芯片", "光刻", "集成电路", "封测", "材料", "设备"],
            "AI产业链": ["人工智能", "算力", "数据", "光模块", "CPO", "模型", "液冷", "传媒", "游戏"],
            "资源/红利": ["银行", "电力", "石油", "煤炭", "中字头", "资源", "黄金", "有色"],
            "大消费": ["食品", "饮料", "旅游", "零售", "医药", "农", "饲料"]
        }
        themes = {}
        for s in sector_list:
            name = s["name"]
            found = False
            for t, kws in theme_map.items():
                if any(k in name for k in kws):
                    if t not in themes: themes[t] = []
                    themes[t].append(name); found = True; break
            if not found:
                if "其他" not in themes: themes["其他"] = []
                themes["其他"].append(name)
        return [{"theme": k, "list": v} for k, v in themes.items()]

    def _save(self):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

def run_sector_module(target_date: str, channel: str = "auto"):
    sa = SectorAcquisition(target_date)
    module_key = "sectors"
    
    # 历史数据增量修复时，强制重跑
    results = None
    if channel == "skillhub": results = sa.fetch_skillhub()
    elif channel == "direct": results = sa.fetch_direct()
    else:
        results = sa.fetch_skillhub()
        if not results: results = sa.fetch_direct()

    if results:
        is_complete = all(len(results[k]) > 0 for k in ["gainers", "losers", "inflow", "outflow"])
        is_post = target_date < datetime.now().strftime("%Y-%m-%d") or datetime.now().strftime("%H:%M") > "15:05"
        
        if target_date not in sa.data: sa.data[target_date] = {"modules": {}}
        sa.data[target_date]["modules"][module_key] = {
            "metadata": {
                "source": f"{channel}_date_bound", 
                "status": "final" if (is_post and is_complete) else "realtime", 
                "integrity": "complete" if is_complete else "partial", 
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "data": results
        }
        sa._save()
        print(f"   模块 {module_key} 日期绑定解析成功。")
    return results

if __name__ == "__main__":
    run_sector_module("2026-05-13")
