import json
import os
import sys
import pandas as pd

# 引入 API 基础类
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../fill")))
from wencai_api import WencaiAPI, parse_num

def test_refined_parsing(target_date="2026-05-13"):
    api = WencaiAPI()
    date_str = target_date.replace("-", "")
    
    print(f"=== 精确解析测试: {target_date} ===")
    
    # 核心问句
    q = f"{date_str} 行业板块涨跌幅排名从低到高"
    print(f"输入 Query: {q}")
    
    try:
        resp = api.query(q, limit=20)
        if not resp.get("success") and resp.get("status_code") != 0:
            print(f"失败: {resp}")
            return
        
        df = pd.DataFrame(resp.get("datas", []))
        if df.empty:
            print("结果: 数据为空")
            return

        cols = df.columns.tolist()
        print(f"API 返回字段清单: {cols}")

        # --- 方案: 日期绑定解析逻辑 ---
        def get_best_val(row, target_day):
            # 1. 优先找带日期的涨跌幅
            target_key = f"涨跌幅[{target_day}]"
            for c in cols:
                if target_key in str(c):
                    val = parse_num(row[c])
                    if val != 0: return val # 优先取非零值

            # 2. 其次找通用涨跌幅
            for c in cols:
                if "涨跌幅" in str(c) and "最新" not in str(c):
                    val = parse_num(row[c])
                    if val != 0: return val
            
            # 3. 最后保底
            for c in cols:
                if "涨跌幅" in str(c):
                    return parse_num(row[c])
            return 0.0

        normalized = []
        name_col = next((c for c in cols if any(kw in str(c) for kw in ["简称", "名称"])), None)
        
        for _, row in df.iterrows():
            name = row[name_col] if name_col else "Unknown"
            val = get_best_val(row, date_str)
            normalized.append({"板块名称": name, "涨跌幅": f"{val:+.2f}%"})

        print("\n[精确解析结果 - 前 20 名]")
        print(pd.DataFrame(normalized).to_markdown(index=True))

    except Exception as e:
        print(f"异常: {e}")

if __name__ == "__main__":
    test_refined_parsing()
