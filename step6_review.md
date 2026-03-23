# Step 6 Review

- 本轮只实现了 Step 6：作者-邮箱匹配模块与匹配 smoke 验证。
- 没有进入 Step 7/8。
- 没有做地域分类。
- 没有做最终 API 响应拼装。
- 没有改动 Step 1 冻结的 API 语义，也没有改变 Step 5 作者抽取语义。

## 本轮实现了什么

- 新增 [`author_email_match.py`](./author_email_match.py)，提供：
  - `AuthorEmailPair`
  - `match_authors_and_emails(authors, emails, pages=None)`
  - `match_authors_and_emails_from_pdf(pdf_path, max_pages=2)`
- 新增 [`scripts/run_author_email_match_smoke.py`](./scripts/run_author_email_match_smoke.py)，支持从 `data/samples_v1.csv` 读取样本并汇总匹配 smoke 结果。
- 匹配逻辑消费：
  - [`author_extract.py`](./author_extract.py) 的作者列表
  - [`email_extract.py`](./email_extract.py) 的邮箱候选
  - [`pdf_extract.py`](./pdf_extract.py) 的页面文本/行信息

## 当前支持的匹配规则

- `exact_localpart_match`
  - `surname+given` / `given+surname`
  - 直接名字 token 命中
  - 带短尾缀的扩展形式，如 `huanglei22s`
- `grouped_email_expansion_match`
  - 对 `{a,b}@domain`、`a,b@domain` 展开后的邮箱逐一匹配
  - 结合作者顺序做保守支持
- `initials_plus_surname_match`
  - `qjin`、`xwu`、`jamesz`
  - `s.pan`
  - `yang.yhx`
  - `zlw...`、`zhangdc...` 这类缩写/拼音压缩形式
- `proximity_supported_match`
  - 用于作者行与邮箱行严格交替、且邮箱 local-part 只能弱匹配昵称/前缀的情况
  - 目前主要覆盖 `S029` 这类一人一行作者、一人一行邮箱版式
- correspondence / marker 支持
  - 当邮箱 snippet 明显是 `Corresponding author` 或 `Correspondence` 时，用作者 markers 做保守加分
  - 只作为支持证据，不单独强配

## 哪些规则最可靠

- 最高可靠：
  - 展开后的 grouped email + 直接名字命中
  - `surname+given` / `given+surname` 的直接 local-part 命中
- 次高可靠：
  - `initials_plus_surname_match`
  - `surname + abbreviation token`，如 `s.pan`、`yang.yhx`
- 最弱但仍保留：
  - `proximity_supported_match`
  - 仅在作者/邮箱行严格邻接、且整体版式非常清晰时启用

## Smoke 结果

- 本轮对 13 篇样本跑了 Step 6 smoke test。
- 结果：`success=13`，`failure=0`。
- smoke 判定偏保守：
  - 对 `annotation_status=done` 的样本，要求预测 pair 为真值 pair 的子集
  - 对 `needs_review` 的样本，只要求有可用重合，不因真值未完全冻结而误判

代表样本：

- 表现最好：
  - `S007`：4/4 grouped email 全命中
  - `S029`：7/7 命中，昵称/缩写邮箱依赖 strict proximity 也能稳定匹配
  - `S030`：7/7 命中，多个 grouped email 块都能稳定展开并配对
- 当前最保守但仍可用：
  - `S028`：只输出 1 条高置信 pair，明显偏低召回，但没有强配
  - `S010`：只输出 2 条高置信 pair，保留了“不确定不配”的策略

## 仍容易失败的情况

- 一个 local-part 只保留非常短的缩写，且没有清晰 correspondence / proximity 支持。
- 多位作者共享同一个机构邮箱，但首页只给出模糊说明，没有组内顺序或名字线索。
- 机构块与邮箱块之间存在大量中间文本，导致 proximity 证据不再可靠。
- 特殊昵称邮箱、实验室代号邮箱、项目邮箱。
- 一对多 / 多对一共享邮箱的复杂情形，目前仍优先不强配。

## Step 7 前还缺什么

- Step 7 只能消费本轮已确认的 pair 结果，不要回改 Step 6 的保守策略。
- `first_author_email` 只能在 Step 6 已存在明确 pair 时补充，不要反向为了 first author 去强推邮箱。
- 进入 Step 7 前仍缺：
  - 地域分类模块
  - 对 unmatched emails / unmatched authors 的最终业务拼装
  - `first_author_email` / `first_author_region` 的字段写入
- 如果 Step 7 需要更多召回，建议只新增“更明确的可解释规则”，不要把 proximity 扩展成大范围猜配。

## 明确未做的事

- 没有做地域分类。
- 没有做最终 API 串联。
- 没有输出完整 payload 或 response envelope。
- 没有改变 `first_author` 的 V1 语义。
