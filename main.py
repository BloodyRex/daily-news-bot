#!/usr/bin/env python3
"""
RSS Subscriber - A simple RSS feed reader.
"""

import sys
import os
import time
import feedparser
import requests
from datetime import datetime

def read_feeds_file(filepath="feeds.txt"):
    """Read RSS feed URLs from a text file."""
    feeds = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    feeds.append(line)
    except FileNotFoundError:
        print(f"Feeds file '{filepath}' not found. Creating an example file.")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Add your RSS feed URLs here (one per line)\n")
            f.write("https://news.ycombinator.com/rss\n")
            f.write("https://www.reddit.com/r/python/.rss\n")
        feeds = ["https://news.ycombinator.com/rss", "https://www.reddit.com/r/python/.rss"]
    return feeds

def fetch_feed(url):
    """Fetch and parse an RSS feed."""
    try:
        # Use feedparser to parse the feed
        feed = feedparser.parse(url)
        if feed.bozo:
            print(f"Warning: Feed parsing error for {url}: {feed.bozo_exception}")
        return feed
    except Exception as e:
        print(f"Error fetching feed {url}: {e}")
        return None

def display_feed(feed, max_items=5):
    """Display feed entries."""
    if not feed or 'entries' not in feed:
        print("  No entries found.")
        return

    print(f"  Feed: {feed.feed.get('title', 'Unknown')}")
    print(f"  Link: {feed.feed.get('link', 'N/A')}")
    print(f"  Updated: {feed.feed.get('updated', 'N/A')}")
    print(f"  Entries ({len(feed.entries)}):")

    for i, entry in enumerate(feed.entries[:max_items]):
        published = entry.get('published', entry.get('updated', 'N/A'))
        print(f"    {i+1}. {entry.get('title', 'No title')}")
        print(f"       Link: {entry.get('link', 'N/A')}")
        print(f"       Published: {published}")
        print()

def main():
    print("RSS Subscriber - Fetching feeds...")
    print("=" * 50)

    feeds = read_feeds_file()
    if not feeds:
        print("No feeds to read. Please add URLs to feeds.txt.")
        return

    print(f"Found {len(feeds)} feed(s).")

    for i, url in enumerate(feeds):
        print(f"\n[{i+1}/{len(feeds)}] Fetching: {url}")
        feed = fetch_feed(url)
        if feed:
            display_feed(feed)
        time.sleep(1)  # Be polite to servers

    print("\nDone.")

if __name__ == "__main__":
    main()