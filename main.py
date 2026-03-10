import os
import akshare as ak
import pandas as pd
import feedparser
import resend
import requests
from datetime import datetime, timedelta

# 配置
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "ref_price": 13.79, "ref_type": "国资转让价"},
    "002475": {"name": "立讯精密", "ref_price": 50.14, "ref_type": "回购均价下限"}
}

def get_technical_analysis(code):
    """抓取历史数据并计算简单的技术指标"""
    try:
        # 获取近60个交易日的日K线
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        if len(df) < 20: return "数据量不足，无法进行技术分析"
        
        curr_price = df.iloc[-1]['收盘']
        
        # 计算均线
        ma5 = df['收盘'].rolling(5).mean().iloc[-1]
        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        
        # 稳健的 RSI(6) 计算
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        
        last_loss = loss.iloc[-1]
        if last_loss == 0:
            rsi6 = 100
        else:
            rs = gain.iloc[-1] / last_loss
            rsi6 = 100 - (100 / (1 + rs))
        
        trend = "📈 多头排列" if ma5 > ma20 else "📉 空头震荡"
        strength = "🔥 超买" if rsi6 > 80 else ("❄️ 超跌" if rsi6 < 20 else "⚖️ 中性")
        
        return f"现价:{curr_price}, MA5:{round(ma5,2)}, MA20:{round(ma20,2)}, RSI6:{round(rsi6,2)} ({trend}, {strength})"
    except Exception as e:
        return f"技术面分析暂不可用: {str(e)}"

def get_stock_intel():
    """获取股票新闻+技术面综合信息"""
    report = ""
    try:
        df_spot = ak.stock_zh_a_spot_em()
        for code, info in TARGET_STOCKS.items():
            row = df_spot[df_spot['代码'] == code].iloc[0]
            curr_p = row['最新价']
            tech_data = get_technical_analysis(code)
            
            # 48h新闻
            df_news = ak.stock_news_em(symbol=code)
            df_news['发布时间'] = pd.to_datetime(df_news['发布时间'])
            limit_time = datetime.now() - timedelta(hours=48)
            recent = df_news[df_news['发布时间'] >= limit_time]
            news_str = "\n".join([f"- {r['新闻标题']}" for _, r in recent.iterrows()])
            
            report += f"【{info['name']} ({code})】\n行情:{curr_p} (参考基准:{info['ref_price']})\n技术指标:{tech_data}\n最新新闻:\n{news_str if news_str else '无'}\n\n"
    except Exception as e:
        report = f"个股数据抓取失败: {str(e)}"
    return report

def get_rss_content():
    """读取 feeds.txt 并获取内容"""
    rss_summary = ""
    if not os.path.exists("feeds.txt"): return "feeds.txt 文件缺失"
    try:
        with open("feeds.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls[:15]:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                rss_summary += f"来源:{feed.feed.get('title','')} | 标题:{entry.title}\n"
    except Exception as e:
        rss_summary = f"RSS 抓取异常: {str(e)}"
    return rss_summary

def ai_analyze(stock_intel, rss_info):
    """DeepSeek 深度综合分析"""
    if not deepseek_key: return "DeepSeek Key 缺失"
    
    prompt = f"""
    你是一个资深投资顾问。请分析以下数据并撰写报告：
    
    一、重点个股分析：
    {stock_intel}
    要求：1. 结合“技术指标”分析目前股价在图形上所处的位置。
         2. 结合“最近新闻”分析消息面是否支撑股价反转。
         3. 给出明确的“操盘手视角”点评。
    
    二、全球宏观简报：
    {rss_info}
    要求：精选3条最重要的新闻，分析其对大盘或相关板块的影响。
    
    请直接输出 HTML。个股使用蓝色背景卡片样式，技术面分析请用加粗字体。
    不要输出Markdown格式，直接输出HTML标签内容。
    """
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            },
            timeout=120
        )
        return response.json()['choices'][0]['message']['content'].replace('```html', '').replace('```', '')
    except Exception as e:
        return f"AI 分析调用失败: {str(e)}"

def main():
    print("🚀 启动自动化投研任务...")
    if not all([resend.api_
