---
name: community-article-table-transform
description: Convert one community article table into another table with a fixed upload schema. Use when the user wants to transform a multilingual article CSV/spreadsheet into a finished delivery table, upload table, article xlsx/csv, or “表格A转表格C”, including adding a type column, renaming language headers to codes, reordering language columns, preserving content rows, and handling placeholders like blank lines, image rows, and topic rows.
---

# Community Article Table Transform

Use this skill when the input is a multilingual article CSV and the target is the fixed community article upload table.

Do not read the runtime template workbook again. This skill already bakes in the fixed output schema, supported `type` values, language-code mapping, and row-conversion rules.

## What is fixed in this skill

- Output columns are fixed:
  - `type, zh_cn, en, de, fr, zh_tw, ko, ja, id, es, pt, ru, it, th, tr, nl, vi, pl, sv, ar, my`
- Supported `type` values are fixed:
  - `title, text, img, youtube_url, vote, topic, text_url, coffee, fungrowth_id`
- Language display names are normalized to language codes.
- Source rows are split into one or more article blocks.
- Blank rows, image placeholders, and special rows are normalized with deterministic rules.
- `Description` is not blindly discarded. If it contains an image hint like `（...图）` or `（...示意图）`, it can become an `img` placeholder row.

## What still needs runtime input

- The source multilingual CSV.
- Optional metadata for rows that cannot be derived from text alone:
  - `img`
  - `topic`
  - `vote`
  - `youtube_url`
  - `text_url`
  - `coffee`
  - `fungrowth_id`

If metadata is missing, keep placeholders or blanks and surface warnings. Do not invent IDs.

## Files

- `scripts/transform_article_table.py`
  - Single entrypoint.
  - Converts source CSV into the fixed output table.
  - Includes the fixed schema, row rules, and basic validation.
  - Can write `.csv`.
  - Can also write a simple single-sheet `.xlsx` for single-article output.
- `assets/run-config.example.json`
  - Runtime config shape.

## Default workflow

1. Copy `assets/run-config.example.json` and fill only the metadata you know.
2. Run the transformer:

```bash
python3 skills/community-article-table-transform/scripts/transform_article_table.py \
  --input "/path/source.csv" \
  --output "/path/output.csv" \
  --config "/path/run-config.json"
```

3. If the source file contains multiple articles, use:

```bash
python3 skills/community-article-table-transform/scripts/transform_article_table.py \
  --input "/path/source.csv" \
  --output-dir "/path/out-dir" \
  --config "/path/run-config.json" \
  --split-all
```

## Non-negotiable rules

- The first output column is always `type`.
- Language columns must use fixed language codes, not display names.
- Language columns must be emitted in the fixed order defined by this skill.
- `title` must exist exactly once per output file.
- Source blank rows are normalized to `<p>&nbsp;</p>`.
- Rows with only `Description` content must still be inspected before dropping them.
- Missing language content stays blank. Do not backfill from English.
- Unknown special rows must not be silently transformed into fake IDs.
