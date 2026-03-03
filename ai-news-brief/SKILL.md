---
name: ai-news-brief
description: 监控 AI 相关推文并生成中文结构化摘要。支持 Anthropic/Claude、xAI/Grok、OpenAI/Sam Altman 等账号。使用场景：(1) 整理 AI 动态速递 (2) 翻译 AI 推文 (3) 生成分类报告。触发词：AI速递、AI动态、推文汇总、twitter监控。
---

# AI 动态速递

## 功能概述

监控 AI 公司和领军人物的 Twitter 动态，筛选 AI 功能技术相关内容，翻译成中文结构化摘要。

## 使用方式

### 1. 指定时间范围（推荐）

```bash
# 查询过去12小时
python3 ~/clawd/scripts/twitter_multi_source.py --hours 12

# 查询过去24小时
python3 ~/clawd/scripts/twitter_multi_source.py --hours 24

# 查询指定时间范围
python3 ~/clawd/scripts/twitter_multi_source.py --start "2026-03-01 00:00" --end "2026-03-02 00:00"
```

### 2. 默认查询

```bash
# 不指定参数，默认查询过去12小时
python3 ~/clawd/scripts/twitter_multi_source.py
```

### 3. 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--hours` | 查询过去N小时 | `--hours 12` |
| `--start` | 开始时间 | `--start "2026-03-01 00:00"` |
| `--end` | 结束时间 | `--end "2026-03-02 00:00"` |

**注意**：`--start` 和 `--end` 必须同时使用。

## 监控账号

- @AnthropicAI (Anthropic)
- @claudeai (Claude)
- @elonmusk (xAI)
- @OpenAI (OpenAI)
- @sama (Sam Altman)

## 输出格式

```markdown
🤖 **AI 动态速递**

⏰ 时间范围：过去12小时

---

**📦 Anthropic / Claude**
1. [Claude 新增实时编写代码能力](https://twitter.com/...) (2026-03-03 14:23)
   • 开启功能预览：claude.ai/new?fp=1

---

**🚀 xAI / Grok (Elon Musk)**
1. [Grok 新增 6 秒视频生成功能](https://twitter.com/...) (2026-03-03 13:45)

---

**🔮 OpenAI / Sam Altman**
1. [ChatGPT 记忆功能大幅改进](https://twitter.com/...) (2026-03-03 12:30)
   • 可引用所有历史对话

---

**📌 总结：** AI 助手向多模态、自动化和开发者工具深度演进，实时界面生成和多模态理解成新焦点。
```

## 筛选规则

### 保留内容（AI 功能技术）
- AI 功能更新、新模型发布
- 技术突破、基准测试
- 产品路线图、功能演示
- API/SDK 更新、开发者工具

### 忽略内容
- 公司收购、人事变动、融资
- 纯政治内容
- 加密货币价格讨论
- 纯个人观点/生活分享

## 配置文件

- **主脚本**：`~/clawd/scripts/twitter_multi_source.py`
- **状态文件**：`~/clawd/scripts/twitter_state.json`
- **API 密钥**：脚本内置（Tavily、智谱）

## 故障排查

### Playwright 抓取失败
- 已改为 headless 模式
- 可能被 Twitter 检测，依赖 Tavily 搜索补充

### Tavily 搜索为空
- 检查 API 密钥是否过期
- 查看日志：`python3 ~/clawd/scripts/twitter_multi_source.py 2>&1 | tee twitter.log`

### 输出格式错误
- 检查翻译提示词（第 260 行）
- 确保包含时间和 URL 信息

## 相关文档

- **关键词列表**：见 `references/keywords.md`
- **输出模板**：见 `references/output-template.md`

## 定时任务（由调度层管理）

Skill 不包含定时逻辑。如需定时执行，请配置 cron：

```bash
# 09:00 - 早班（过去24小时）
0 9 * * * python3 ~/clawd/scripts/twitter_multi_source.py --hours 24

# 15:00 - 午班（过去12小时）
0 15 * * * python3 ~/clawd/scripts/twitter_multi_source.py --hours 12

# 00:00 - 晚班（过去12小时）
0 0 * * * python3 ~/clawd/scripts/twitter_multi_source.py --hours 12
```
