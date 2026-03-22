# Samples Schema

- 文件用途：告诉你如何直接填写 `data/samples_v1.csv`。
- 什么时候使用：每次向主标注表追加新样本时使用。
- 我应该怎么维护：以“直接填主表”为原则维护；如果列含义变动，必须同步更新本文件。

## 先看分类

每篇都要填：
- `sample_id`
- `pdf_path`
- `file_exists`
- `source_format_guess`
- `layout_guess`
- `ground_truth_authors_json`
- `ground_truth_first_author_json`
- `ground_truth_emails_json`
- `annotation_status`

按情况填：
- `has_corresponding_author_marker`
- `has_equal_contribution_note`
- `has_shared_or_group_email`
- `ground_truth_co_first_authors_json`
- `ground_truth_pairs_json`
- `ground_truth_email_regions_json`
- `notes`

## 逐列速查

| 列名 | 要不要填 | 什么时候必须填 | 什么时候可以留空 | 怎么填 | 最短可复制示例 |
| --- | --- | --- | --- | --- | --- |
| `sample_id` | 每篇都要填 | 新增一篇样本时必须填 | 不可留空 | 用稳定编号，和 PDF 文件名对应 | `S001` |
| `pdf_path` | 每篇都要填 | PDF 放入项目后必须填 | 不可留空 | 写相对路径 | `papers/raw/S001_example.pdf` |
| `file_exists` | 每篇都要填 | 主表建行时就填 | 不可留空 | 只写 `true` 或 `false` | `true` |
| `source_format_guess` | 每篇都要填 | 录入基础信息时填 | 不建议留空；看不出时填 `unknown` | 人工判断来源模板 | `IEEE` |
| `layout_guess` | 每篇都要填 | 录入基础信息时填 | 不建议留空；看不出时填 `unknown` | 人工判断版式 | `two-column` |
| `has_corresponding_author_marker` | 按情况填 | 看到了通讯作者相关标记时必须明确写 | 看不清时不要空着，填 `unclear` | 写 `true` / `false` / `unclear` | `true` |
| `has_equal_contribution_note` | 按情况填 | 看到 equal contribution 或 co-first 说明时必须明确写 | 看不清时填 `unclear` | 写 `true` / `false` / `unclear` | `false` |
| `has_shared_or_group_email` | 按情况填 | 看到共享邮箱、分组邮箱或团队邮箱时必须明确写 | 看不清时填 `unclear` | 写 `true` / `false` / `unclear` | `unclear` |
| `ground_truth_authors_json` | 每篇都要填 | 开始正式标注作者时必须填 | 未开始时可先用 `[]` 占位 | 按作者顺序写 JSON 数组 | `[{"author_raw":"Author One","author_norm":"Author One","source_page":1,"author_index":0,"markers":[]}]` |
| `ground_truth_first_author_json` | 每篇都要填 | 一旦作者顺序明确就必须填 | 只有作者顺序无法判断时才可写 `null` | 永远写作者顺序第一位 | `{"author_raw":"Author One","author_norm":"Author One","source_page":1,"reason":"first_by_author_order"}` |
| `ground_truth_co_first_authors_json` | 特殊情况下重点处理 | 只有有明确共同一作证据时才填作者列表 | 没证据时填 `[]` | 写 co-first 作者数组，不改变 `first_author` | `[]` |
| `ground_truth_emails_json` | 每篇都要填 | 开始填邮箱真值时必须填 | 未发现或未开始时可填 `[]` | 写能直接确认的邮箱数组 | `[{"email":"author.one@example.com","source_page":1}]` |
| `ground_truth_pairs_json` | 特殊情况下重点处理 | 只有作者和邮箱对应关系明确时才填 | 不确定时填 `[]` | 只写确定 pair，不强配 | `[]` |
| `ground_truth_email_regions_json` | 特殊情况下重点处理 | 需要记录邮箱地域时填 | 暂未判断时可填 `[]`；不确定单条可写 `UNKNOWN` | 写邮箱级别的 `CN` / `OVERSEAS` / `UNKNOWN` | `[{"email":"author.one@example.com","region":"OVERSEAS"}]` |
| `annotation_status` | 每篇都要填 | 建行时就必须填 | 不可留空 | 只写 `todo` / `in_progress` / `annotated` / `reviewed` / `blocked` | `todo` |
| `notes` | 特殊情况下重点处理 | 有歧义、保守留空、共享邮箱难配、需要指向 note 文件时必须填 | 普通清晰样本可以留空字符串 | 写短说明；长说明放单篇 note | `Needs note file for shared email ambiguity.` |

## 特别提醒列

以下列通常只有遇到特殊样本才需要重点处理：
- `has_corresponding_author_marker`
- `has_equal_contribution_note`
- `has_shared_or_group_email`
- `ground_truth_co_first_authors_json`
- `ground_truth_pairs_json`
- `ground_truth_email_regions_json`
- `notes`

## JSON 列总规则

- 所有 `*_json` 列都必须是合法 JSON 字符串。
- 不要留空白单元格，用 `[]` 或 `null`。
- `ground_truth_first_author_json` 一旦不是 `null`，`reason` 必须与 V1 一致，写 `first_by_author_order`。