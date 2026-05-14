from code.longtou.logger import setup_logger

logger = setup_logger(__name__)

class MarketAnalyzer:
    """增量异动分析引擎"""
    
    @staticmethod
    def diff_sectors(current_sectors, base_sectors):
        """对比两个时间点的板块变化"""
        if not base_sectors:
            return []
            
        base_map = {s['name']: i for i, s in enumerate(base_sectors)}
        diff_results = []
        
        for i, curr in enumerate(current_sectors):
            name = curr['name']
            if name in base_map:
                prev_rank = base_map[name]
                rank_up = prev_rank - i
                # 如果排名上升超过 2 位，或者涨幅斜率很大
                if rank_up >= 2:
                    diff_results.append({
                        'name': name,
                        'rank_up': rank_up,
                        'pct_chg': curr['pct_chg'],
                        'capital_inflow': curr.get('capital_inflow', 0)
                    })
            else:
                # 新进前 20 的板块
                diff_results.append({
                    'name': name,
                    'rank_up': 99,  # 标记为新进
                    'pct_chg': curr['pct_chg'],
                    'capital_inflow': curr.get('capital_inflow', 0)
                })
                
        # 仅返回异动最剧烈的前 5 个
        diff_results.sort(key=lambda x: x['rank_up'], reverse=True)
        return diff_results[:5]

    @staticmethod
    def diff_leaders(current_leaders, base_leaders):
        """对比龙头股变化"""
        if not base_leaders:
            return current_leaders
            
        base_codes = {l['code'] for l in base_leaders}
        new_leaders = [l for l in current_leaders if l['code'] not in base_codes]
        return new_leaders
