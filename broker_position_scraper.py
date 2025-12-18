#!/usr/bin/env python3
"""
期货公司持仓数据爬虫 + HTML报告生成
一键获取乾坤期货、摩根大通、国泰君安、中信期货的持仓数据并生成可视化报告

使用方法:
    python3 broker_position_scraper.py

操作步骤:
    1. 首次运行会打开浏览器让你登录
    2. 登录成功后按 Enter 键
    3. 之后运行会自动使用保存的登录状态，无需重复登录
"""

import asyncio
import json
import re
import os
from datetime import datetime
from playwright.async_api import async_playwright
import pandas as pd


class BrokerPositionScraper:
    """期货公司持仓数据爬虫"""
    
    BASE_URL = "https://www.jiaoyikecha.com"
    TARGET_BROKERS = ["乾坤期货", "摩根大通", "国泰君安", "中信期货"]
    AUTH_FILE = "auth_state.json"  # 保存登录状态的文件
    
    def __init__(self):
        self.position_data = []
        self.api_data = {}
        
    async def run(self):
        """运行爬虫并生成报告"""
        print("=" * 70)
        print("🚀 期货公司持仓数据爬虫")
        print(f"   目标席位: {', '.join(self.TARGET_BROKERS)}")
        print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # 获取数据
        await self._scrape_data()
        
        # 处理数据并生成报告
        if self.position_data:
            self._generate_report()
        else:
            print("\n❌ 未获取到数据，无法生成报告")
            
    async def _scrape_data(self):
        """爬取数据"""
        async with async_playwright() as p:
            # 检查是否有保存的登录状态
            has_auth = os.path.exists(self.AUTH_FILE)
            
            browser = await p.chromium.launch(
                headless=has_auth,  # 有登录状态时使用无头模式
                slow_mo=50 if not has_auth else 0
            )
            
            # 如果有保存的登录状态，加载它
            if has_auth:
                print("\n[1/4] 使用已保存的登录状态...")
                context = await browser.new_context(
                    storage_state=self.AUTH_FILE,
                    viewport={"width": 1400, "height": 900},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
            else:
                context = await browser.new_context(
                    viewport={"width": 1400, "height": 900},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
                
            page = await context.new_page()
            page.set_default_timeout(120000)
            
            page.on("response", lambda r: asyncio.create_task(self._handle_response(r)))
            
            try:
                print("\n[1/4] 打开网站..." if has_auth else "\n[1/4] 打开网站...")
                await page.goto(self.BASE_URL, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                # 检查是否需要登录
                need_login = not has_auth
                if has_auth:
                    # 验证登录状态是否有效
                    is_logged_in = await page.evaluate('''() => {
                        return document.body.innerText.includes('退出') || 
                               document.body.innerText.includes('个人中心') ||
                               document.querySelector('.user-info') !== null;
                    }''')
                    if not is_logged_in:
                        print("   ⚠️ 登录状态已过期，需要重新登录")
                        need_login = True
                        # 删除过期的登录状态
                        os.remove(self.AUTH_FILE)
                        await browser.close()
                        # 重新打开浏览器（非无头模式）
                        browser = await p.chromium.launch(headless=False, slow_mo=50)
                        context = await browser.new_context(
                            viewport={"width": 1400, "height": 900},
                            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                        )
                        page = await context.new_page()
                        page.set_default_timeout(120000)
                        page.on("response", lambda r: asyncio.create_task(self._handle_response(r)))
                        await page.goto(self.BASE_URL, wait_until="domcontentloaded")
                        await asyncio.sleep(3)
                
                if need_login:
                    print("\n" + "=" * 70)
                    print("🔐 请在浏览器窗口中登录您的账号")
                    print("   登录完成后，回到终端按 Enter 键继续...")
                    print("   (登录状态会被保存，下次无需重复登录)")
                    print("=" * 70)
                    input()
                    
                    # 保存登录状态
                    await context.storage_state(path=self.AUTH_FILE)
                    print("   ✓ 登录状态已保存")
                
                print("\n[2/4] 验证登录状态...")
                await asyncio.sleep(2)
                
                print("\n[3/4] 获取席位持仓数据...")
                for broker in self.TARGET_BROKERS:
                    print(f"\n  📊 {broker}...")
                    try:
                        url = f"{self.BASE_URL}/#/broker/position/broker={broker}"
                        await page.goto(url, wait_until="domcontentloaded")
                        await asyncio.sleep(5)
                        
                        try:
                            await page.wait_for_selector("table", timeout=10000)
                        except:
                            pass
                            
                        await self._extract_page_data(page, broker)
                        
                    except Exception as e:
                        print(f"    ❌ 出错: {e}")
                        
                print("\n[4/4] 处理数据...")
                        
            except Exception as e:
                print(f"❌ 出错: {e}")
                # 如果出错可能是登录状态问题，删除保存的状态
                if os.path.exists(self.AUTH_FILE):
                    os.remove(self.AUTH_FILE)
                    print("   已清除登录状态，请重新运行")
            finally:
                await browser.close()
                
    async def _handle_response(self, response):
        """处理API响应"""
        url = response.url
        if response.status == 200:
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    data = await response.json()
                    if "broker" in url.lower() or "position" in url.lower():
                        self.api_data[url] = data
                        if isinstance(data, dict) and data.get("code") == 0:
                            self._extract_from_api(url, data)
            except:
                pass
                
    def _extract_from_api(self, url: str, response: dict):
        """从API提取数据"""
        data = response.get("data")
        if not data:
            return
            
        broker = ""
        if "broker=" in url:
            from urllib.parse import unquote
            broker = unquote(url.split("broker=")[1].split("&")[0].split("/")[0])
            
        if broker not in self.TARGET_BROKERS:
            return
            
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self._add_position(broker, item)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            self._add_position(broker, item, key)
                            
    def _add_position(self, broker: str, item: dict, direction: str = None):
        """添加持仓记录"""
        variety = item.get("variety") or item.get("varietyName") or item.get("name")
        if not variety:
            return
            
        self.position_data.append({
            "席位": broker,
            "品种": variety,
            "合约": item.get("code") or item.get("contract"),
            "方向": direction,
            "多头持仓": item.get("buy") or item.get("long"),
            "多头变化": item.get("buy_chge") or item.get("buyChg"),
            "空头持仓": item.get("ss") or item.get("sell") or item.get("short"),
            "空头变化": item.get("ss_chge") or item.get("sellChg"),
            "净持仓": item.get("net"),
            "净变化": item.get("net_chge") or item.get("netChg"),
        })
        
    async def _extract_page_data(self, page, broker: str):
        """从页面提取数据"""
        try:
            table_data = await page.evaluate('''() => {
                const results = [];
                const tables = document.querySelectorAll('table');
                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    let headers = [];
                    rows.forEach((row, idx) => {
                        const cells = row.querySelectorAll('td, th');
                        const rowData = [];
                        cells.forEach(cell => rowData.push(cell.innerText.trim()));
                        if (rowData.length > 0) {
                            if (idx === 0 || rowData.some(c => ['品种', '合约', '多头', '空头'].some(h => c.includes(h)))) {
                                headers = rowData;
                            } else if (headers.length > 0) {
                                const obj = {};
                                headers.forEach((h, i) => { if (i < rowData.length) obj[h] = rowData[i]; });
                                results.push(obj);
                            }
                        }
                    });
                });
                return results;
            }''')
            
            if table_data:
                for row in table_data:
                    row["席位"] = broker
                    self.position_data.append(row)
                print(f"    ✓ 获取 {len(table_data)} 条记录")
            else:
                print(f"    ⚠️ 未获取到数据")
                
        except Exception as e:
            print(f"    ❌ 解析出错: {e}")
            
    def _generate_report(self):
        """生成HTML报告"""
        print("\n" + "=" * 70)
        print("📊 生成HTML报告...")
        print("=" * 70)
        
        # 保存原始数据
        df_raw = pd.DataFrame(self.position_data)
        df_raw.to_excel("broker_positions_raw.xlsx", index=False)
        
        # 处理数据
        df_clean = self._clean_data(df_raw)
        
        if df_clean.empty:
            print("❌ 数据处理后为空")
            return
            
        df_clean.to_excel("broker_positions_cleaned.xlsx", index=False)
        
        # 统计
        print("\n📈 数据统计:")
        for broker in self.TARGET_BROKERS:
            count = len(df_clean[df_clean['席位'] == broker])
            print(f"   {broker}: {count} 个品种")
            
        # 生成HTML
        html = self._build_html(df_clean)
        
        output_file = "broker_positions_report.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
            
        print(f"\n✅ 报告已生成: {output_file}")
        print(f"   请在浏览器中打开查看")
        
    def _clean_data(self, df):
        """清理数据"""
        results = []
        current_variety = None
        
        for _, row in df.iterrows():
            broker = row.get('席位', '')
            variety_text = str(row.get('品种', '')) if pd.notna(row.get('品种')) else ''
            net_text = row.get('总净持仓', '')
            contract_text = row.get('合约', '')
            long_text = row.get('多头持仓', '')
            short_text = row.get('空头持仓', '')
            
            # 跳过分类行
            if pd.isna(net_text) and pd.isna(contract_text) and pd.isna(long_text):
                if variety_text and '建仓过程' not in variety_text and len(variety_text) < 10:
                    current_variety = variety_text
                continue
                
            # 解析净持仓
            direction, net_pos, net_chg = self._parse_net(net_text)
            
            if direction:
                current_variety = variety_text if variety_text and '建仓过程' not in variety_text else current_variety
                contract = self._extract_contract(contract_text)
                long_pos, long_chg = self._parse_position(long_text)
                short_pos, short_chg = self._parse_position(short_text)
                
                if current_variety:
                    results.append({
                        '席位': broker,
                        '品种': current_variety,
                        '净方向': direction,
                        '净持仓': net_pos,
                        '净变化': net_chg,
                        '多头持仓': long_pos,
                        '多头变化': long_chg,
                        '空头持仓': short_pos,
                        '空头变化': short_chg,
                    })
                    
        df_result = pd.DataFrame(results)
        df_result = df_result.dropna(subset=['品种'])
        df_result = df_result[df_result['品种'].str.len() > 0]
        df_result = df_result.drop_duplicates(subset=['席位', '品种'])
        
        return df_result
        
    def _parse_net(self, text):
        """解析净持仓"""
        if pd.isna(text) or text == 0:
            return None, None, None
        text = str(text)
        match = re.search(r'净(多|空)(\d+)\s*\n?\(?([增减]少?)(\d+)\)?', text)
        if match:
            direction = '多' if match.group(1) == '多' else '空'
            position = int(match.group(2))
            change_dir = 1 if '增' in match.group(3) else -1
            change = int(match.group(4)) * change_dir
            return direction, position, change
        return None, None, None
        
    def _parse_position(self, text):
        """解析持仓"""
        if pd.isna(text):
            return None, None
        text = str(text)
        match = re.match(r'(\d+)\s*\n?\(([+-]?\d+)\)', text)
        if match:
            return int(match.group(1)), int(match.group(2))
        match = re.match(r'(\d+)', text)
        if match:
            return int(match.group(1)), 0
        return None, None
        
    def _extract_contract(self, text):
        """提取合约代码"""
        if pd.isna(text):
            return None
        match = re.match(r'([a-zA-Z]+\d+)', str(text))
        return match.group(1) if match else None
        
    def _build_html(self, df):
        """构建HTML"""
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>期货公司持仓分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        h1 {{
            text-align: center;
            color: #00d4ff;
            margin-bottom: 10px;
            font-size: 2.2em;
            text-shadow: 0 0 30px rgba(0, 212, 255, 0.6);
        }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 30px; }}
        .section {{
            background: rgba(255, 255, 255, 0.03);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .section-title {{
            color: #00d4ff;
            font-size: 1.4em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(0, 212, 255, 0.3);
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }}
        .broker-card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s;
        }}
        .broker-card:hover {{ transform: translateY(-5px); }}
        .broker-name {{ font-size: 1.3em; font-weight: bold; color: #00d4ff; margin-bottom: 15px; }}
        .broker-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .stat-item {{ padding: 8px; border-radius: 8px; background: rgba(0, 0, 0, 0.2); }}
        .stat-value {{ font-size: 1.5em; font-weight: bold; }}
        .stat-label {{ font-size: 0.8em; color: #888; }}
        .long {{ color: #ff4757; }}
        .short {{ color: #2ed573; }}
        .tabs {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
        .tab {{
            padding: 12px 24px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .tab:hover {{ background: rgba(0, 212, 255, 0.1); }}
        .tab.active {{ background: rgba(0, 212, 255, 0.2); border-color: #00d4ff; color: #00d4ff; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 10px; text-align: right; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }}
        th {{ background: rgba(0, 212, 255, 0.1); color: #00d4ff; font-weight: 600; position: sticky; top: 0; }}
        td:first-child, th:first-child {{ text-align: left; }}
        tr:hover {{ background: rgba(255, 255, 255, 0.03); }}
        .positive {{ color: #ff4757; }}
        .negative {{ color: #2ed573; }}
        .table-container {{ max-height: 500px; overflow-y: auto; border-radius: 10px; }}
        .comparison {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .compare-box {{ background: rgba(255, 255, 255, 0.02); border-radius: 10px; padding: 15px; }}
        .compare-title {{ font-size: 1.1em; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }}
        .variety-tag {{
            display: inline-block;
            padding: 4px 10px;
            margin: 3px;
            border-radius: 15px;
            font-size: 0.85em;
        }}
        .variety-tag.long {{ background: rgba(255, 71, 87, 0.2); color: #ff4757; }}
        .variety-tag.short {{ background: rgba(46, 213, 115, 0.2); color: #2ed573; }}
        @media (max-width: 1200px) {{ .summary-cards {{ grid-template-columns: repeat(2, 1fr); }} .comparison {{ grid-template-columns: 1fr; }} }}
        @media (max-width: 768px) {{ .summary-cards {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 期货公司持仓分析报告</h1>
        <p class="subtitle">生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 数据来源: 交易可查</p>
        
        <div class="summary-cards">
'''
        
        # 统计卡片
        for broker in self.TARGET_BROKERS:
            df_b = df[df['席位'] == broker]
            total = len(df_b)
            long_count = len(df_b[df_b['净方向'] == '多'])
            short_count = len(df_b[df_b['净方向'] == '空'])
            pct = round(long_count/(total if total else 1)*100)
            
            html += f'''            <div class="broker-card">
                <div class="broker-name">{broker}</div>
                <div class="broker-stats">
                    <div class="stat-item"><div class="stat-value">{total}</div><div class="stat-label">持仓品种</div></div>
                    <div class="stat-item"><div class="stat-value long">{long_count}</div><div class="stat-label">净多品种</div></div>
                    <div class="stat-item"><div class="stat-value short">{short_count}</div><div class="stat-label">净空品种</div></div>
                    <div class="stat-item"><div class="stat-value">{pct}%</div><div class="stat-label">多头占比</div></div>
                </div>
            </div>
'''
        
        html += '''        </div>
        
        <div class="section">
            <h2 class="section-title">📊 各席位持仓对比</h2>
            <div class="comparison">
                <div class="compare-box">
                    <div class="compare-title long">🔴 净多品种</div>
'''
        
        # 净多对比
        for broker in self.TARGET_BROKERS:
            df_b = df[(df['席位'] == broker) & (df['净方向'] == '多')]
            varieties = df_b.nlargest(8, '净持仓')['品种'].tolist() if not df_b.empty and '净持仓' in df_b.columns else []
            html += f'                    <div style="margin-bottom:10px;"><strong>{broker}:</strong> '
            for v in varieties:
                html += f'<span class="variety-tag long">{v}</span>'
            html += '</div>\n'
            
        html += '''                </div>
                <div class="compare-box">
                    <div class="compare-title short">🟢 净空品种</div>
'''
        
        # 净空对比
        for broker in self.TARGET_BROKERS:
            df_b = df[(df['席位'] == broker) & (df['净方向'] == '空')]
            varieties = df_b.nlargest(8, '净持仓')['品种'].tolist() if not df_b.empty and '净持仓' in df_b.columns else []
            html += f'                    <div style="margin-bottom:10px;"><strong>{broker}:</strong> '
            for v in varieties:
                html += f'<span class="variety-tag short">{v}</span>'
            html += '</div>\n'
            
        html += '''                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📈 各席位持仓明细</h2>
            <div class="tabs">
'''
        
        # 标签
        for i, broker in enumerate(self.TARGET_BROKERS):
            active = 'active' if i == 0 else ''
            html += f'                <div class="tab {active}" onclick="showTab(\'{broker}\')">{broker}</div>\n'
            
        html += '            </div>\n'
        
        # 表格
        for i, broker in enumerate(self.TARGET_BROKERS):
            active = 'active' if i == 0 else ''
            df_b = df[df['席位'] == broker].copy()
            if '净持仓' in df_b.columns:
                df_b['净持仓_abs'] = df_b['净持仓'].abs()
                df_b = df_b.sort_values('净持仓_abs', ascending=False)
            
            html += f'''            <div class="tab-content {active}" id="tab-{broker}">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr><th>品种</th><th>净方向</th><th>净持仓</th><th>净变化</th><th>多头持仓</th><th>多头变化</th><th>空头持仓</th><th>空头变化</th></tr>
                        </thead>
                        <tbody>
'''
            
            for _, row in df_b.iterrows():
                net_dir = row.get('净方向', '')
                net_class = 'long' if net_dir == '多' else 'short'
                net_pos = int(row['净持仓']) if pd.notna(row.get('净持仓')) else 0
                net_chg = int(row['净变化']) if pd.notna(row.get('净变化')) else 0
                long_pos = int(row['多头持仓']) if pd.notna(row.get('多头持仓')) else 0
                long_chg = int(row['多头变化']) if pd.notna(row.get('多头变化')) else 0
                short_pos = int(row['空头持仓']) if pd.notna(row.get('空头持仓')) else 0
                short_chg = int(row['空头变化']) if pd.notna(row.get('空头变化')) else 0
                
                net_chg_class = 'positive' if net_chg > 0 else 'negative' if net_chg < 0 else ''
                long_chg_class = 'positive' if long_chg > 0 else 'negative' if long_chg < 0 else ''
                short_chg_class = 'positive' if short_chg > 0 else 'negative' if short_chg < 0 else ''
                
                html += f'''                            <tr>
                                <td>{row['品种']}</td>
                                <td class="{net_class}">净{net_dir}</td>
                                <td>{net_pos:,}</td>
                                <td class="{net_chg_class}">{'+' if net_chg > 0 else ''}{net_chg:,}</td>
                                <td>{long_pos:,}</td>
                                <td class="{long_chg_class}">{'+' if long_chg > 0 else ''}{long_chg:,}</td>
                                <td>{short_pos:,}</td>
                                <td class="{short_chg_class}">{'+' if short_chg > 0 else ''}{short_chg:,}</td>
                            </tr>
'''
            
            html += '''                        </tbody>
                    </table>
                </div>
            </div>
'''
        
        html += '''        </div>
        
        <div style="text-align: center; color: #666; margin-top: 30px; padding: 20px;">
            <p>⚠️ 风险提示：以上数据仅供参考，期货交易风险较大，请谨慎决策</p>
        </div>
    </div>
    
    <script>
        function showTab(broker) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + broker).classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
'''
        
        return html


async def main():
    scraper = BrokerPositionScraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
