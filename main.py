import os
import akshare as ak
import pandas as pd
import feedparser
import resend
import requests
from datetime import datetime, timedelta

# 1. 基础配置
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "ref_price": 13.79, "ref_type": "国资转让价"},
    "002475": {"name": "立讯精密", "ref_price": 50.14, "ref_type": "回购均价下限"}
}

def get_technical_analysis(code):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        if len(df) < 20: return "数据量不足"
        curr_price = df.iloc[-1]['收盘']
        ma5 = df['收盘'].rolling(5).mean().iloc[-1]
        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        last_loss = loss.iloc[-1]
        rsi6 = 100 if last_loss == 0 else 100 - (100 / (1 + (gain.iloc[-1] / last_loss)))
        trend = "📈 多头" if ma5 > ma20 else "📉 震荡"
        strength = "🔥 超买" if rsi6 > 80 else ("❄️ 超跌" if rsi6 < 20 else "⚖️ 中性")
        return f"现价:{curr_price}, MA5:{round(ma5,2)}, MA20:{round(ma20,2)}, RSI6:{round(rsi6,2)} ({trend}, {strength})"
    except:
        return "技术面获取失败"

def get_stock_intel():
    report = ""
    try:
        df_spot = ak.stock_zh_a_spot_em()
        for code, info in TARGET_STOCKS.items():
            row = df_spot[df_spot['代码'] == code].iloc[0]
            tech_data = get_technical_analysis(code)
            df_news = ak.stock_news_em(symbol=code)
            df_news['发布时间'] = pd.to_datetime(df_news['发布时间'])
            recent = df_news[df_news['发布时间'] >= (datetime.now() - timedelta(hours=48))]
            news_str = "\n".join([f"- {r['新闻标题']}" for _, r in recent.iterrows()])
            report += f"【{info['name']} ({code})】\n行情:{row['最新价']} (基准:{info['ref_price']})\n指标:{tech_data}\n新闻:\n{news_str if news_str else '暂无'}\n\n"
    except:
        report = "个股抓取异常"
    return report

def get_rss_content():
    rss_summary = ""
    if not os.path.exists("feeds.txt"): return "feeds.txt 缺失"
    try:
        with open("feeds.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls[:15]:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                rss_summary += f"来源:{feed.feed.get('title','')} | 标题:{entry.title}\n"
    except:
        rss_summary = "RSS 读取失败"
    return rss_summary

def ai_analyze(stock_intel, rss_info):
    if not deepseek_key: return "DeepSeek Key 缺失"
    prompt = f"""
    你是一个资深投资顾问。请处理以下数据并输出 HTML 报告：
    1. 个股分析：{stock_intel} (结合RSI和基准价给出建议)
    2. RSS资讯：{rss_info} (严格分为💰财经、🌍时政、💻科技三类，每类至少3条)
    规范：900px宽屏排版，标题大号加粗，正文分级，次要信息灰色。不要输出Markdown符号。
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
        return "AI 分析失败"

def main():
    print("🚀 启动任务...")
    if not all([resend.api_key, receiver_email, deepseek_key]):
        print("❌ 配置缺失")
        return

    stock_intel = get_stock_intel()
    rss_info = get_rss_content()
    final_content = ai_analyze(stock_intel, rss_info)
    
    # 修复后的 HTML 模板
    html_template = f"""
    <div style="background-color: #ffffff; padding: 20px; font-family: sans-serif;">
        <div style="width: 100%; max-width: 950px; margin: 0 auto; border-top: 3px solid #111; padding-top: 25px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 30px;">
                <span style="font-size: 24px; font-weight: bold;">投研内参</span>
                <span style="color: #666;">{datetime.now().strftime('%m-%d %H:%M')}</span>
            </div>
            <div style="line-height: 1.7; color: #222;">
                {final_content}
            </div>
            <div style="margin-top: 50px; border-top: 1px solid #eee; text-align: center; color: #bbb; font-size: 11px;">
                Akshare + DeepSeek 联合驱动
            </div>
        </div>
    </div>
    """

    try:
        resend.Emails.send({{
            "from": "Insight <onboarding@resend.dev>",
            "to": [receiver_email],
            "subject": f"【投研】{datetime.now().strftime('%m-%d')} 复盘内参",
            "html": html_template
        }})
        print("✅ 成功！")
    except Exception as e:
        print(f"❌ 失败: {e}")

if __name__ == "__main__":
    main()
