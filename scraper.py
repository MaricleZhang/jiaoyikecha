#!/usr/bin/env python3
"""
交易可查期货数据爬虫
爬取不同期货品种过去两周的数据
"""

import asyncio
import json
import zlib
import base64
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from playwright.async_api import async_playwright


class FuturesScraper:
    """期货数据爬虫"""
    
    BASE_URL = "https://www.jiaoyikecha.com"
    
    # 常见期货品种
    VARIETIES = [
        {"name": "螺纹钢", "symbol": "RB"},
        {"name": "热卷", "symbol": "HC"},
        {"name": "铁矿石", "symbol": "I"},
        {"name": "焦炭", "symbol": "J"},
        {"name": "焦煤", "symbol": "JM"},
        {"name": "豆粕", "symbol": "M"},
        {"name": "豆油", "symbol": "Y"},
        {"name": "棕榈油", "symbol": "P"},
        {"name": "白糖", "symbol": "SR"},
        {"name": "棉花", "symbol": "CF"},
        {"name": "PTA", "symbol": "TA"},
        {"name": "甲醇", "symbol": "MA"},
        {"name": "沪铜", "symbol": "CU"},
        {"name": "沪铝", "symbol": "AL"},
        {"name": "沪锌", "symbol": "ZN"},
        {"name": "沪镍", "symbol": "NI"},
        {"name": "原油", "symbol": "SC"},
        {"name": "燃油", "symbol": "FU"},
        {"name": "沥青", "symbol": "BU"},
        {"name": "橡胶", "symbol": "RU"},
    ]
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.cookies = {}
        self.session = None
        self.api_responses = {}
        self.position_data = []  # 持仓数据
        
    async def scrape_all(self, max_varieties: int = 10, days: int = 14):
        """爬取所有数据"""
        print("=" * 60)
        print("交易可查期货数据爬虫")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"目标: 获取 {max_varieties} 个品种过去 {days} 天的数据")
        print("=" * 60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()
            page.set_default_timeout(60000)
            
            # 监听API响应
            page.on("response", lambda r: asyncio.create_task(self._handle_response(r)))
            
            try:
                # 访问首页获取基础数据
                print("\n[1/3] 访问首页获取基础数据...")
                await page.goto(self.BASE_URL, wait_until="domcontentloaded")
                await asyncio.sleep(10)
                
                # 获取Cookie
                cookies = await context.cookies()
                for cookie in cookies:
                    self.cookies[cookie["name"]] = cookie["value"]
                print(f"获取到 {len(self.cookies)} 个Cookie")
                
                # 访问各品种持仓页面
                print(f"\n[2/3] 访问品种持仓页面...")
                varieties = self.VARIETIES[:max_varieties]
                for i, variety in enumerate(varieties):
                    print(f"  ({i+1}/{len(varieties)}) {variety['name']}({variety['symbol']})...")
                    try:
                        # 访问持仓页面
                        await page.goto(
                            f"{self.BASE_URL}/#/position/variety={variety['symbol']}", 
                            wait_until="domcontentloaded"
                        )
                        await asyncio.sleep(5)
                        
                        # 尝试点击历史数据按钮或切换日期
                        # 等待数据加载
                        await asyncio.sleep(3)
                        
                    except Exception as e:
                        print(f"    访问出错: {e}")
                        
            except Exception as e:
                print(f"浏览器访问出错: {e}")
            finally:
                await browser.close()
        
        # 保存和解析数据
        print(f"\n[3/3] 保存和解析数据...")
        self._save_and_parse_data()
        
    async def _handle_response(self, response):
        """处理API响应"""
        url = response.url
        if any(x in url for x in ["ajax", "api"]) and response.status == 200:
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    data = await response.json()
                    self.api_responses[url] = data
                    
                    # 提取持仓数据
                    if "position" in url.lower():
                        self._extract_position_data(url, data)
                        
                    api_name = url.split('/')[-1].split('?')[0]
                    print(f"    ✓ {api_name}")
            except:
                pass
                
    def _extract_position_data(self, url: str, response: dict):
        """提取持仓数据"""
        if not isinstance(response, dict) or response.get("code") != 0:
            return
            
        data = response.get("data")
        if not data:
            return
            
        # 从URL提取品种
        variety = ""
        if "variety=" in url:
            variety = url.split("variety=")[1].split("&")[0]
            
        # 处理不同格式的持仓数据
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self.position_data.append({
                        "品种": variety or item.get("variety") or item.get("symbol"),
                        "日期": item.get("date") or item.get("trading_day"),
                        "会员": item.get("broker") or item.get("member") or item.get("participant_name"),
                        "多头持仓": item.get("long") or item.get("buy") or item.get("long_position"),
                        "多头变化": item.get("long_chg") or item.get("buy_chg"),
                        "空头持仓": item.get("short") or item.get("sell") or item.get("short_position"),
                        "空头变化": item.get("short_chg") or item.get("sell_chg"),
                        "净持仓": item.get("net") or item.get("net_position"),
                    })
        elif isinstance(data, dict):
            # 可能是嵌套结构
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            self.position_data.append({
                                "品种": variety or item.get("variety"),
                                "类型": key,
                                "日期": item.get("date"),
                                "会员": item.get("broker") or item.get("member"),
                                "多头持仓": item.get("long") or item.get("buy"),
                                "多头变化": item.get("long_chg"),
                                "空头持仓": item.get("short") or item.get("sell"),
                                "空头变化": item.get("short_chg"),
                                "净持仓": item.get("net"),
                            })
        
    def _decode_search_data(self, encoded_str: str) -> dict:
        """解码search数据"""
        try:
            padding = 4 - len(encoded_str) % 4
            if padding != 4:
                encoded_str += '=' * padding
            encoded_str = encoded_str.replace('-', '+').replace('_', '/')
            decoded = base64.b64decode(encoded_str)
            decompressed = zlib.decompress(decoded, -zlib.MAX_WBITS)
            return json.loads(decompressed.decode('utf-8'))
        except:
            return {}
        
    def _save_and_parse_data(self):
        """保存和解析数据"""
        # 保存原始数据
        with open("api_raw_data.json", "w", encoding="utf-8") as f:
            json.dump(self.api_responses, f, ensure_ascii=False, indent=2)
        print(f"原始数据已保存到 api_raw_data.json")
        
        # 解析数据
        all_data = []
        
        for url, response in self.api_responses.items():
            if not isinstance(response, dict) or response.get("code") != 0:
                continue
                
            data = response.get("data")
            if data is None:
                continue
                
            # AI观点
            if "aireport" in url and isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("varietyName"):
                        all_data.append({
                            "类型": "AI观点",
                            "品种": item.get("varietyName"),
                            "代码": item.get("symbol"),
                            "看多": item.get("viewBullish"),
                            "震荡": item.get("viewVolatile"),
                            "看空": item.get("viewBearish"),
                        })
                        
            # 基本面数据
            elif "fundamental_db" in url and isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        all_data.append({
                            "类型": "基本面指标",
                            "品种": item.get("variety"),
                            "指标名称": item.get("name"),
                            "数值": item.get("val"),
                            "日期": item.get("data_date"),
                            "涨跌": item.get("chge"),
                        })
                        
            # 资金流向
            elif "home_money_flow" in url and isinstance(data, dict):
                varieties = data.get("varieties", [])
                values = data.get("value", [])
                if len(varieties) == len(values):
                    for i, variety in enumerate(varieties):
                        all_data.append({
                            "类型": "资金流向",
                            "品种": variety,
                            "净流入(万)": values[i],
                        })
                        
            # 快讯
            elif "home_flow" in url and isinstance(data, dict):
                news_list = data.get("data", [])
                if isinstance(news_list, list):
                    for item in news_list[:30]:
                        if isinstance(item, dict):
                            all_data.append({
                                "类型": "快讯",
                                "时间": item.get("post_time"),
                                "内容": item.get("content", "")[:300],
                            })
                            
            # 品种列表
            elif "search" in url and isinstance(data, str):
                decoded = self._decode_search_data(data)
                if decoded:
                    for v in decoded.get("varieties", []):
                        if isinstance(v, dict):
                            all_data.append({
                                "类型": "品种信息",
                                "品种代码": v.get("symbol"),
                                "品种名称": v.get("name"),
                            })
                    for c in decoded.get("contracts", []):
                        if isinstance(c, dict):
                            all_data.append({
                                "类型": "合约信息",
                                "合约代码": c.get("code"),
                                "品种名称": c.get("name"),
                            })
                    for b in decoded.get("brokers", []):
                        if isinstance(b, dict):
                            all_data.append({
                                "类型": "席位信息",
                                "席位名称": b.get("name"),
                            })
                            
            # 行情数据
            elif "market_temp" in url and isinstance(data, dict):
                for symbol, info in data.items():
                    if isinstance(info, dict):
                        all_data.append({
                            "类型": "行情",
                            "品种": symbol,
                            "价格": info.get("price"),
                            "涨跌幅": info.get("chge_rate"),
                        })
                        
        # 添加持仓数据
        for pos in self.position_data:
            pos["类型"] = "持仓"
            all_data.append(pos)
            
        # 保存到Excel
        if all_data:
            df = pd.DataFrame(all_data)
            df = df.dropna(axis=1, how='all')
            
            with pd.ExcelWriter("futures_data.xlsx", engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='全部数据', index=False)
                
                for dtype in df["类型"].unique():
                    df_type = df[df["类型"] == dtype].drop(columns=["类型"])
                    df_type = df_type.dropna(axis=1, how='all')
                    sheet_name = dtype[:30]
                    df_type.to_excel(writer, sheet_name=sheet_name, index=False)
                    
            print(f"数据已保存到 futures_data.xlsx，共 {len(all_data)} 条记录")
            
            print("\n数据统计:")
            for dtype in df["类型"].unique():
                count = len(df[df["类型"] == dtype])
                print(f"  {dtype}: {count} 条")
                
            # 预览资金流向数据
            df_flow = df[df["类型"] == "资金流向"]
            if not df_flow.empty:
                print("\n资金流向数据预览:")
                print(df_flow.head(20).to_string(index=False))
                
            # 预览AI观点
            df_ai = df[df["类型"] == "AI观点"]
            if not df_ai.empty:
                print("\nAI观点数据预览:")
                print(df_ai.head(10).to_string(index=False))
        else:
            print("未能解析出结构化数据")


async def main():
    scraper = FuturesScraper(headless=True)
    await scraper.scrape_all(max_varieties=10, days=14)


if __name__ == "__main__":
    asyncio.run(main())
