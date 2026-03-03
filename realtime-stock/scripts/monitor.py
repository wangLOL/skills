#!/usr/bin/env python3
"""
盘中监控脚本 - 监控关注池并触发告警

用法:
  python monitor.py --once           # 检查一次并发送告警
  python monitor.py --daemon         # 持续监控（每分钟检查一次）
  python monitor.py --test           # 测试模式（不发消息）
"""

import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 导入 fetch_quote 模块
sys.path.insert(0, str(Path(__file__).parent))
from fetch_quote import fetch_quotes, load_watchlist

# 配置文件路径
MONITOR_CONFIG = Path(__file__).parent / "monitor_config.json"
STATE_FILE = Path(__file__).parent / "monitor_state.json"

# 东方财富 API
EASTMONEY_QUOTE = "https://push2.eastmoney.com/api/qt/ulist.np/get"


def load_config() -> Dict[str, Any]:
    """加载监控配置"""
    if not MONITOR_CONFIG.exists():
        # 默认配置
        default = {
            "watchlist": [],
            "alerts": {
                "price_change_up": 3.0,      # 涨幅超过 3% 告警
                "price_change_down": -3.0,   # 跌幅超过 -3% 告警
                "volume_ratio": 2.0,         # 成交量超过 2 倍告警
                "support_break": True,       # 跌破支撑位告警
                "resistance_break": True,    # 突破压力位告警
            },
            "support_levels": {},            # {code: price}
            "resistance_levels": {},         # {code: price}
            "telegram": {
                "enabled": True,
                "chat_id": "-1003828603322",  # 炒股群
            }
        }
        return default
    
    with open(MONITOR_CONFIG, "r") as f:
        return json.load(f)


def load_state() -> Dict[str, Any]:
    """加载状态文件"""
    if not STATE_FILE.exists():
        return {"last_alerts": {}, "last_prices": {}}
    
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]):
    """保存状态文件"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram_alert(message: str, chat_id: str) -> bool:
    """发送 Telegram 告警"""
    try:
        # 使用 clawdbot CLI
        import subprocess
        result = subprocess.run(
            [
                "clawdbot", "message", "send",
                "--channel", "telegram",
                "--target", chat_id,
                "--message", message
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"发送告警失败: {e}", file=sys.stderr)
        return False


def check_alerts(quotes: List[Dict], config: Dict, state: Dict) -> List[str]:
    """检查触发条件"""
    alerts = []
    alert_config = config.get("alerts", {})
    support_levels = config.get("support_levels", {})
    resistance_levels = config.get("resistance_levels", {})
    last_prices = state.get("last_prices", {})
    
    for q in quotes:
        code = q["code"]
        name = q["name"]
        price = q["price"]
        pct = q["pct"]
        
        # 1. 涨跌幅告警
        threshold_up = alert_config.get("price_change_up", 3.0)
        threshold_down = alert_config.get("price_change_down", -3.0)
        
        if pct >= threshold_up:
            alerts.append(f"🚀 {name}({code}) 涨幅 {pct:+.2f}%，超过阈值 {threshold_up}%")
        elif pct <= threshold_down:
            alerts.append(f"⚠️ {name}({code}) 跌幅 {pct:+.2f}%，超过阈值 {threshold_down}%")
        
        # 2. 支撑位告警
        if alert_config.get("support_break", True) and code in support_levels:
            support = support_levels[code]
            last_price = last_prices.get(code, 0)
            
            if last_price >= support and price < support:
                alerts.append(f"🔴 {name}({code}) 跌破支撑位 {support:.2f}，当前价 {price:.2f}")
        
        # 3. 压力位告警
        if alert_config.get("resistance_break", True) and code in resistance_levels:
            resistance = resistance_levels[code]
            last_price = last_prices.get(code, 0)
            
            if last_price <= resistance and price > resistance:
                alerts.append(f"🟢 {name}({code}) 突破压力位 {resistance:.2f}，当前价 {price:.2f}")
        
        # 更新最后价格
        last_prices[code] = price
    
    # 更新状态
    state["last_prices"] = last_prices
    
    return alerts


def run_once(test_mode: bool = False):
    """运行一次检查"""
    config = load_config()
    state = load_state()
    
    # 获取关注池
    codes = config.get("watchlist") or load_watchlist()
    if not codes:
        print("关注池为空", file=sys.stderr)
        return
    
    # 获取实时行情
    quotes = fetch_quotes(codes)
    if not quotes:
        print("获取行情失败", file=sys.stderr)
        return
    
    # 检查告警
    alerts = check_alerts(quotes, config, state)
    
    # 发送告警
    if alerts:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"📊 盘中监控 ({timestamp})\n\n" + "\n".join(alerts)
        
        if test_mode:
            print(message)
        else:
            telegram_config = config.get("telegram", {})
            if telegram_config.get("enabled", True):
                chat_id = telegram_config.get("chat_id", "-1003828603322")
                if send_telegram_alert(message, chat_id):
                    print(f"已发送 {len(alerts)} 条告警")
                else:
                    print("发送失败", file=sys.stderr)
    else:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 无触发告警")
    
    # 保存状态
    save_state(state)


def run_daemon(test_mode: bool = False):
    """持续监控"""
    print("开始盘中监控（每分钟检查一次）...")
    print("按 Ctrl+C 停止")
    
    while True:
        try:
            run_once(test_mode)
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n监控已停止")
            break
        except Exception as e:
            print(f"错误: {e}", file=sys.stderr)
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="盘中监控")
    parser.add_argument("--once", action="store_true", help="检查一次")
    parser.add_argument("--daemon", action="store_true", help="持续监控")
    parser.add_argument("--test", action="store_true", help="测试模式（不发消息）")
    
    args = parser.parse_args()
    
    if args.daemon:
        run_daemon(args.test)
    else:
        run_once(args.test)


if __name__ == "__main__":
    main()
