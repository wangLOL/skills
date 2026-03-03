# Deep Stock Analysis - Tavily Search

## 配置要求

### 1. 安装依赖

```bash
pip install tavily-python
```

### 2. 获取 Tavily API Key

1. 访问 https://tavily.com
2. 注册账号
3. 在 Dashboard 获取 API Key

### 3. 配置环境变量

**方式一：临时设置**
```bash
export TAVILY_API_KEY="tvly-your-api-key"
```

**方式二：永久设置（推荐）**
```bash
echo 'export TAVILY_API_KEY="tvly-your-api-key"' >> ~/.zshrc
source ~/.zshrc
```

### 4. 测试

```bash
python3 ~/.agents/skills/deep-stock-analysis/scripts/tavily_search.py "江丰电子 2025年报"
```

---

## 使用方法

```bash
# 基础搜索
python3 tavily_search.py "搜索关键词"

# 指定结果数量
python3 tavily_search.py "搜索关键词" --max-results 10

# JSON 输出
python3 tavily_search.py "搜索关键词" --json
```

---

## 常用搜索模板

### 基础数据
```bash
python3 tavily_search.py "公司名 股价 今日收盘 2026年X月X日"
python3 tavily_search.py "公司名 2025年报 营收 净利润"
python3 tavily_search.py "公司名 业务结构 收入占比"
```

### 订单与上下游
```bash
python3 tavily_search.py "公司名 订单 2026"
python3 tavily_search.py "公司名 上游原料 价格 2026"
python3 tavily_search.py "公司名 下游需求 2026"
```

### 估值与二级市场
```bash
python3 tavily_search.py "公司名 PE 估值 2026"
python3 tavily_search.py "公司名 融资融券 主力资金 龙虎榜 2026"
```

### 公司动态
```bash
python3 tavily_search.py "公司名 2026年 1月 2月 新闻"
python3 tavily_search.py "公司名 高管 减持 公告"
```

---

## 为什么使用 Tavily？

1. **专为 AI 设计** - 返回结构化、高质量的结果
2. **实时数据** - 获取最新的网络数据
3. **答案摘要** - 自动生成摘要，节省时间
4. **来源追溯** - 每个结果都有明确的 URL 和来源

---

## 故障排除

### API Key 无效
```
Error: TAVILY_API_KEY environment variable not set
```
**解决**：确保已正确设置环境变量

### 依赖缺失
```
Error: tavily-python not installed
```
**解决**：运行 `pip install tavily-python`

### 搜索失败
```
Error: Tavily search failed: ...
```
**解决**：检查网络连接和 API Key 是否有效
