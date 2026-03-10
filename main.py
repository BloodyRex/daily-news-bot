import os
import akshare as ak
import pandas as pd
import feedparser
import resend
import requests
from datetime import datetime, timedelta

# 1. 核心基础配置
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

# 关注标的与基准价格（国资/回购成本线）
TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "ref_price": 13.79, "ref_type": "国资转让价"},
    "002475": {"name": "立讯精密", "ref_price": 50.14, "ref_type": "回购均价下限"}
}

def get_technical_analysis(code):
    """抓取历史行情并计算技术面指标"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        if len(df) < 20: return "数据量不足，无法分析"
        
        curr_price = df.iloc[-1]['收盘']
        ma5 = df['收盘'].rolling(5).mean().iloc[-1]
        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        
        # 稳健的 RSI(6) 计算
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        last_loss = loss.iloc[-1]
        rsi6 = 100 if last_loss == 0 else 100 - (100 / (1 + (gain.iloc[-1] / last_loss)))
        
        trend = "📈 多头排列" if ma5 > ma20 else "📉 空头震荡"
        strength = "🔥 超买" if rsi6 > 80 else ("❄️ 超跌" if rsi6 < 20 else "⚖️ 中性")
        
        return f"现价:{curr_price}, MA5:{round(ma5,2)}, MA20:{round(ma20,2)}, RSI6:{round(rsi6,2)} ({trend}, {strength})"
    except Exception as e:
        return f"技术面获取失败: {str(e)}"

def get_stock_intel():
    """整合个股实时行情、技术指标与48h新闻"""
    report = ""
    try:
        df_spot = ak.stock_zh_a_spot_em()
        for code, info in TARGET_STOCKS.items():
            row = df_spot[df_spot['代码'] == code].iloc[0]
            curr_p = row['最新价']
            tech_data = get_technical_analysis(code)
            
            # 获取48h新闻
            df_news = ak.stock_news_em(symbol=code)
            df_news['发布时间'] = pd.to_datetime(df_news['发布时间'])
            recent = df_news[df_news['发布时间'] >= (datetime.now() - timedelta(hours=48))]
            news_str = "\n".join([f"- {r['新闻标题']}" for _, r in recent.iterrows()])
            
            report += f"【{info['name']} ({code})】\n行情价:{curr_p} (参考基准:{info['ref_price']})\n量化指标:{tech_data}\n48H动态:\n{news_str if news_str else '暂无重大公告'}\n\n"
    except Exception as e:
        report = f"个股抓取异常: {str(e)}"
    return report

def get_rss_content():
    """读取 feeds.txt 并提取最新资讯"""
    rss_summary = ""
    if not os.path.exists("feeds.txt"): return "feeds.txt 缺失"
    try:
        with open("feeds.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls[:15]:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                source = feed.feed.get('title', '未知来源')
                rss_summary += f"来源:{source} | 标题:{entry.title}\n"
    except Exception as e:
        rss_summary = f"RSS 读取失败: {str(e)}"
    return rss_summary

def ai_analyze(stock_intel, rss_info):
    """调用 DeepSeek 进行分级排版分析"""
    if not deepseek_key: return "DeepSeek API Key 未配置"
    
    prompt = f"""
    你是一个资深投资总监和商业主编。请处理以下原始数据，输出一份专业的 HTML 投研内参。
    
    一、重点个股分析（数据）：
    {stock_intel}
    
    二、全球宏观简报（数据）：
    {rss_info}

    【任务指令】：
    1. **个股复盘**：结合技术指标（重点看RSI是否超跌）与基准价，给出清晰的【现状-逻辑-操作建议】。
    2. **RSS 3x3 策略**：将新闻严格划分为【💰财经与市场】、【🌍时政与综合】、【💻科技与产品】。
       每一类确保整合至少3条高人气、高价值内容，并附带简短点评。
    
    【HTML 排版规范】：
    - 界面宽度要大（适应 900px），边距极简。
    - 标题用黑色加粗大号字；正文分段清晰；技术参数、来源等次要信息用 #888 灰色小号字。
    - 禁止输出任何 Markdown 标记（如 ```html）。
    """
    
    try:
        response = requests.post(
            "[https://api.deepseek.com/v1/chat/completions](https://api.deepseek.com/v1/chat/completions)",
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
        return f"AI 引擎调用失败: {str(e)}"

def main():
    print("🚀 启动自动化投研工作流...")
    if not all([resend.api_key, receiver_email, deepseek_key]):
        print("❌ 错误：环境变量 Secrets 配置不全")
        return

    # 获取并处理内容
    stock_intel = get_stock_intel()
    rss_info = get_rss_content()
    final_content = ai_analyze(stock_intel, rss_info)
    
    # 组装宽屏 HTML 模板并发送
    print("📧 正在组装宽屏报表并发送...")
    try:
        resend.Emails.send({
            "from": "Investment_Insight <onboarding@resend.dev>",
            "to": [receiver_email],
            "subject": f"【投研内参】{datetime.now().strftime('%m-%d')} 技术+消息深度复盘",
            "html": f"""
            <div style="background-color: #ffffff; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;">
                <div style="width: 100%; max-width: 950px; margin: 0 auto; border-top: 3px solid #111; padding-top: 25px;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 40px;">
                        <span style="font-size:
