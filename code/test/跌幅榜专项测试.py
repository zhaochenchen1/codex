import json
import os
import sys
import pandas as pd

# 引入 API 基础类
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../fill")))
from wencai_api import WencaiAPI, parse_num

def test_losers_ranking(target_date="2026-05-13"):
    api = WencaiAPI()
    date_str = target_date.replace("-", "")
    
    print(f"=== 跌幅榜专项测试: {target_date} ===")

    test_queries = [
        {"desc": "变体1: 行业板块涨跌幅排名从低到高", "q": f"{date_str} 行业板块涨跌幅排名从低到高"},
        {"desc": "变体2: 行业板块涨幅从小到大排名", "q": f"{date_str} 行业板块涨幅从小到大排名"},
        {"desc": "变体3: 概念板块涨跌幅从小到大排名", "q": f"{date_str} 概念板块涨跌幅从小到大排名"},
    ]

    for item in test_queries:
        print(f"\n[执行] {item['desc']}")
        print(f"输入 Query: {item['q']}")
        
        try:
            resp = api.query(item['q'], limit=20)
            if not resp.get("success") and resp.get("status_code") != 0:
                print(f"API 响应错误: {resp}")
                continue
            
            df = pd.DataFrame(resp.get("datas", []))
            if df.empty:
                print(">>> 结果: 返回数据为空 (可能触发了负值过滤) <<<")
            else:
                print(f">>> 结果: 成功获取 {len(df)} 行数据 <<<")
                print("返回字段:", df.columns.tolist())
                # 提取核心展示字段
                cols = df.columns.tolist()
                name_col = next((c for c in cols if any(kw in str(c) for kw in ["简称", "名称"])), None)
                val_col = next((c for c in cols if "涨跌幅" in str(c)), None)
                
                if name_col and val_col:
                    print(df[[name_col, val_col]].head(10).to_markdown(index=False))
                else:
                    print("无法提取标准列，打印原始前3行:")
                    print(df.head(3).to_string(index=False))

        except Exception as e:
            print(f"异常: {e}")

if __name__ == "__main__":
    test_losers_ranking()
