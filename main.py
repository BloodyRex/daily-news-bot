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

# 【持仓配置区】已更新您的最新成本
TARGET_STOCKS = {
    "603966": {"name": "法兰泰克", "cost": 13.33},
    "002475": {"name": "立讯精密", "cost": 55.03},
    "603118": {"name": "共进股份", "cost": 12.08},
    "300427": {"name": "红相股份", "cost": 15.45}
}

def get_technical_analysis(code):
    """提取行情数据并自动寻找区间关键点位"""
    try:
        # 获取近60个交易日的数据
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        if len(df) < 20: return None
        
        curr_price = df.iloc[-1]['收盘']
        # 计算 60 日区间最高（压力位）与最低（支撑位）
        high_60 = df['最高'].max()
        low_60 = df['最低'].min()
        
        # 均线与指标
        ma5 = df['收盘'].rolling(5).mean().iloc[-1]
        ma20 = df['收盘'].rolling(20).mean().iloc[-1]
        
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        last_loss = loss.iloc[-1]
        rsi6 = 100 if last_loss == 0 else 100 - (100 / (1 + (gain.iloc[-1] / last_loss)))
        
        trend = "📈 多头排列" if ma5 > ma20 else "📉 趋势走弱"
        strength = "🔥 超买" if rsi6 > 80 else ("❄️ 超跌" if rsi6 < 20 else "⚖️ 中性")
        
        return {
            "curr": curr_price,
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "rsi6": round(rsi6, 2),
            "high_60": high_60,
            "low_60": low_60,
            "trend_desc": f"{trend} ({strength})"
        }
    except:
        return None

def get_stock_intel():
    """整合持仓数据与自动点位信息"""
    report = ""
    try:
        df_spot = ak.stock_zh_a_spot_em()
        for code, info in TARGET_STOCKS.items():
            # 过滤个股实时行情
            match_row = df_spot[df_spot['代码'] == code]
            if match_row.empty: continue
            
            row = match_row.iloc[0]
            tech = get_technical_analysis(code)
            
            # 获取最近48小时新闻
            df_news = ak.stock_news_em(symbol=code)
            df_news['发布时间'] = pd.to_datetime(df_news['发布时间'])
            recent = df_news[df_news['发布时间'] >= (datetime.now() - timedelta(hours=48))]
            news_str = "\n".join([f"- {r['新闻标题']}" for _, r in recent.iterrows()])
            
            if tech:
                report += f"【{info['name']} ({code})】\n" \
                          f"我的成本: {info['cost']} | 当前价格: {tech['curr']}\n" \
                          f"技术面: {tech['trend_desc']}, RSI6: {tech['rsi6']}\n" \
                          f"支撑区(60日低): {tech['low_60']} | 压力区(60日高): {tech['high_60']}\n" \
                          f"核心公告与新闻:\n{news_str if news_str else '暂无重要公告'}\n\n"
    except Exception as e:
        report = f"持仓分析模块抓取异常: {str(e)}"
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
                rss_summary += f"来源:{feed.feed.get('title','')} | 标题:{entry.title} | 内容:{entry.get('summary', entry.get('description', ''))[:200]}\n"
    except:
        rss_summary = "RSS 数据流异常"
    return rss_summary

def ai_analyze(stock_intel, rss_info):
    if not deepseek_key: return "DeepSeek Key 缺失"
    prompt = f"""
    你是一个资深投资组合策略师。请根据以下持仓详情和市场数据，直接撰写一份“全屏宽版”投研复盘邮件。
    
    一、我的持仓诊断（重点）：
    {stock_intel}
    【分析指令】：
    1. 针对每只股票，直接对比我的“持仓成本”与“当前价”。如果是深度亏损标的，请分析最新新闻和支撑位，给出【补仓/减仓/锁仓】的具体建议。
    2. 利用 60 日支撑和压力位，给出明确的止盈止损预期。
    3. 评价当前技术面趋势，提示短期风险。

    二、宏观资讯分析：
    {rss_info}
    【要求】：按💰财经、🌍时政、💻科技分级。每条信息必须给出“中文标题”和“核心内涵总结”。

    规范：全屏显示，去掉所有边框和边距。标题用蓝色，重要建议使用加粗 HTML。直接输出 HTML 内容。
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
        return "AI 分析器暂时无法响应，请稍后检查网络。"

def main():
    if not all([resend.api_key, receiver_email, deepseek_key]):
        return print("❌ 缺失环境变量配置")

    stock_intel = get_stock_intel()
    rss_info = get_rss_content()
    final_content = ai_analyze(stock_intel, rss_info)
    
    html_output = f"""
    <div style="margin: 0; padding: 0; width: 100%; font-family: -apple-system, system-ui, sans-serif; background-color: #ffffff;">
        <div style="width: 100%; border-top: 8px solid #0052D9; padding: 25px 0;">
            <div style="padding: 0 20px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: baseline;">
                <h1 style="font-size: 28px; color: #111; margin: 0;">Alpha 持仓深度诊断</h1>
                <span style="font-size: 14px; color: #999;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
            </div>
            <div style="padding: 0 20px; line-height: 1.8; color: #222;">
                {final_content}
            </div>
            <div style="margin-top: 60px; padding: 40px 20px; border-top: 1px solid #f0f0f0; color: #bbb; font-size: 11px;">
                自动化投研报告 · 基于 Akshare 数据与 DeepSeek 决策引擎
            </div>
        </div>
    </div>
    """

    try:
        resend.Emails.send({
            "from": "Portfolio_Insight <onboarding@resend.dev>",
            "to": [receiver_email],
            "subject": f"【持仓内参】{datetime.now().strftime('%m-%d')} 复盘与操作建议",
            "html": html_output
        })
        print("✅ 深度诊断研报已发送。")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    main()
