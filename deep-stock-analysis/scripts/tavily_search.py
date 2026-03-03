#!/usr/bin/env python3
"""
Tavily Search Script for Deep Stock Analysis
Usage: python3 tavily_search.py "search query" [--max-results 5]
"""

import os
import sys
import json
from datetime import datetime

try:
    from tavily import TavilyClient
except ImportError:
    print("Error: tavily-python not installed. Run: pip install tavily-python", file=sys.stderr)
    sys.exit(1)

def search(query: str, max_results: int = 5) -> dict:
    """Perform Tavily search and return results."""
    api_key = os.environ.get("TAVILY_API_KEY")
    
    if not api_key:
        print("Error: TAVILY_API_KEY environment variable not set", file=sys.stderr)
        print("Get your API key at: https://tavily.com", file=sys.stderr)
        sys.exit(1)
    
    client = TavilyClient(api_key=api_key)
    
    try:
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_domains=[],
            exclude_domains=[],
            include_answer=True,
            include_raw_content=False,
        )
        return response
    except Exception as e:
        print(f"Error: Tavily search failed: {e}", file=sys.stderr)
        sys.exit(1)

def format_output(response: dict) -> str:
    """Format search results for readability."""
    output = []
    output.append(f"搜索时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("=" * 60)
    
    # Answer
    if response.get("answer"):
        output.append("\n【摘要】")
        output.append(response["answer"])
    
    # Results
    output.append(f"\n【搜索结果】共 {len(response.get('results', []))} 条")
    output.append("-" * 60)
    
    for i, result in enumerate(response.get("results", []), 1):
        output.append(f"\n{i}. {result.get('title', 'N/A')}")
        output.append(f"   URL: {result.get('url', 'N/A')}")
        output.append(f"   来源: {result.get('source', 'N/A')}")
        
        content = result.get('content', '')
        if len(content) > 300:
            content = content[:300] + "..."
        output.append(f"   内容: {content}")
        
        if result.get('published_date'):
            output.append(f"   发布时间: {result['published_date']}")
    
    return "\n".join(output)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tavily_search.py \"search query\" [--max-results N]", file=sys.stderr)
        sys.exit(1)
    
    query = sys.argv[1]
    max_results = 5
    
    # Parse arguments
    args = sys.argv[2:]
    if "--max-results" in args:
        idx = args.index("--max-results")
        if idx + 1 < len(args):
            try:
                max_results = int(args[idx + 1])
            except ValueError:
                pass
    
    # Also support JSON output
    json_output = "--json" in args
    
    response = search(query, max_results)
    
    if json_output:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(format_output(response))

if __name__ == "__main__":
    main()
