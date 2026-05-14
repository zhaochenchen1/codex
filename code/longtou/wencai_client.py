import pywencai
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed
from code.longtou.logger import setup_logger

logger = setup_logger(__name__)

class WencaiClient:
    """问财数据抓取类"""
    
    def __init__(self):
        # 核心查询模板
        # 采用“从个股聚合板块”的策略，确保数据获取的稳定性
        self.sector_query = "非ST，非新三板，所属概念，涨跌幅，资金流向"
        self.leader_query = "连续涨停天数>0, 涨跌幅, 换手率, 成交额, 股票简称, 所属概念"
        self.blacklist = {
            '融资融券', '深股通', '沪股通', '标普大盘', 'MSCI', '富时罗素', '转融通', '填权', 
            '昨日涨停', '含可转债', '地方国资改革', '国企改革', '央企国企改革', '壳资源',
            '证金持股', '中央汇金持股', '举牌', '股权转让', '破净股', '创业板重组松绑',
            '近期强势股', '已获批筹', '预盈预增', '送转预期', '小盘股', '中盘股', '大盘股',
            '新股与次新股', '沪证券', '深证券', 'a股', '高送转', '均线空头', '中特估',
            '参股银行', '参股券商', '人工智能', '互联网+', '破净资产', '昨日涨停', '华为概念'
        }

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def fetch_sectors(self):
        """抓取板块排名及资金流向 (通过个股数据聚合)"""
        logger.info("正在抓取个股数据以聚合板块信息...")
        df = pywencai.get(query=self.sector_query, loop=True)
        if df is None or df.empty:
            return []
        
        # 寻找核心列
        col_concept = next((c for c in df.columns if '所属概念' in str(c)), None)
        col_pct = next((c for c in df.columns if '涨跌幅' in str(c)), None)
        col_inflow = next((c for c in df.columns if '资金流向' in str(c) or '净流入' in str(c)), None)
        
        if not col_concept:
            logger.error("未找到 '所属概念' 列")
            return []

        # 展开概念并聚合
        concept_data = []
        for _, row in df.iterrows():
            concepts = str(row[col_concept]).split(';')
            pct = self._parse_num(row.get(col_pct))
            inflow = self._parse_num(row.get(col_inflow))
            
            for cp in concepts:
                cp = cp.strip()
                if cp and cp != 'None' and cp not in self.blacklist:
                    concept_data.append({'name': cp, 'pct': pct, 'inflow': inflow})
        
        if not concept_data:
            return []
            
        # 使用 Pandas 进行聚合
        rdf = pd.DataFrame(concept_data)
        agg_df = rdf.groupby('name').agg({
            'pct': 'mean',
            'inflow': 'sum'
        }).reset_index()
        
        # 重命名并排序
        agg_df.columns = ['name', 'pct_chg', 'capital_inflow']
        agg_df = agg_df.sort_values(by='pct_chg', ascending=False)
        
        # 转换为 List[Dict]
        results = agg_df.head(20).to_dict(orient='records')
        for r in results:
            r['pct_chg'] = round(r['pct_chg'], 2)
        return results

    def _parse_num(self, val):
        """解析问财返回的数值字符串"""
        if val is None or pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).replace('%', '').replace('None', '0').strip()
        try:
            return float(val_str)
        except:
            return 0.0

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def fetch_leaders(self):
        """抓取龙头股及跨板块信息"""
        logger.info("正在抓取龙头股数据...")
        df = pywencai.get(query=self.leader_query, loop=True)
        if df is None or df.empty:
            return []
            
        results = []
        for _, row in df.iterrows():
            concepts = str(row.get('所属同花顺概念', '')).split(';')
            results.append({
                'name': row.get('股票简称', '未知'),
                'code': row.get('股票代码', '未知'),
                'limit_up_days': int(row.get('连续涨停天数', 0) or 0),
                'cross_sector_count': len([c for c in concepts if c.strip()]),
                'sectors': concepts
            })
        
        # 筛选跨板块龙头 (跨 2 个及以上)
        results = [r for r in results if r['cross_sector_count'] >= 2]
        results.sort(key=lambda x: (x['limit_up_days'], x['cross_sector_count']), reverse=True)
        return results[:10]

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(3))
    def fetch_sector_reason(self, sector_name):
        """获取板块异动原因"""
        query = f"{sector_name}今日异动解析"
        logger.info(f"正在查询 {sector_name} 的异动原因...")
        df = pywencai.get(query=query, loop=True)
        if df is None or df.empty:
            return "暂无详细解析"
        
        # 尝试提取解析字段
        reason_col = next((c for c in df.columns if '解析' in str(c) or '原因' in str(c)), None)
        if reason_col:
            return df.iloc[0][reason_col]
        return "基本面支撑及资金博弈"
