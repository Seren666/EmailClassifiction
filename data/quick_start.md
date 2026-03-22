# Quick Start

- 文件用途：一页式说明第二步最简人工流程。
- 什么时候使用：准备开始录入第一篇或新的一篇论文时使用。
- 我应该怎么维护：如果主流程变化，只更新这一页和 `data/fill_workflow.md`，保持两者一致。

## 最短流程

1. 把 PDF 放到 `papers/raw/`。
2. 打开 `data/samples_v1.csv`，直接追加一行。
3. 先填每篇都要填的列。
4. 再填按情况填写的列。
5. 必要时补一个 `annotation_notes` 文件。
6. 运行 `python scripts/validate_samples.py`。

## 每篇都要填的列

- `sample_id`
- `pdf_path`
- `file_exists`
- `source_format_guess`
- `layout_guess`
- `ground_truth_authors_json`
- `ground_truth_first_author_json`
- `ground_truth_emails_json`
- `annotation_status`

## 按情况填的列

- `has_corresponding_author_marker`
- `has_equal_contribution_note`
- `has_shared_or_group_email`
- `ground_truth_co_first_authors_json`
- `ground_truth_pairs_json`
- `ground_truth_email_regions_json`
- `notes`

## 关键规则

- `first_author` 永远是作者顺序第一位。
- 通讯作者不改变 `first_author`。
- 共同一作不改变 V1 的 `first_author`。
- 不确定的 pair 不要强配。

## 最后验证

```bash
python scripts/validate_samples.py
```