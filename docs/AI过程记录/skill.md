# 已安装技能概览 (Skill Overview)

本项目集成了同花顺问财 (Iwencai) 的多个专业金融分析技能。所有技能均支持自然语言输入，并通过 `scripts/cli.py` 脚本执行。

## 技能列表

| 技能名称 | 核心功能 | 执行脚本路径 |
| :--- | :--- | :--- |
| **hithink-management-query** | 股东股本、实控人、高管信息 | `code/skills/hithink-management-query/scripts/cli.py` |
| **hithink-market-query** | 股票/ETF实时行情、资金流向、技术指标 | `code/skills/hithink-market-query/scripts/cli.py` |
| **hithink-zhishu-query** | 国内外主要指数行情、点位查询 | `code/skills/hithink-zhishu-query/scripts/cli.py` |
| **市场情绪偏离分析** | 逆向投资、超跌反弹、寻找“错杀”机会 | `code/skills/市场情绪偏离分析/scripts/cli.py` |

---

## 详细用法示例

### 1. 股东股本分析
用于查询公司的治理结构和股东变动。
```bash
python3 code/skills/hithink-management-query/scripts/cli.py --query "宝馨科技最新的实际控制人是谁？"
```

### 2. 实时行情与资金
用于监控市场动态和个股实时走势。
```bash
python3 code/skills/hithink-market-query/scripts/cli.py --query "今日主力净买入排名前五的股票"
```

### 3. 指数表现
用于宏观市场观察。
```bash
python3 code/skills/hithink-zhishu-query/scripts/cli.py --query "中证500指数目前的成交量是多少？"
```

### 4. 逆向策略分析
用于挖掘情绪与基本面背离的机会。
```bash
python3 "code/skills/市场情绪偏离分析/scripts/cli.py" --query "寻找电力设备行业中近半年跌幅超过30%的绩优股"
```

---

## 维护与扩展
若要安装新技能，请使用以下命令：
```bash
iwencai-skillhub-cli install <skill-slug>
```
安装后，请记得同步更新 `README.txt` 和本 `skill.md` 文档。
