# 交易可查期货数据爬虫

爬取 https://www.jiaoyikecha.com/ 网站的期货品种数据。

## 功能

- 获取期货品种AI观点（看多/震荡/看空）
- 获取资金流向数据
- 获取基本面指标
- 获取市场快讯
- 获取品种、合约、席位信息

## 安装

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行爬虫
python scraper.py
```

## 输出文件

- `futures_data.xlsx` - 期货数据（按类型分sheet）
  - 全部数据
  - AI观点
  - 资金流向
  - 基本面指标
  - 快讯
  - 品种信息
  - 合约信息
  - 席位信息
- `api_raw_data.json` - 原始API响应数据

## 数据说明

### AI观点
| 字段 | 说明 |
|------|------|
| 品种 | 期货品种名称 |
| 代码 | 品种代码 |
| 看多 | 看多观点数量 |
| 震荡 | 震荡观点数量 |
| 看空 | 看空观点数量 |

### 资金流向
| 字段 | 说明 |
|------|------|
| 品种 | 期货品种名称 |
| 净流入(万) | 资金净流入金额（万元） |

### 基本面指标
| 字段 | 说明 |
|------|------|
| 品种 | 期货品种名称 |
| 指标名称 | 指标名称 |
| 数值 | 当前数值 |
| 日期 | 数据日期 |
| 涨跌 | 涨跌幅 |

## 注意事项

1. 该网站使用了动态加载，爬虫使用 Playwright 模拟浏览器访问
2. 部分数据（如详细持仓数据）可能需要登录才能获取
3. 请合理控制爬取频率，避免对服务器造成压力
4. 数据仅供学习研究使用

## 自定义配置

修改 `scraper.py` 中的参数：

```python
# 修改要爬取的品种数量
await scraper.scrape_all(max_varieties=10, days=14)

# 设置为 False 可以看到浏览器操作过程
scraper = FuturesScraper(headless=False)
```

## 支持的期货品种

- 黑色系：螺纹钢(RB)、热卷(HC)、铁矿石(I)、焦炭(J)、焦煤(JM)
- 农产品：豆粕(M)、豆油(Y)、棕榈油(P)、白糖(SR)、棉花(CF)
- 化工品：PTA(TA)、甲醇(MA)
- 有色金属：沪铜(CU)、沪铝(AL)、沪锌(ZN)、沪镍(NI)
- 能源：原油(SC)、燃油(FU)、沥青(BU)
- 其他：橡胶(RU)
