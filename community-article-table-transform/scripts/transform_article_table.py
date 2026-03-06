#!/usr/bin/env python3

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

PLACEHOLDER_HINT_RE = re.compile(r"^[（(].*[）)]$")
IMAGE_HINT_RE = re.compile(
    r"(kv|key visual|截图|截圖|图片|圖片|图|圖|海报|海報|portrait|screenshot|gif|sticker)",
    re.IGNORECASE,
)
TITLE_PREFIX = "Title - "
DISPLAY_NAME_TO_CODE = {
    "Chinese (Simplified)": "zh_cn",
    "English": "en",
    "German": "de",
    "French": "fr",
    "Chinese (Traditional)": "zh_tw",
    "Korean": "ko",
    "Japanese": "ja",
    "Indonesian": "id",
    "Spanish": "es",
    "Portuguese": "pt",
    "Russian": "ru",
    "Italian": "it",
    "Thai": "th",
    "Turkish": "tr",
    "Dutch": "nl",
    "Vietnamese": "vi",
    "Polish": "pl",
    "Swedish": "sv",
    "Arabic": "ar",
    "Malaysian": "my",
}
OUTPUT_LANGUAGE_ORDER = [
    "zh_cn",
    "en",
    "de",
    "fr",
    "zh_tw",
    "ko",
    "ja",
    "id",
    "es",
    "pt",
    "ru",
    "it",
    "th",
    "tr",
    "nl",
    "vi",
    "pl",
    "sv",
    "ar",
    "my",
]
SUPPORTED_TYPES = {
    "title",
    "text",
    "img",
    "youtube_url",
    "vote",
    "topic",
    "text_url",
    "coffee",
    "fungrowth_id",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Transform a multilingual article CSV into the fixed article upload table."
    )
    parser.add_argument("--input", required=True, help="Source multilingual CSV path")
    parser.add_argument(
        "--output",
        help="Output path for a single article (.csv or .xlsx)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory when --split-all is used. Files are written as .csv",
    )
    parser.add_argument("--config", required=True, help="Runtime config JSON path")
    parser.add_argument(
        "--article-index",
        type=int,
        default=1,
        help="1-based article index when source contains multiple articles",
    )
    parser.add_argument(
        "--split-all",
        action="store_true",
        help="Split all detected articles into separate CSV files",
    )
    return parser.parse_args()


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    config.setdefault("drop_leading_blank_after_title", True)
    config.setdefault("collapse_blank_runs", True)
    config.setdefault("default_placeholders", {})
    config.setdefault("special_rows", {})
    return config


def normalize_row(raw_row):
    normalized = {code: "" for code in OUTPUT_LANGUAGE_ORDER}
    for display_name, code in DISPLAY_NAME_TO_CODE.items():
        normalized[code] = (raw_row.get(display_name) or "").strip()
    normalized["_description"] = (raw_row.get("Description") or "").strip()
    return normalized


def row_has_content(row):
    return any((row.get(code) or "").strip() for code in OUTPUT_LANGUAGE_ORDER)


def strip_title_prefix(text):
    if text.startswith(TITLE_PREFIX):
        return text[len(TITLE_PREFIX) :].strip()
    return text


def normalize_title_row(row):
    return {code: strip_title_prefix(row.get(code, "")) for code in OUTPUT_LANGUAGE_ORDER}


def is_explicit_title_row(row):
    return any((row.get(code) or "").startswith(TITLE_PREFIX) for code in OUTPUT_LANGUAGE_ORDER)


def read_source_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [normalize_row(raw_row) for raw_row in reader]


def split_articles(rows):
    articles = []
    current = None

    for row in rows:
        if is_explicit_title_row(row):
            if current is not None:
                articles.append(current)
            current = {"title": normalize_title_row(row), "body": []}
            continue

        if current is None:
            if not row_has_content(row):
                continue
            current = {"title": row, "body": []}
            continue

        current["body"].append(row)

    if current is not None:
        articles.append(current)
    return articles


def looks_like_blank(row):
    return not row_has_content(row)


def row_label_text(row):
    zh_text = (row.get("zh_cn") or "").strip()
    if zh_text:
        return zh_text
    return (row.get("_description") or "").strip()


def looks_like_image_placeholder(row):
    label = row_label_text(row)
    if not label or not PLACEHOLDER_HINT_RE.match(label):
        return False
    return bool(IMAGE_HINT_RE.search(label))


def build_special_index(config):
    indexed = {}
    for row_type, entries in config.get("special_rows", {}).items():
        indexed[row_type] = []
        for entry in entries:
            indexed[row_type].append(
                {
                    "match": entry.get("match"),
                    "regex": entry.get("regex"),
                    "value": entry.get("value"),
                }
            )
    return indexed


def resolve_special_row(row, special_index):
    label = row_label_text(row)
    if not label:
        return None

    for row_type, entries in special_index.items():
        for entry in entries:
            exact_match = entry.get("match")
            regex_match = entry.get("regex")
            if exact_match and label == exact_match:
                return row_type, entry.get("value")
            if regex_match and re.search(regex_match, label):
                return row_type, entry.get("value")
    return None


def fixed_value_row(row_type, value):
    rendered = "" if value is None else value
    if isinstance(rendered, (dict, list)):
        rendered = json.dumps(rendered, ensure_ascii=False, separators=(",", ":"))
    rendered = str(rendered)
    row = {"type": row_type}
    for code in OUTPUT_LANGUAGE_ORDER:
        row[code] = rendered
    return row


def text_row(content):
    row = {"type": "text"}
    for code in OUTPUT_LANGUAGE_ORDER:
        row[code] = content.get(code, "")
    return row


def blank_text_row():
    return fixed_value_row("text", "<p>&nbsp;</p>")


def is_blank_text_output_row(row):
    if row.get("type") != "text":
        return False
    return all((row.get(code) or "") == "<p>&nbsp;</p>" for code in OUTPUT_LANGUAGE_ORDER)


def transform_article(article, config):
    rows = []
    warnings = []
    special_index = build_special_index(config)
    placeholders = config.get("default_placeholders", {})

    title = {"type": "title"}
    for code in OUTPUT_LANGUAGE_ORDER:
        title[code] = article["title"].get(code, "")
    rows.append(title)

    emitted_non_title = False
    previous_blank = False

    for source_row in article["body"]:
        special = resolve_special_row(source_row, special_index)
        if special:
            row_type, configured_value = special
            value = configured_value
            if value in (None, ""):
                value = placeholders.get(row_type, "")
                warnings.append(
                    f"{row_type} row matched but no concrete value configured: {row_label_text(source_row)}"
                )
            rows.append(fixed_value_row(row_type, value))
            previous_blank = False
            emitted_non_title = True
            continue

        if looks_like_image_placeholder(source_row):
            value = placeholders.get("img", "")
            warnings.append(
                f"Image placeholder converted heuristically and left unresolved: {row_label_text(source_row)}"
            )
            rows.append(fixed_value_row("img", value))
            previous_blank = False
            emitted_non_title = True
            continue

        if looks_like_blank(source_row):
            if not emitted_non_title and config.get("drop_leading_blank_after_title", True):
                continue
            if previous_blank and config.get("collapse_blank_runs", True):
                continue
            rows.append(blank_text_row())
            previous_blank = True
            emitted_non_title = True
            continue

        rows.append(text_row(source_row))
        previous_blank = False
        emitted_non_title = True

    while rows and is_blank_text_output_row(rows[-1]):
        rows.pop()

    return rows, warnings


def sanitize_filename(value):
    value = strip_title_prefix(value).strip() or "article"
    value = re.sub(r"[\\\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\\s+", "_", value)
    return value[:80]


def write_csv(path, rows):
    headers = ["type"] + OUTPUT_LANGUAGE_ORDER
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def column_name(index):
    letters = []
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def inline_string_cell(ref, value):
    escaped = escape(value)
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escaped}</t></is></c>'


def build_sheet_xml(headers, rows):
    all_rows = [headers]
    for row in rows:
        all_rows.append([row.get(header, "") for header in headers])

    xml_rows = []
    for row_index, values in enumerate(all_rows, start=1):
        cells = []
        for col_index, value in enumerate(values, start=1):
            if value == "":
                continue
            ref = f"{column_name(col_index)}{row_index}"
            cells.append(inline_string_cell(ref, str(value)))
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData>"
        "</worksheet>"
    )


def write_simple_xlsx(path, rows):
    headers = ["type"] + OUTPUT_LANGUAGE_ORDER
    sheet_xml = build_sheet_xml(headers, rows)

    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        "docProps/core.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Community Article Table</dc:title>
</cp:coreProperties>""",
        "docProps/app.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>""",
        "xl/worksheets/sheet1.xml": sheet_xml,
    }

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path, content in files.items():
            archive.writestr(relative_path, content)


def render_article(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix == ".xlsx":
        write_simple_xlsx(output_path, rows)
        return
    if suffix != ".csv":
        raise ValueError(f"Unsupported output format: {output_path.suffix}")
    write_csv(output_path, rows)


def validate_rows(rows):
    errors = []
    title_count = sum(1 for row in rows if row.get("type") == "title")
    if title_count != 1:
        errors.append(f"Expected exactly 1 title row, found {title_count}.")
    for index, row in enumerate(rows, start=1):
        row_type = row.get("type", "")
        if row_type not in SUPPORTED_TYPES:
            errors.append(f"Row {index} has unsupported type: {row_type}")
    return errors


def main():
    args = parse_args()
    config = load_config(args.config)
    source_rows = read_source_rows(args.input)
    articles = split_articles(source_rows)

    if not articles:
        print("No article content detected.", file=sys.stderr)
        return 1

    if args.split_all:
        if not args.output_dir:
            print("--output-dir is required with --split-all", file=sys.stderr)
            return 1
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        all_warnings = []
        for index, article in enumerate(articles, start=1):
            rows, warnings = transform_article(article, config)
            errors = validate_rows(rows)
            if errors:
                print(json.dumps({"article": index, "errors": errors}, ensure_ascii=False, indent=2), file=sys.stderr)
                return 1
            filename = f"{index:02d}_{sanitize_filename(article['title'].get('zh_cn') or article['title'].get('en') or 'article')}.csv"
            write_csv(output_dir / filename, rows)
            for warning in warnings:
                all_warnings.append(f"[article {index}] {warning}")
        print(json.dumps({"articles": len(articles), "warnings": all_warnings}, ensure_ascii=False, indent=2))
        return 0

    if not args.output:
        print("--output is required for single-article mode", file=sys.stderr)
        return 1
    if args.article_index < 1 or args.article_index > len(articles):
        print(f"article-index out of range: 1..{len(articles)}", file=sys.stderr)
        return 1

    article = articles[args.article_index - 1]
    rows, warnings = transform_article(article, config)
    errors = validate_rows(rows)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    render_article(rows, Path(args.output))
    print(
        json.dumps(
            {
                "articles_detected": len(articles),
                "selected_article": args.article_index,
                "output": str(Path(args.output)),
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
