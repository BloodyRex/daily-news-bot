import os
import akshare as ak
import pandas as pd
import feedparser
import resend
import requests
import time
from datetime import datetime, timedelta

# 1. 基础配置
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

# 已更新您的最新成本位
TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "cost": 13.33},
    "002475": {"name": "立讯精密", "cost": 55.03},
    "603118": {"name": "共进股份", "cost": 12.08},
    "300427": {"name": "红相股份", "cost": 15.45}
}

def get_technical_analysis(code):
    """提取行情并计算区间点位，增加重试逻辑"""
    for _ in range(3): # 最多尝试3次
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
            if df.empty or len(df) < 10: continue
            
            curr_price = df.iloc[-1]['收盘']
            high_60 = df['最高'].max()
            low_60 = df['最低'].min()
            ma5 = df['收盘'].rolling(5).mean().iloc[-1]
            ma20 = df['收盘'].rolling(20).mean().iloc[-1]
            
            # RSI 计算
            delta = df['收盘'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
            last_loss = loss.iloc[-1]
            rsi6 = 100 if last_loss == 0 else 100 - (100 / (1 + (gain.iloc[-1] / last_loss)))
            
            trend = "📈 多头" if ma5 > ma20 else "📉 走弱"
            strength = "🔥 高位" if rsi6 > 80 else ("❄️ 低位" if rsi6 < 20 else "⚖️ 中性")
            
            return {
                "curr": curr_price, "ma5": round(ma5, 2), "ma20": round(ma20, 2),
                "rsi6": round(rsi6, 2), "high_60": high_60, "low_60": low_60,
                "trend_desc": f"{trend} ({strength})"
            }
        except:
            time.sleep(2)
    return None

def get_stock_intel():
    """整合持仓数据"""
    report = ""
    stock_found = False
    try:
        # 尝试获取全市场快照
        df_spot = ak.stock_zh_a_spot_em()
        
        for code, info in TARGET_STOCKS.items():
            match_row = df_spot[df_spot['代码'] == code]
            tech = get_technical_analysis(code)
            
            # 抓取个股新闻
            try:
                df_news = ak.stock_news_em(symbol=code)
                df_news['发布时间'] = pd.to_datetime(df_news['发布时间'])
                recent = df_news[df_news['发布时间'] >= (datetime.now() - timedelta(hours=48))]
                news_str = "\n".join([f"- {r['新闻标题']}" for _, r in recent.iterrows()])
            except:
                news_str = "新闻接口连接受限"

            if tech:
                stock_found = True
                report += f"【{info['name']} ({code})】\n" \
                          f"我的成本: {info['cost']} | 当前价格: {tech['curr']}\n" \
                          f"技术面: {tech['trend_desc']}, RSI6: {tech['rsi6']}\n" \
                          f"60日参考: 支撑位 {tech['low_60']} / 压力位 {tech['high_60']}\n" \
                          f"最新新闻:\n{news_str if news_str else '暂无公告'}\n\n"
    except Exception as e:
        print(f"数据抓取严重异常: {e}")

    if not stock_found:
        return "ERROR: 持仓数据抓取完全失败，请检查网络或Akshare版本。"
    return report

def get_rss_content():
    """抓取RSS"""
    rss_summary = ""
    if not os.path.exists("feeds.txt"): return "feeds.txt missing"
    try:
        with open("feeds.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls[:10]:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                rss_summary += f"来源:{feed.feed.get('title','')} | 标题:{entry.title}\n"
    except:
        rss_summary = "RSS获取受阻"
    return rss_summary

def ai_analyze(stock_intel, rss_info):
    if not deepseek_key: return "AI Key Missing"
    
    # 如果数据抓取失败，注入警告但强制AI根据已知成本分析
    prompt = f"""
    你是一个资深投资组合专家。
    已知我的持仓成本：法兰泰克 13.33, 立讯精密 55.03, 共进股份 12.08, 红相股份 15.45。
    当前抓取到的实时数据如下：
    {stock_intel}
    
    【任务】：
    1. 若实时价缺失，请明确提示并基于成本位进行策略推演。
    2. 针对红相股份、共进股份这种深套标的，给出专业的“止损/补仓/锁仓”逻辑。
    3. 全屏宽版排版，严禁使用Markdown代码块，直接输出HTML。
    4. 资讯汇总按💰财经、🌍时政、💻科技分类，并附带核心逻辑。
    """
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3},
            timeout=120
        )
        return resp.json()['choices'][0]['message']['content'].replace('```html', '').replace('```', '')
    except:
        return "AI 复盘生成失败，请核查 DeepSeek 余额或网络。"

def main():
    print("🚀 正在尝试连接金融数据源...")
    stock_intel = get_stock_intel()
    rss_info = get_rss_content()
    
    # 无论实时数据是否获取成功，都让AI介入生成分析
    final_content = ai_analyze(stock_intel, rss_info)
    
    html_output = f"""
    <div style="margin:0; padding:0; width:100%; font-family:sans-serif; background-color:#ffffff;">
        <div style="width:100%; border-top:8px solid #0052D9; padding:25px 0;">
            <div style="padding:0 20px; display:flex; justify-content:space-between; align-items:baseline;">
                <h1 style="font-size:28px; color:#111; margin:0;">Alpha 持仓深度诊断</h1>
                <span style="color:#999;">{datetime.now().strftime('%m-%d %H:%M')}</span>
            </div>
            <div style="padding:0 20px; line-height:1.8; color:#222;">
                {final_content}
            </div>
        </div>
    </div>
    """

    try:
        resend.Emails.send({
            "from": "Portfolio_Insight <onboarding@resend.dev>",
            "to": [receiver_email],
            "subject": f"【持仓内参】{datetime.now().strftime('%m-%d')} 深度复盘",
            "html": html_output
        })
        print("✅ 研报已投递。")
    except Exception as e:
        print(f"❌ 邮件模块异常: {e}")

if __name__ == "__main__":
    main()
