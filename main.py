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

# 关注标的清单（新增共进股份、红相股份）
TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "ref_price": 13.79},
    "002475": {"name": "立讯精密", "ref_price": 50.14},
    "603118": {"name": "共进股份", "ref_price": 8.50},  # 参考基准价可根据实际调整
    "300427": {"name": "红相股份", "ref_price": 7.20}   
}

def get_technical_analysis(code):
    """计算核心量化指标"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        if len(df) < 20: return "数据不足"
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
        return "量化数据暂缺"

def get_stock_intel():
    """抓取个股深度信息"""
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
            report += f"【{info['name']} ({code})】\n行情:{row['最新价']} (基准:{info['ref_price']})\n指标:{tech_data}\n动态:\n{news_str if news_str else '暂无公告'}\n\n"
    except:
        report = "个股数据源连接超时"
    return report

def get_rss_content():
    """提取 RSS 原始资讯"""
    rss_summary = ""
    if not os.path.exists("feeds.txt"): return "feeds.txt 缺失"
    try:
        with open("feeds.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls[:15]:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                rss_summary += f"来源:{feed.feed.get('title','')} | 标题:{entry.title} | 内容:{entry.get('summary', entry.get('description', ''))[:200]}\n"
    except:
        rss_summary = "RSS 数据流异常"
    return rss_summary

def ai_analyze(stock_intel, rss_info):
    """DeepSeek 高级排版分析引擎"""
    if not deepseek_key: return "DeepSeek Key 缺失"
    prompt = f"""
    你是一个顶级基金经理。请将以下数据整理成“无边框全屏”研报。
    
    1. 个股复盘（{stock_intel}）：
       - 分析共进股份、红相股份等新加入标的。
       - 结合 RSI 指标指出谁在超跌买入区，谁在风险区。
       - 分级排版：个股标题大号加粗，点评正文清晰，技术参数灰色小号字。

    2. 全球动态总结（{rss_info}）：
       - 必须严格分为：💰财经与市场、🌍时政与综合、💻科技与产品。
       - **重点要求**：每一条新闻必须包含“中文标题”和“核心内容总结（100字以内）”。
       - 严禁只有标题没有总结。确保读者读完邮件即获取完整信息，无需点击原文。

    规范：全篇取消边框，宽度撑满。直接输出 HTML 标签，不含 Markdown。
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
        return "AI 分析模块暂时下线"

def main():
    print("🚀 启动宽屏深度研报任务...")
    if not all([resend.api_key, receiver_email, deepseek_key]):
        return print("❌ 缺失环境变量")

    stock_intel = get_stock_intel()
    rss_info = get_rss_content()
    final_content = ai_analyze(stock_intel, rss_info)
    
    # 极简全屏 HTML 模板
    html_output = f"""
    <div style="margin: 0; padding: 0; width: 100%; font-family: sans-serif; background-color: #ffffff;">
        <div style="width: 100%; border-top: 5px solid #1a1a1a; padding: 30px 0;">
            <div style="padding: 0 20px; margin-bottom: 40px; display: flex; justify-content: space-between; align-items: baseline;">
                <h1 style="font-size: 32px; margin: 0; color: #111; letter-spacing: -1px;">AI 投研全景内参</h1>
                <span style="font-size: 14px; color: #888;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
            </div>
            <div style="padding: 0 20px; line-height: 1.8; color: #222; font-size: 16px;">
                {final_content}
            </div>
            <div style="margin-top: 80px; padding: 40px 20px; border-top: 1px solid #f0f0f0; text-align: left; color: #aaa; font-size: 12px;">
                核心数据源：Akshare & 实时 RSS | 算法驱动：DeepSeek-V3
            </div>
        </div>
    </div>
    """

    try:
        resend.Emails.send({
            "from": "Investment_Insight <onboarding@resend.dev>",
            "to": [receiver_email],
            "subject": f"【投研全景】{datetime.now().strftime('%m-%d')} 技术面+深度资讯总结",
            "html": html_output
        })
        print("✅ 深度研报已满屏送达。")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    main()
