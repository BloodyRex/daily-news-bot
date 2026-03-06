#!/usr/bin/env python3
import os
import feedparser
import resend
import requests
from datetime import datetime, timezone, timedelta

# 配置环境变量
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")

def ai_summarize(content_list):
    """调用 DeepSeek API 进行批量翻译和摘要"""
    if not deepseek_key or not content_list:
        return content_list

    prompt = f"""
    你是一个专业的资讯简报编辑。请将以下 RSS 资讯条目翻译成中文，并进行分类整理。
    要求：
    1. 标题要准确、吸引人。
    2. 摘要请提炼核心观点，每条控制在 50-80 字左右。
    3. 风格简洁、专业，适合快速阅读。
    
    待处理资讯：
    {content_list}
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
            timeout=30
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"AI 总结出错: {e}")
        return "AI 总结暂时不可用，请查看原文链接。"

def fetch_and_build_html(feeds):
    now = datetime.now(timezone.utc)
    all_news_text = "" # 用于发给 AI 处理的文本
    entries_data = []  # 存储带链接的数据

    # 1. 抓取并筛选数据
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
                if pub_parsed:
                    pub_date = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                    if (now - pub_date) < timedelta(days=1):
                        title = entry.title
                        link = entry.link
                        summary = entry.get('summary', '')[:200]
                        all_news_text += f"标题: {title}\n摘要: {summary}\n---\n"
                        entries_data.append({"title": title, "link": link})
        except Exception as e:
            print(f"解析错误 {url}: {e}")

    if not entries_data:
        return None

    # 2. 调用 DeepSeek 进行翻译和总结
    print("正在请求 DeepSeek AI 进行智能整理...")
    ai_content = ai_summarize(all_news_text)

    # 3. 构建 HTML 模板
    html = f"""
    <div style="background-color: #f6f8fa; padding: 30px; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.08);">
            <div style="border-bottom: 2px solid #eaecef; padding-bottom: 20px; margin-bottom: 30px; text-align: center;">
                <h1 style="margin: 0; color: #1f2328; font-size: 24px;">Rex's Intelligence Feed</h1>
                <p style="color: #57606a; font-size: 14px; margin-top: 10px;">{datetime.now().strftime('%Y年%m月%d日')} | AI 驱动的深度简报</p>
            </div>
            
            <div style="line-height: 1.8; color: #24292f; white-space: pre-wrap; font-size: 15px;">
{ai_content}
            </div>

            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eaecef;">
                <p style="font-size: 13px; color: #8c959f; text-align: center; font-style: italic;">
                    资讯来源：{len(feeds)} 个订阅源 | 整理者：DeepSeek AI
                </p>
            </div>
        </div>
    </div>
    """
    return html

def main():
    print("Newsletter Bot (AI版) 开始运行...")
    feeds = []
    if os.path.exists("feeds.txt"):
        with open("feeds.txt", "r") as f:
            feeds = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not feeds:
        print("没有可抓取的源。")
        return

    email_body = fetch_and_build_html(feeds)

    if email_body:
        try:
            resend.Emails.send({
                "from": "Rex News <onboarding@resend.dev>",
                "to": [receiver_email],
                "subject": f"AI 简报：{datetime.now().strftime('%m/%d')} 行业动态总结",
                "html": email_body
            })
            print("✅ AI 中文简报已发送！")
        except Exception as e:
            print(f"❌ 发送失败: {e}")
    else:
        print("⚠️ 过去 24 小时内无更新。")

if __name__ == "__main__":
    main()