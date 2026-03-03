---
name: realtime-stock
description: 实时股票行情获取与盘中监控。支持单只/批量股票实时行情查询、涨跌幅告警、支撑压力位突破提醒。使用场景：(1) 查询股票实时价格和涨跌幅 (2) 监控关注池异动 (3) 设置涨跌幅/成交量/支撑压力位告警。触发词："实时行情"、"股价"、"涨跌"、"监控"、"告警"、"支撑位"、"压力位"。
---

# 实时股票行情监控

## 快速开始

### 查询单只股票

```bash
python ~/.agents/skills/realtime-stock/scripts/fetch_quote.py 688195
```

### 查询多只股票

```bash
python ~/.agents/skills/realtime-stock/scripts/fetch_quote.py 688195,601138,300476
```

### 查询关注池

```bash
python ~/.agents/skills/realtime-stock/scripts/fetch_quote.py --watchlist
```

### JSON 格式输出

```bash
python ~/.agents/skills/realtime-stock/scripts/fetch_quote.py 688195 --json
```

---

## 盘中监控

### 检查一次（手动触发）

```bash
python ~/.agents/skills/realtime-stock/scripts/monitor.py --once
```

检查关注池，触发告警时发送到 Telegram。

### 持续监控（后台服务）

```bash
python ~/.agents/skills/realtime-stock/scripts/monitor.py --daemon
```

每分钟检查一次，持续运行。

### 测试模式（不发消息）

```bash
python ~/.agents/skills/realtime-stock/scripts/monitor.py --once --test
```

---

## 告警规则

在 `scripts/monitor_config.json` 中配置：

| 告警类型 | 默认值 | 说明 |
|---------|--------|------|
| price_change_up | 3.0% | 涨幅超过 3% 告警 |
| price_change_down | -3.0% | 跌幅超过 -3% 告警 |
| volume_ratio | 2.0 | 成交量超过 2 倍告警 |
| support_break | true | 跌破支撑位告警 |
| resistance_break | true | 突破压力位告警 |

---

## 配置支撑/压力位

编辑 `scripts/monitor_config.json`：

```json
{
  "support_levels": {
    "688195": 200.0,
    "300059": 22.0
  },
  "resistance_levels": {
    "688195": 225.0,
    "300059": 25.0
  }
}
```

---

## 数据源

**API**: 东方财富 push2 API
- 端点: `https://push2.eastmoney.com/api/qt/ulist.np/get`
- 延迟: 约 3-5 秒
- 免费: 无需登录/API Key

**返回字段**:
- f2: 最新价
- f3: 涨跌幅
- f5: 成交量
- f6: 成交额
- f12: 股票代码
- f14: 股票名称
- f15: 最高价
- f16: 最低价
- f17: 开盘价
- f18: 昨收价

---

## 集成到 cron

### 每分钟检查（仅交易时间）

```bash
# 编辑 crontab
crontab -e

# 添加（9:30-11:30, 13:00-15:00 每分钟检查）
*/1 9-11 * * 1-5 python ~/.agents/skills/realtime-stock/scripts/monitor.py --once
*/1 13-14 * * 1-5 python ~/.agents/skills/realtime-stock/scripts/monitor.py --once
```

### 使用 OpenClaw cron

```bash
openclaw cron add --name "stock-monitor-0930" --schedule "*/1 9-10 * * 1-5" --message "运行盘中监控" python ~/.agents/skills/realtime-stock/scripts/monitor.py --once
```

---

## 与其他工具配合

### 在个股分析中使用

分析个股时，先用此工具获取实时价格：

```bash
# 第1步：获取实时价格
quotes=$(python ~/.agents/skills/realtime-stock/scripts/fetch_quote.py 688195 --json)

# 第2步：解析价格
price=$(echo $quotes | jq -r '.[0].price')
pct=$(echo $quotes | jq -r '.[0].pct')

# 第3步：结合技术面分析
echo "当前价格: $price, 涨跌幅: $pct%"
```

### 在报告中使用

生成报告时，用 `--watchlist` 获取整个关注池的实时数据。

---

## 注意事项

1. **API 限制**: 东方财富 API 有频率限制，避免短时间内大量请求
2. **延迟**: 数据有 3-5 秒延迟，不是真正的"实时"
3. **交易时间**: 仅在交易时间（9:30-11:30, 13:00-15:00）有数据更新
4. **科创板**: 科创板股票（688开头）涨跌幅限制为 20%
5. **配置告警阈值**: 根据个人风险偏好调整 `monitor_config.json`

---

## 故障排查

### 无数据返回

检查股票代码是否正确，网络是否通畅。

### 告警未触发

1. 检查 `monitor_config.json` 配置
2. 使用 `--test` 模式查看日志
3. 确认 Telegram chat_id 正确

### 依赖缺失

```bash
pip install requests pyyaml
```
