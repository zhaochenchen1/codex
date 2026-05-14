# 数据库设计与变动记录 (SQL Maintenance)

本项目使用 MySQL 存储每日市场快照数据，用于实现增量推送及周期性复盘分析。

## [2026-05-11 14:40] 表结构优化：单行日期模式 (Flattened JSON)

根据需求，将 1 对多的关系简化为单表单行模式，每次抓取的数据以 JSON 格式存储于对应时间点的字段中。

### 市场每日快照表 (daily_market_snapshots)

```sql
CREATE TABLE `daily_market_snapshots` (
    `trade_date` DATE PRIMARY KEY COMMENT '交易日期',
    `data_1030` LONGTEXT COMMENT '10:30 抓取的全量 JSON 数据 (包含板块、资金、龙头股)',
    `data_1130` LONGTEXT COMMENT '11:30 抓取的全量 JSON 数据',
    `data_1430` LONGTEXT COMMENT '14:30 抓取的全量 JSON 数据',
    `daily_summary` TEXT COMMENT '当日异动总结/轮动分析结果',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日市场分时数据存根';
```

---
*优点：查询特定日期的完整对比路径极快；无需复杂的 Join；Python 处理 JSON 数据非常灵活。*

---
*注：后续表结构变更（如增加字段、索引）请在此文档下方以 ## [日期] 格式追加记录。*
