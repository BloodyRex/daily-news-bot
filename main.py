import os
import akshare as ak
import pandas as pd
import feedparser
import resend
import requests
from datetime import datetime, timedelta

# 配置环境变量
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

# 特定关注标的
TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "ref_price": 13.79, "ref_type": "国资转让价"},
    "002475": {"name": "立讯精密", "ref_price": 50.14, "ref_type": "回购均价下限"}
}

def get_stock_data():
    """获取特定股票行情与48h新闻"""
    print("Fetching stock data...")
    stock_report = ""
    df_spot = ak.stock_zh_a_spot_em()
    
    for code, info in TARGET_STOCKS.items():
        # 行情分析
        row = df_spot[df_spot['代码'] == code].iloc[0]
        curr_p = row['最新价']
        offset = round(((curr_p - info['ref_price']) / info['ref_price']) * 100, 2)
        
        # 48h新闻
        df_news = ak.stock_news_em(symbol=code)
        df_news['发布时间'] = pd.to_datetime(df_news['发布时间'])
        recent = df_news[df_news['发布时间'] >= (datetime.now() - timedelta(hours=48))]
        news_str = "\n".join([f"- {r['新闻标题']}" for _, r in recent.iterrows()])
        
        stock_report += f"【{info['name']}】现价:{curr_p}, 基准:{info['ref_price']}, 偏离:{offset}%\n最新动态:\n{news_str}\n\n"
    return stock_report

def get_rss_content():
    """读取 feeds.txt 并获取 RSS 内容"""
    print("Fetching RSS feeds...")
    rss_summary = ""
    if not os.path.exists("feeds.txt"):
        return ""
        
    with open("feeds.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    for url in urls[:10]: # 限制前10个源防止内容过长
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # 每个源取前3条
            rss_summary += f"来源:{feed.feed.get('title', '未知')} | 标题:{entry.title}\n"
    return rss_summary

def ai_analyze(stock_info, rss_info):
    """DeepSeek 综合分析"""
    prompt = f"""
    你是一个资深投资经理。请根据以下两部分数据撰写一份内参：
    
    1. 【重点标的追踪】：
    {stock_info}
    (要求：对比基准价分析风险与机会，给出犀利点评)
    
    2. 【全球宏观动态】：
    {rss_info}
    (要求：精选重要新闻进行翻译总结，分析对大盘或相关赛道的影响)
    
    请直接输出 HTML 格式。重点标的使用蓝色卡片样式，宏观动态使用列表样式。
    """
    
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {deepseek_key}"},
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
    )
    return response.json()['choices'][0]['message']['content'].replace('```html', '').replace('```', '')

def main():
    stock_info = get_stock_data()
    rss_info = get_rss_content()
    
    final_content = ai_analyze(stock_info, rss_info)
    
    # 发送邮件
    resend.Emails.send({
        "from": "StockIntelligence <onboarding@resend.dev>",
        "to": [receiver_email],
        "subject": f"【投研内参】{datetime.now().strftime('%m-%d')} 特定标的+宏观综合版",
        "html": f"<div style='background:#f9f9f9; padding:20px;'>{final_content}</div>"
    })
    print("Done!")

if __name__ == "__main__":
    main()