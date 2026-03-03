#!/usr/bin/env python3
"""盘中监控报告生成器"""
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from fetch_quote import fetch_quotes, load_watchlist

def generate_report():
    """生成监控报告"""
    codes = load_watchlist()
    if not codes:
        print("关注池为空")
        return
    
    quotes = fetch_quotes(codes)
    if not quotes:
        print("获取行情失败")
        return
    
    # 按涨跌幅排序
    quotes.sort(key=lambda x: x.get('pct', 0), reverse=True)
    
    # 分类
    strong = [q for q in quotes if q.get('pct', 0) >= 2]
    weak = [q for q in quotes if q.get('pct', 0) <= -2]
    normal = [q for q in quotes if -2 < q.get('pct', 0) < 2]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"📊 盘中监控报告 ({timestamp})\n")
    
    print(f"关注池: {len(codes)} 只股票\n")
    
    if strong:
        print("🚀 强势股（涨幅 ≥ 2%）:")
        for q in strong:
            print(f"  {q['code']} {q['name']} {q['pct']:+.2f}% 价格:{q['price']:.2f}")
        print()
    
    if weak:
        print("⚠️ 弱势股（跌幅 ≤ -2%）:")
        for q in weak:
            print(f"  {q['code']} {q['name']} {q['pct']:+.2f}% 价格:{q['price']:.2f}")
        print()
    
    print(f"📊 平稳股（-2% < 涨跌 < 2%）: {len(normal)} 只\n")
    
    # 统计
    up = len([q for q in quotes if q.get('pct', 0) > 0])
    down = len([q for q in quotes if q.get('pct', 0) < 0])
    flat = len(quotes) - up - down
    
    print(f"📈 上涨: {up} 只  📉 下跌: {down} 只  ➡️ 平盘: {flat} 只")

if __name__ == "__main__":
    generate_report()
