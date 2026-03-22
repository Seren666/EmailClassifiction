# Sample Inventory

- 文件用途：可选补充记录，用来额外记候选来源或找样本时的备忘。
- 什么时候使用：只有你想额外记录候选论文来源、搜索线索或备用样本时才使用。
- 我应该怎么维护：它不再是主流程的一部分；默认可以完全不填。

## 现在的定位

- 这不是必填文件。
- 这不是前置步骤。
- 默认流程是直接把 PDF 放进 `papers/raw/`，然后填写 `data/samples_v1.csv`。

## 可选模板

| sample_id | pdf_path | source | layout | why_keep_a_note | status |
| --- | --- | --- | --- | --- | --- |
| S001 | papers/raw/S001_placeholder_paper.pdf | IEEE | two-column | 可选示例：记一下这篇为什么值得保留为候选或备用 | candidate |

## 建议值

- `status` 可用：`candidate` / `annotated` / `archived`
- `why_keep_a_note` 可写：来源链接说明、为什么暂存、为什么作为备用样本