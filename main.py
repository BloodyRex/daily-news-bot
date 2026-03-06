#!/usr/bin/env python3
import os
import feedparser
import resend
import requests
from datetime import datetime, timezone, timedelta

# 配置
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

def ai_process_content(raw_text):
    """请求 DeepSeek 进行翻译、分类、总结并直接生成 HTML 块"""
    if not deepseek_key or not raw_text.strip():
        return "<p>暂无深度资讯总结。</p>"

    # 更加严厉且明确的指令
    prompt = f"""
    你是一个高端科技周刊的主编。请将以下原始 RSS 数据整理成一份精美的中文简报。
    
    任务要求：
    1. 分类整理：将资讯分为“人工智能”、“编程技术”、“行业新闻”或其他合适类别。
    2. 翻译与总结：将英文标题翻译成地道的中文，并基于摘要提炼核心价值。
    3. 严格排版：请直接输出 HTML 格式的内容。
       - 每个类别用 <h2 style="color: #2c3e50; border-left: 4px solid #c0392b; padding-left: 10px; margin-top: 30px;">类别名称</h2> 标签。
       - 每条资讯用 <div> 包裹，标题用 <a style="color: #2980b9; font-weight: bold; text-decoration: none; font-size: 16px;">，内容用 <p style="color: #555; line-height: 1.6; margin: 5px 0 15px 0;">。
    4. 简洁：每条总结控制在 60 字以内，去掉无用的“Comments”等字样。

    原始数据：
    {raw_text}
    """

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个只会输出 HTML 格式正文的助手。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
            },
            timeout=60
        )
        res_json = response.json()
        return res_json['choices'][0]['message']['content'].replace('```html', '').replace('```', '')
    except Exception as e:
        print(f"DeepSeek 报错: {e}")
        return f"<p>AI 整理失败，请检查 API Key 或网络。错误详情: {e}</p>"

def fetch_data(feeds):
    now = datetime.now(timezone.utc)
    raw_text = ""
    valid_count = 0

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
                if pub_parsed:
                    pub_date = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                    if (now - pub_date) < timedelta(days=1):
                        title = entry.title
                        # 过滤掉几乎没有内容的摘要
                        summary = entry.get('summary', '')
                        if len(summary) < 20: summary = "（查看原文了解详情）"
                        
                        raw_text += f"Source: {feed.feed.get('title', 'News')}\nTitle: {title}\nLink: {entry.link}\nSummary: {summary}\n---\n"
                        valid_count += 1
        except Exception as e:
            print(f"抓取失败 {url}: {e}")
            
    return raw_text, valid_count

def main():
    print("🚀 开始执行 AI 汉化简报任务...")
    
    if not all([resend.api_key, receiver_email, deepseek_key]):
        print("❌ 错误: 环境变量 (RESEND/RECEIVER/DEEPSEEK) 配置不全")
        return

    # 读取源
    feeds = []
    if os.path.exists("feeds.txt"):
        with open("feeds.txt", "r") as f:
            feeds = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    raw_data, count = fetch_data(feeds)
    
    if count > 0:
        # 让 AI 处理内容
        formatted_content = ai_process_content(raw_data)
        
        # 组装最终邮件
        full_html = f"""
        <div style="background-color: #f9f9f9; padding: 20px; font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;">
            <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; border-bottom: 2px solid #f0f0f0; padding-bottom: 20px; margin-bottom: 20px;">
                    <h1 style="margin: 0; color: #333; font-size: 22px;">Rex's Daily Intelligence</h1>
                    <p style="color: #999; font-size: 13px;">{datetime.now().strftime('%Y-%m-%d')} | AI 深度整理版</p>
                </div>
                {formatted_content}
                <div style="text-align: center; margin-top: 40px; color: #ccc; font-size: 11px; border-top: 1px solid #f0f0f0; padding-top: 20px;">
                    由 DeepSeek V3 驱动 | Rex 的自动化工作流
                </div>
            </div>
        </div>
        """
        
        try:
            resend.Emails.send({
                "from": "Newsletter <onboarding@resend.dev>",
                "to": [receiver_email],
                "subject": f"今日深度简报：{count} 条资讯 AI 总结",
                "html": full_html
            })
            print(f"✅ 成功！已发送 {count} 条资讯的总结。")
        except Exception as e:
            print(f"邮件发送失败: {e}")
    else:
        print("今日无新资讯更新。")

if __name__ == "__main__":
    main()
