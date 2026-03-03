#!/usr/bin/env python3
"""
实时行情获取脚本 - 基于东方财富 push2 API

用法:
  python fetch_quote.py 688195              # 单只股票
  python fetch_quote.py 688195,601138,300476  # 多只股票
  python fetch_quote.py --watchlist          # 使用关注池
"""

import sys
import json
import requests
from pathlib import Path
from typing import List, Dict, Any

# 东方财富实时行情 API
EASTMONEY_QUOTE = "https://push2.eastmoney.com/api/qt/ulist.np/get"


def secid_for_cn_stock(code: str) -> str:
    """将 A 股代码转换为东方财富 secid 格式"""
    code = str(code).strip()
    if code.startswith("6"):
        return f"1.{code}"
    if code.startswith(("0", "3")):
        return f"0.{code}"
    return f"1.{code}"


def fetch_quotes(codes: List[str]) -> List[Dict[str, Any]]:
    """获取实时行情"""
    if not codes:
        return []
    
    fields = "f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18"
    secids = [secid_for_cn_stock(c) for c in codes]
    
    params = {
        "fltt": 2,
        "invt": 2,
        "fields": fields,
        "secids": ",".join(secids),
        "pn": 1,
        "pz": len(secids),
        "np": 1,
        "fid": "f3",
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        r = requests.get(EASTMONEY_QUOTE, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        diff = (((data or {}).get("data") or {}).get("diff")) or []
        m = {str(x.get("f12", "")).strip(): x for x in diff}
        
        result = []
        for code in codes:
            if code in m:
                q = m[code]
                def safe_float(val, default=0):
                    """安全转换为浮点数"""
                    if val is None or val == "" or val == "-":
                        return default
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return default
                
                result.append({
                    "code": code,
                    "name": q.get("f14", ""),
                    "price": safe_float(q.get("f2")),
                    "pct": safe_float(q.get("f3")),
                    "open": safe_float(q.get("f17")),
                    "high": safe_float(q.get("f15")),
                    "low": safe_float(q.get("f16")),
                    "prev_close": safe_float(q.get("f18")),
                    "volume": safe_float(q.get("f5")),
                    "amount": safe_float(q.get("f6")),
                })
        return result
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return []


def load_watchlist() -> List[str]:
    """从配置文件加载关注池"""
    # 尝试多个可能的路径
    possible_paths = [
        Path(__file__).parent.parent.parent.parent / "clawd/stock_monitor/config.yaml",
        Path.home() / "clawd/stock_monitor/config.yaml",
        Path("/Users/EricLu/clawd/stock_monitor/config.yaml"),
    ]
    
    config_path = None
    for p in possible_paths:
        if p.exists():
            config_path = p
            break
    
    if not config_path:
        return []
    
    try:
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config.get("watchlist", [])
    except Exception as e:
        print(f"加载关注池失败: {e}", file=sys.stderr)
        return []


def format_output(quotes: List[Dict[str, Any]], format_type: str = "table") -> str:
    """格式化输出"""
    if not quotes:
        return "无数据"
    
    if format_type == "json":
        return json.dumps(quotes, ensure_ascii=False, indent=2)
    
    # 表格格式
    lines = []
    lines.append(f"{'代码':<8} {'名称':<10} {'最新价':>8} {'涨跌幅':>8} {'最高':>8} {'最低':>8} {'成交额(亿)':>10}")
    lines.append("-" * 80)
    
    for q in quotes:
        code = q["code"]
        name = q["name"][:8]
        try:
            price = float(q["price"]) if q["price"] and q["price"] != "-" else 0
            pct = float(q["pct"]) if q["pct"] and q["pct"] != "-" else 0
            high = float(q["high"]) if q["high"] and q["high"] != "-" else 0
            low = float(q["low"]) if q["low"] and q["low"] != "-" else 0
            amount = float(q["amount"]) / 100000000 if q["amount"] and q["amount"] != "-" else 0
        except (ValueError, TypeError):
            price = pct = high = low = amount = 0
        
        lines.append(f"{code:<8} {name:<10} {price:>8.2f} {pct:>+7.2f}% {high:>8.2f} {low:>8.2f} {amount:>10.2f}")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    # 解析参数
    arg = sys.argv[1]
    format_type = "table"
    
    if "--json" in sys.argv:
        format_type = "json"
        sys.argv.remove("--json")
    
    # 获取股票代码列表
    if arg == "--watchlist":
        codes = load_watchlist()
        if not codes:
            print("关注池为空", file=sys.stderr)
            sys.exit(1)
    else:
        codes = [c.strip() for c in arg.split(",")]
    
    # 获取行情
    quotes = fetch_quotes(codes)
    
    # 输出
    print(format_output(quotes, format_type))


if __name__ == "__main__":
    main()
