# S003 Sample Note

- 文件用途：记录本轮首页人工核对后仍未完全消除的模糊点。
- 什么时候使用：当你下载的 PDF 已存在，但首页信息还不足以让该样本直接设为 `done` 时使用。
- 我应该怎么维护：后续只在你核对该 PDF 首页/脚注后补充，不要凭猜测补真值。

## Basic Info

- `sample_id`: S003
- `pdf_path`: papers/raw/S003_mapreduce_ralm.pdf
- `annotation_status`: needs_review

## Author Block Observation

- 作者顺序已按首页核对并写回主表。
- 共同一作字段仅在首页标记足够明确时填写。

## Email Observation

- 已记录首页可直接读到的邮箱：[{'email': 'cw2384@cumc.columbia.edu', 'source_page': 1}, {'email': 'yip4002@med.cornell.edu', 'source_page': 1}]
- 未解决点：Two corresponding-author emails are visible, but the first-page text does not explicitly bind each email to one of the two corresponding authors.

## Ground Truth Decision

- `first_author` 继续严格按作者顺序第一位填写。
- `co_first_authors` 不覆盖 V1 `first_author`。
- `pairs` 只保留首页上足够直接的对应关系。

## Open Questions

- Two corresponding-author emails are visible, but the first-page text does not explicitly bind each email to one of the two corresponding authors.
