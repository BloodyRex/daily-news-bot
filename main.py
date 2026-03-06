#!/usr/bin/env python3
import sys
import os
import time
import feedparser
import resend
from datetime import datetime, timezone, timedelta

# 从 GitHub Secrets 读取配置
resend.api_key = os.environ.get("RESEND_API_KEY")
receiver_email = os.environ.get("RECEIVER_EMAIL")

def read_feeds_file(filepath="feeds.txt"): # 保留你的文件名
    """Read RSS feed URLs from a text file."""
    feeds = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    feeds.append(line)
    except FileNotFoundError:
        # 如果文件不存在，脚本会报错退出，确保你在 GitHub 仓库根目录有 feeds.txt
        print(f"Error: Feeds file '{filepath}' not found.")
        return []
    return feeds

def fetch_and_build_html(feeds):
    """抓取并构建 HTML 邮件内容"""
    now = datetime.now(timezone.utc)
    html_body = '<div style="font-family: sans-serif; line-height: 1.6;">'
    total_entries = 0

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            title = feed.feed.get('title', '未知订阅源')
            html_body += f'<h2 style="color: #2c3e50; border-bottom: 1px solid #eee;">{title}</h2><ul>'
            
            feed_count = 0
            for entry in feed.entries:
                # 获取时间并判断是否为 24 小时内更新
                pub_parsed = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
                if pub_parsed:
                    pub_date = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
                    if (now - pub_date) < timedelta(days=1):
                        html_body += f'<li style="margin-bottom: 10px;"><a href="{entry.link}">{entry.title}</a></li>'
                        feed_count += 1
                        total_entries += 1
            
            if feed_count == 0:
                html_body += '<li style="color: #999;">过去 24 小时无更新</li>'
            html_body += '</ul>'
        except Exception as e:
            print(f"Error fetching {url}: {e}")
    
    html_body += '</div>'
    return html_body if total_entries > 0 else None

def main():
    print("RSS Subscriber - Starting automation...")
    
    # 验证环境变量
    if not resend.api_key or not receiver_email:
        print("❌ 错误: 找不到 RESEND_API_KEY 或 RECEIVER_EMAIL 环境变量。")
        return

    feeds = read_feeds_file("feeds.txt")
    if not feeds:
        print("No feeds to read.")
        return

    print(f"Found {len(feeds)} feed(s). Processing...")
    
    email_content = fetch_and_build_html(feeds)

    if email_content:
        print(f"Attempting to send email to {receiver_email}...")
        try:
            resend.Emails.send({
                "from": "Newsletter <onboarding@resend.dev>",
                "to": [receiver_email],
                "subject": f"每日资讯汇总 - {datetime.now().strftime('%Y-%m-%d')}",
                "html": email_content
            })
            print("✅ Email sent successfully!")
        except Exception as e:
            print(f"❌ Resend API Error: {e}")
    else:
        print("⚠️ No updates found in the last 24 hours. Skipping email.")

if __name__ == "__main__":
    main()