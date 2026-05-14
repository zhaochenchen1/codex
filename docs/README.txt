# Iwencai SkillHub 技能使用手册

本项目已安装以下 Iwencai SkillHub 技能，所有技能均通过同花顺问财 OpenAPI 获取数据。

## 通用环境配置
所有技能均依赖以下环境变量：
- `IWENCAI_BASE_URL`: https://openapi.iwencai.com
- `IWENCAI_API_KEY`: (已配置在 ~/.zshrc)

---

## 已安装技能列表

### 1. hithink-management-query (股东股本查询)
*   **用途**：查询公司的股本结构、股东人数、前十大股东、实控人、股权质押及高管信息。
*   **使用方法**：
    ```bash
    python3 skills/hithink-management-query/scripts/cli.py --query "查询问句"
    ```
*   **示例**：
    ```bash
    python3 skills/hithink-management-query/scripts/cli.py --query "宝馨科技的前十大股东"
    ```

### 2. hithink-market-query (行情数据查询)
*   **用途**：获取股票、ETF、指数的实时价格、涨跌幅、成交量、资金流向及技术指标等。
*   **使用方法**：
    ```bash
    python3 skills/hithink-market-query/scripts/cli.py --query "查询问句"
    ```
*   **示例**：
    ```bash
    python3 skills/hithink-market-query/scripts/cli.py --query "今日主力净流入前十的股票"
    ```

### 3. hithink-zhishu-query (指数数据查询)
*   **用途**：查询各类指数（如沪深300、创业板指、纳指等）的行情、点位和涨跌情况。
*   **使用方法**：
    ```bash
    python3 skills/hithink-zhishu-query/scripts/cli.py --query "查询问句"
    ```
*   **示例**：
    ```bash
    python3 skills/hithink-zhishu-query/scripts/cli.py --query "沪深300指数今天的表现"
    ```

### 4. 市场情绪偏离分析 (逆向投资分析)
*   **用途**：识别被市场“错杀”的超跌绩优股，寻找基本面稳健但情绪过冷的投资机会。
*   **使用方法**：
    ```bash
    python3 "skills/市场情绪偏离分析/scripts/cli.py" --query "查询问句"
    ```
*   **示例**：
    ```bash
    python3 "skills/市场情绪偏离分析/scripts/cli.py" --query "半导体行业中被错杀的绩优股"
    ```

---
*注：新增技能时，请按上述格式在此文档末尾追加说明。*
