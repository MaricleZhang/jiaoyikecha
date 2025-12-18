# 期货公司持仓数据爬虫

获取乾坤期货、摩根大通、国泰君安、中信期货的持仓数据并生成可视化HTML报告。

## 安装

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用方法

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行爬虫
python3 broker_position_scraper.py
```

## 操作步骤

1. 运行脚本后会自动打开浏览器
2. 在浏览器中登录交易可查账号
3. 登录成功后回到终端按 Enter 键
4. 等待数据获取完成，自动生成HTML报告

## 输出文件

| 文件 | 说明 |
|------|------|
| `broker_positions_raw.xlsx` | 原始数据 |
| `broker_positions_cleaned.xlsx` | 清理后数据 |
| `broker_positions_report.html` | 可视化报告 |

## 目标席位

- 乾坤期货
- 摩根大通
- 国泰君安
- 中信期货

## 报告内容

- 各席位持仓品种统计
- 净多/净空品种对比
- 各品种持仓明细（持仓量、持仓变化）

## 注意事项

1. 需要登录交易可查账号才能获取完整数据
2. 数据仅供学习研究使用
