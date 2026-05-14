import os
import schedule
import time
from datetime import datetime
from code.longtou.logger import setup_logger
from code.longtou.db_manager import DBManager
from code.longtou.wencai_client import WencaiClient
from code.longtou.analyzer import MarketAnalyzer
from code.longtou.notifier import DingTalkNotifier

logger = setup_logger(__name__)

class LongtouMonitor:
    def __init__(self):
        self.db = DBManager()
        self.wc = WencaiClient()
        self.notifier = DingTalkNotifier()
        self.analyzer = MarketAnalyzer()

    def run_task(self, time_slot):
        """核心任务流程"""
        logger.info(f"开始执行 {time_slot} 定时任务...")
        trade_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 1. 抓取数据
            sectors = self.wc.fetch_sectors()
            leaders = self.wc.fetch_leaders()
            current_data = {
                'sectors': sectors,
                'leaders': leaders
            }
            
            # 2. 保存快照
            self.db.save_snapshot(trade_date, time_slot, current_data)
            
            # 3. 获取今日历史快照进行对比
            all_snapshots = self.db.get_today_snapshots(trade_date)
            
            # 4. 执行分析与构建推送内容
            if time_slot == "10:30":
                self._push_full_report(trade_date, time_slot, sectors, leaders)
            else:
                # 获取 10:30 的数据作为基准
                base_data = all_snapshots.get('data_1030')
                if base_data:
                    diff_sectors = self.analyzer.diff_sectors(sectors, base_data['sectors'])
                    new_leaders = self.analyzer.diff_leaders(leaders, base_data['leaders'])
                    self._push_incremental_report(trade_date, time_slot, diff_sectors, new_leaders)
                else:
                    self._push_full_report(trade_date, time_slot, sectors, leaders)
                    
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)

    def _push_full_report(self, date, time_slot, sectors, leaders):
        """首次全量推送"""
        md = f"### 🐉 A股板块龙头全量报告 ({time_slot})\n"
        md += f"**日期**: {date}\n\n"
        
        md += "#### 📊 领涨板块 Top 10\n"
        for i, s in enumerate(sectors[:10], 1):
            md += f"{i}. **{s['name']}** | 涨幅: {s['pct_chg']}% | 资金: {s.get('capital_inflow', 0)/10**8:.2f}亿\n"
            
        md += "\n#### 🚀 跨板块核心龙头\n"
        for l in leaders[:5]:
            md += f"- **{l['name']}** ({l['code']}) | {l['limit_up_days']}连板 | 跨{l['cross_sector_count']}个板块\n"
            
        self.notifier.send_report(f"市场全量报告-{time_slot}", md)

    def _push_incremental_report(self, date, time_slot, diff_sectors, new_leaders):
        """后续增量推送"""
        if not diff_sectors and not new_leaders:
            logger.info("无显著异动，跳过推送")
            return
            
        md = f"### ⚡ 市场异动增量报告 ({time_slot})\n"
        md += f"对比 10:30 基准，市场发生以下显著变化：\n\n"
        
        if diff_sectors:
            md += "#### 📈 异动拉升板块\n"
            for s in diff_sectors:
                reason = self.wc.fetch_sector_reason(s['name'])
                rank_str = f"新进前20" if s['rank_up'] == 99 else f"排名上升 {s['rank_up']} 位"
                md += f"- **{s['name']}** ({rank_str})\n"
                md += f"  - ⚡ 涨幅: {s['pct_chg']}% | 资金流入: {s['capital_inflow']/10**8:.2f}亿\n"
                md += f"  - 📝 **异动原因**: {reason}\n\n"
                
        if new_leaders:
            md += "#### 🆕 新确认跨板块龙头\n"
            for l in new_leaders:
                md += f"- **{l['name']}** ({l['code']}) | {l['limit_up_days']}连板 | 跨{l['cross_sector_count']}概念: {','.join(l['sectors'][:3])}\n"
                
        self.notifier.send_report(f"市场异动预警-{time_slot}", md)

def main():
    monitor = LongtouMonitor()
    
    # 设定定时任务
    schedule.every().day.at("10:30").do(monitor.run_task, "10:30")
    schedule.every().day.at("11:30").do(monitor.run_task, "11:30")
    schedule.every().day.at("14:30").do(monitor.run_task, "14:30")
    
    # 模拟首次执行测试
    if os.environ.get('TEST_MODE') == 'true':
        monitor.run_task("10:30")
        time.sleep(2)
        monitor.run_task("11:30") # 模拟第二次执行看增量
        return

    logger.info("龙头发掘系统已启动...")
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    main()
