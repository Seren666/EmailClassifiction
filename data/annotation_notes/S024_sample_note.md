# S024 Sample Note

- 文件用途：记录本轮首页人工核对后仍未完全消除的模糊点。
- 什么时候使用：当你下载的 PDF 已存在，但首页信息还不足以让该样本直接设为 `done` 时使用。
- 我应该怎么维护：后续只在你核对该 PDF 首页/脚注后补充，不要凭猜测补真值。

## Basic Info

- `sample_id`: S024
- `pdf_path`: papers/raw/S024_speechcolab_leaderboard.pdf
- `annotation_status`: needs_review

## Author Block Observation

- 作者顺序已按首页核对并写回主表。
- 共同一作字段仅在首页标记足够明确时填写。

## Email Observation

- 已记录首页可直接读到的邮箱：[{'email': 'jerry.jiayu.du@gmail.com', 'source_page': 1}, {'email': 'lijp22@mails.tsinghua.edu.cn', 'source_page': 1}, {'email': 'wqzhang@tsinghua.edu.cn', 'source_page': 1}]
- 未解决点：Guoguo Chen's email is line-broken on the first page, so it is left unresolved pending manual PDF confirmation.

## Ground Truth Decision

- `first_author` 继续严格按作者顺序第一位填写。
- `co_first_authors` 不覆盖 V1 `first_author`。
- `pairs` 只保留首页上足够直接的对应关系。

## Open Questions

- Guoguo Chen's email is line-broken on the first page, so it is left unresolved pending manual PDF confirmation.
