#!/usr/bin/env python3
"""
Twitter AI 监控 - 多源整合版

用法：
  python3 twitter_multi_source.py --hours 12
  python3 twitter_multi_source.py --start "2026-03-01 00:00" --end "2026-03-02 00:00"
"""

import asyncio
import json
import re
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import requests

# 配置
STATE_FILE = Path(__file__).parent / "twitter_state.json"
TELEGRAM_TARGET = "1689599511"
ZHIPU_API_KEY = "0c30230e83324adb8e36f7a4763d0e6d.MW9cJ41DI0fzOtjW"
TAVILY_API_KEY = "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"

# 监控账号
ACCOUNTS = [
    {"username": "AnthropicAI", "name": "Anthropic", "category": "anthropic"},
    {"username": "claudeai", "name": "Claude", "category": "anthropic"},
    {"username": "elonmusk", "name": "Elon Musk", "category": "xai"},
    {"username": "OpenAI", "name": "OpenAI", "category": "openai"},
    {"username": "sama", "name": "Sam Altman", "category": "openai"},
]

# AI 功能/技术相关关键词（只筛选与 AI 功能和技术相关的内容）
AI_KEYWORDS = [
    # 模型和产品
    "Claude", "Grok", "GPT", "ChatGPT", "DALL-E", "Sora", "Opus", "Sonnet", "Haiku",
    "o1", "o3", "o4", "GPT-4", "GPT-5", "Reasoning",
    # AI 功能
    "AI", "agent", "AGI", "LLM", "multimodal", "vision", "voice",
    "code", "coding", "reasoning", "thinking", "memory",
    "API", "SDK", "CLI", "tool", "function calling",
    # 技术术语
    "model", "training", "fine-tuning", "RLHF", "inference",
    "release", "update", "launch", "announce", "new feature",
    "safety", "alignment", "benchmark", "performance",
    # 特定产品
    "xAI", "OpenAI", "Anthropic", "Remote Control", "Cowork",
]


def parse_time_args(args):
    """解析时间参数"""
    if args.start and args.end:
        # 指定时间范围
        start = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
        end = datetime.strptime(args.end, "%Y-%m-%d %H:%M")
        hours = int((end - start).total_seconds() / 3600)
        window_name = f"{start.strftime('%Y-%m-%d %H:%M')} 至 {end.strftime('%Y-%m-%d %H:%M')}"
    elif args.hours:
        # 指定小时数
        hours = args.hours
        end = datetime.now()
        start = end - timedelta(hours=hours)
        window_name = f"过去{hours}小时"
    else:
        # 默认12小时
        hours = 12
        end = datetime.now()
        start = end - timedelta(hours=hours)
        window_name = f"过去{hours}小时"
    
    # Tavily 搜索天数（向上取整）
    search_days = max(1, (hours + 23) // 24)
    
    return window_name, search_days, start, end


def is_in_time_range(tweet, start_time, end_time):
    """检查推文是否在时间范围内"""
    if not tweet.get('timestamp'):
        # 没有时间戳的保留（可能是非 Twitter 链接）
        return True
    
    try:
        tweet_time = datetime.strptime(tweet['timestamp'], '%Y-%m-%d %H:%M')
        return start_time <= tweet_time <= end_time
    except:
        return True


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"pushed": {}, "last_summary": None}


def save_state(state):
    state["last_summary"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def is_ai_related(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in AI_KEYWORDS)


def normalize_text(text):
    """标准化文本用于去重"""
    text = re.sub(r'@\w+', '', text)
    text = ' '.join(text.split())
    return text[:100].lower()


def extract_timestamp_from_url(url):
    """从 Twitter URL 中提取时间戳（Snowflake ID）"""
    # Twitter URL 格式：https://twitter.com/username/status/TWEET_ID
    # Snowflake ID 前 41 位是时间戳（从 2010-11-04 01:42:54 UTC 开始的毫秒数）
    match = re.search(r'/status/(\d+)', url)
    if match:
        tweet_id = int(match.group(1))
        # 提取时间戳（前 41 位）
        timestamp_ms = (tweet_id >> 22) + 1288834974657  # Twitter epoch: 2010-11-04 01:42:54 UTC
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime('%Y-%m-%d %H:%M')
    return ""


# ========== 方式1: Playwright ==========
async def fetch_via_playwright(account):
    """Playwright 直连 Twitter"""
    from playwright.async_api import async_playwright
    
    tweets = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,  # 改为无头模式，避免 cron 超时
                args=['--disable-blink-features=AutomationControlled']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            url = f"https://twitter.com/{account['username']}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)  # 减少等待时间：8秒→3秒
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1)  # 减少等待时间：3秒→1秒
            
            tweet_elements = await page.query_selector_all('article[data-testid="tweet"]')
            
            for tweet_el in tweet_elements[:10]:
                try:
                    link_el = await tweet_el.query_selector('a[href*="/status/"]')
                    text_el = await tweet_el.query_selector('[data-testid="tweetText"]')
                    
                    if text_el:
                        text = await text_el.inner_text()
                        if text:
                            tweets.append({
                                'text': text,
                                'source': 'playwright',
                                'account': account['name'],
                                'category': account.get('category', 'other'),
                            })
                except:
                    pass
            
            await browser.close()
            
    except Exception as e:
        print(f"  Playwright @{account['username']} 失败: {e}")
    
    return tweets


# ========== 方式2: Tavily 搜索 ==========
def fetch_via_search(account, search_days=1):
    """通过 Tavily 搜索获取"""
    tweets = []
    
    queries = [
        f"from:{account['username']} AI OR Claude OR Grok OR GPT OR model OR release",
        f"{account['name']} AI new feature update site:twitter.com",
    ]
    
    for query in queries:
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "days": search_days,
                },
                timeout=30,
            )
            
            if response.status_code == 200:
                results = response.json().get("results", [])
                for item in results:
                    url = item.get("url", "")
                    if "twitter.com" in url or "x.com" in url:
                        text = item.get("content", "")
                        # 从 URL 提取时间戳
                        timestamp = extract_timestamp_from_url(url)
                        if text:
                            tweets.append({
                                'text': text,
                                'source': 'search',
                                'account': account['name'],
                                'category': account.get('category', 'other'),
                                'url': url,
                                'timestamp': timestamp,
                            })
        except Exception as e:
            print(f"  搜索失败: {e}")
    
    return tweets


# ========== 汇总去重 ==========
def merge_and_dedupe(all_tweets):
    """合并去重"""
    seen = set()
    unique_tweets = []
    
    for tweet in all_tweets:
        fingerprint = normalize_text(tweet['text'])
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique_tweets.append(tweet)
    
    return unique_tweets


# ========== 翻译汇总 ==========
def translate_and_summarize(all_tweets, state, window_name):
    """翻译并生成中文摘要"""
    
    # 过滤 AI 功能技术相关（严格模式）
    ai_tweets = [t for t in all_tweets if is_ai_related(t['text'])]
    
    # 不过滤已推送，直接按时间窗口来
    if not ai_tweets:
        return None
    
    # 按账号分组
    by_account = defaultdict(list)
    for t in ai_tweets:
        by_account[t['account']].append(t)
    
    # 准备翻译内容（包含时间戳和 URL）
    input_text = ""
    for account, tweets in by_account.items():
        input_text += f"\n【{account}】\n"
        for tweet in tweets:  # 不限制条数
            # 添加时间戳和 URL
            timestamp = tweet.get('timestamp', '')
            url = tweet.get('url', '')
            input_text += f"- {tweet['text']}"
            if timestamp:
                input_text += f" | 时间: {timestamp}"
            if url:
                input_text += f" | URL: {url}"
            input_text += "\n"
    
    prompt = f"""请将以下英文内容翻译成中文，并整理成结构化的 AI 动态摘要。

**重要：只关注与 AI 功能、技术相关的内容，包括：**
- AI 功能更新、新模型发布
- 技术突破、基准测试
- 产品路线图、功能演示
- API/SDK 更新、开发者工具

**必须忽略以下内容：**
- 公司收购、人事变动、融资
- 纯政治内容
- 加密货币价格讨论
- 纯个人观点/生活分享

时间段：{window_name}

内容（每条包含时间戳和 URL）：
{input_text}

请按以下格式输出：

🤖 **AI 动态速递（{window_name}）**

---

**📦 Anthropic / Claude**
1. [标题文字](URL) (YYYY-MM-DD HH:MM)
   • [补充说明或背景，可选]
2. ...

---

**🚀 xAI / Grok (Elon Musk)**
1. [标题文字](URL) (YYYY-MM-DD HH:MM)
   • [补充说明或背景，可选]
2. ...

---

**🔮 OpenAI / Sam Altman**
1. [标题文字](URL) (YYYY-MM-DD HH:MM)
   • [补充说明或背景，可选]
2. ...

---

**📌 总结：**[一句话总结核心趋势，30-50字]

要求：
- 只保留 AI 功能技术相关内容
- 忽略公司收购、人事变动、融资等商业内容
- 条数不限制，全部展示
- **每条必须包含：超链接标题 + 时间戳（YYYY-MM-DD HH:MM格式）**
- 如果没有 URL 或时间，就省略对应部分
- 保持简洁，突出重点
- 如果某分类没有内容就跳过
- 不要在每条前面加 [主题] 标签，直接写内容
"""

    try:
        # 使用 OpenClaw 主模型（zai/glm-5）
        result = subprocess.run(
            [
                "openclaw", "agent",
                "--agent", "main",
                "--message", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=120,  # 增加到 120 秒
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"GLM-5 调用错误: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"翻译失败: {e}")
        return None


def send_to_telegram(message):
    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", TELEGRAM_TARGET,
        "--message", message,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False


async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Twitter AI 监控')
    parser.add_argument('--hours', type=int, help='查询过去N小时')
    parser.add_argument('--start', type=str, help='开始时间 (YYYY-MM-DD HH:MM)')
    parser.add_argument('--end', type=str, help='结束时间 (YYYY-MM-DD HH:MM)')
    args = parser.parse_args()
    
    # 获取时间窗口
    window_name, search_days, start_time, end_time = parse_time_args(args)
    
    print(f"=== Twitter AI 监控 ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    print(f"查询时段: {window_name}")
    print(f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    state = load_state()
    all_tweets = []
    
    for account in ACCOUNTS:
        print(f"\n抓取 @{account['username']}...")
        
        # 方式1: Playwright
        print("  [1/2] Playwright...")
        tweets1 = await fetch_via_playwright(account)
        print(f"       找到 {len(tweets1)} 条")
        all_tweets.extend(tweets1)
        
        # 方式2: Tavily 搜索
        print("  [2/2] Tavily 搜索...")
        tweets2 = fetch_via_search(account, search_days)
        print(f"       找到 {len(tweets2)} 条")
        all_tweets.extend(tweets2)
    
    # 合并去重
    print(f"\n总计: {len(all_tweets)} 条，去重后...")
    unique_tweets = merge_and_dedupe(all_tweets)
    print(f"去重后: {len(unique_tweets)} 条")
    
    # 过滤时间范围
    print(f"\n过滤时间范围（{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}）...")
    filtered_tweets = [t for t in unique_tweets if is_in_time_range(t, start_time, end_time)]
    print(f"过滤后: {len(filtered_tweets)} 条")

    if not filtered_tweets:
        print("⚠️ 时间过滤后为空，没有符合时间范围的推文")
        # 发送空结果通知
        empty_msg = f"🤖 AI 动态速递\n\n⏰ 时间范围：{window_name}\n\n📭 没有找到符合时间范围的 AI 相关动态"
        send_to_telegram(empty_msg)
        return
    
    # 翻译汇总
    print("\n生成中文汇总...")
    summary = translate_and_summarize(filtered_tweets, state, window_name)
    
    if not summary:
        summary = f"🤖 AI 动态速递\n\n📭 {window_name} 没有新的 AI 相关动态"
    else:
        # 在标题中显示时间范围
        summary = summary.replace(
            f"🤖 **AI 动态速递（{window_name}）**",
            f"🤖 **AI 动态速递**\n\n⏰ 时间范围：{window_name}"
        )
    
    # 发送
    print("发送汇总...")
    if send_to_telegram(summary):
        print("✓ 已发送")
        
        # 清理旧状态
        if len(state.get('pushed', {})) > 500:
            oldest = list(state['pushed'].keys())[:-500]
            for k in oldest:
                del state['pushed'][k]
        
        save_state(state)
    else:
        print("✗ 发送失败")
    
    print(f"\n=== 完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
