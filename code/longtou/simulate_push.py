import json
from datetime import datetime
from code.longtou.db_manager import DBManager
from code.longtou.analyzer import MarketAnalyzer
from code.longtou.wencai_client import WencaiClient

def simulate():
    db = DBManager()
    wc = WencaiClient()
    analyzer = MarketAnalyzer()
    trade_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n{'='*20} 模拟推送效果展示 ({trade_date}) {'='*20}\n")
    
    snapshots = db.get_today_snapshots(trade_date)
    if not snapshots:
        print("错误: 数据库中未找到今日快照数据")
        return

    # 1. 模拟 10:30 全量推送
    print(f"--- [10:30 模拟报告] ---")
    d1030 = snapshots.get('data_1030')
    if d1030:
        md = "#### 📊 领涨板块 Top 10\n"
        for i, s in enumerate(d1030['sectors'][:10], 1):
            md += f"{i}. **{s['name']}** | 涨幅: {s['pct_chg']}% | 资金: {s.get('capital_inflow', 0)/10**8:.2f}亿\n"
        md += "\n#### 🚀 跨板块核心龙头\n"
        for l in d1030['leaders'][:5]:
            md += f"- **{l['name']}** ({l['code']}) | {l['limit_up_days']}连板 | 跨{l['cross_sector_count']}个板块\n"
        print(md)
    else:
        print("10:30 数据缺失\n")

    # 2. 模拟 11:30 增量推送
    print(f"\n--- [11:30 模拟异动] ---")
    d1130 = snapshots.get('data_1130')
    if d1130 and d1030:
        diff_sectors = analyzer.diff_sectors(d1130['sectors'], d1030['sectors'])
        new_leaders = analyzer.diff_leaders(d1130['leaders'], d1030['leaders'])
        
        if not diff_sectors and not new_leaders:
            print("对比 10:30，市场无显著异动\n")
        else:
            if diff_sectors:
                print("📈 异动拉升板块:")
                for s in diff_sectors:
                    reason = wc.fetch_sector_reason(s['name'])
                    rank_str = "新进前20" if s['rank_up'] == 99 else f"排名上升 {s['rank_up']} 位"
                    print(f"- **{s['name']}** ({rank_str}) | 涨幅: {s['pct_chg']}% | 原因: {reason}")
            if new_leaders:
                print("\n🆕 新确认跨板块龙头:")
                for l in new_leaders:
                    print(f"- **{l['name']}** ({l['code']}) | {l['limit_up_days']}连板")
    else:
        print("11:30 数据或基准缺失\n")

    # 3. 模拟 14:30 增量推送
    print(f"\n--- [14:30 模拟异动] ---")
    d1430 = snapshots.get('data_1430')
    if d1430 and d1030:
        diff_sectors = analyzer.diff_sectors(d1430['sectors'], d1030['sectors'])
        new_leaders = analyzer.diff_leaders(d1430['leaders'], d1030['leaders'])
        
        if not diff_sectors and not new_leaders:
            print("对比 10:30，午后市场平稳，无显著异动\n")
        else:
            if diff_sectors:
                print("📈 午后突袭/持续走强板块:")
                for s in diff_sectors:
                    reason = wc.fetch_sector_reason(s['name'])
                    rank_str = "新进前20" if s['rank_up'] == 99 else f"排名上升 {s['rank_up']} 位"
                    print(f"- **{s['name']}** ({rank_str}) | 涨幅: {s['pct_chg']}% | 原因: {reason}")
            if new_leaders:
                print("\n🆕 午后确认跨板块龙头:")
                for l in new_leaders:
                    print(f"- **{l['name']}** ({l['code']}) | {l['limit_up_days']}连板")
    else:
        print("14:30 数据或基准缺失\n")

if __name__ == "__main__":
    simulate()
