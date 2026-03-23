# Step 7 Review

- 本轮只实现了 Step 7：基于现有作者列表、邮箱列表、作者-邮箱已确认 pair，生成结构化中间结果。
- 没有进入 Step 8。
- 没有做 FastAPI、最终接口暴露或最终 API 串联。
- 没有修改 Step 1 冻结的 API 语义，也没有改变 Step 5 / Step 6 的抽取与匹配语义。

## 本轮实现了什么

- 新增 [`assemble_structured_output.py`](./assemble_structured_output.py)，提供：
  - `assemble_structured_output(authors, emails, pairs, pages=None)`
  - `assemble_structured_output_from_pdf(pdf_path, max_pages=2)`
  - `classify_email_region(email)`
- 新增 [`scripts/run_step7_smoke.py`](./scripts/run_step7_smoke.py)，用于批量验证 Step 7 中间结果是否稳定、可用。
- 中间结果对象包含：
  - `authors`
  - `first_author`
  - `co_first_authors`
  - `equal_contribution_detected`
  - `emails`
  - `pairs`
  - `shared_emails`
  - `unmatched_authors`
  - `unmatched_emails`
  - `first_author_email`
  - `first_author_region`
  - `stats`

## first_author_email 如何保守生成

- `first_author` 永远直接取作者顺序第一位，不做任何重排。
- `first_author_email` 只从 Step 6 已确认的 `pairs` 中取。
- 如果第一作者在 Step 6 没有已确认 pair，则 `first_author_email = null`。
- 不会为了补 `first_author_email` 反向去猜邮箱，也不会根据邮箱顺序或通讯作者说明强配第一作者。

## 当前支持的地域判断

- 只对“已确认邮箱”做保守地域判断。
- 规则非常简单：
  - 域名以 `.cn` 结尾 -> `CN`
  - 常见国内公共邮箱域名，如 `qq.com`、`163.com`、`126.com`、`foxmail.com` -> `CN`
  - 其他可识别域名 -> `OVERSEAS`
  - 邮箱缺失或域名异常 -> `UNKNOWN`
- `first_author_region` 只在 `first_author_email` 存在时填写，否则保持 `null`。

## 哪些样本能直接得到 first_author_email

- 在本轮 smoke 中，以下样本能直接得到 `first_author_email`：
  - `S001`
  - `S002`
  - `S004`
  - `S006`
  - `S007`
  - `S008`
  - `S009`
  - `S027`
  - `S028`
  - `S029`
  - `S030`
- 这类样本通常满足以下条件之一：
  - 第一作者在 Step 6 中已有明确 pair。
  - grouped email 已被可靠展开且第一作者成功命中。
  - 第一作者 local-part 与姓名直接对应，或缩写规则足够明确。

## 哪些样本会保留 null

- 在本轮 smoke 中，以下样本保留了 `first_author_email = null`：
  - `S010`
  - `S026`
- 保留 `null` 的原因都符合 Step 6 的保守边界：
  - 第一作者在 Step 6 没有已确认 pair。
  - 只有其他作者能匹配邮箱、但第一作者证据不足。
  - local-part 过短、过于模糊，或只能依赖弱 proximity 但未达到接受阈值。

## 仍然容易失败的情况

- 第一作者邮箱根本不在首页或前两页。
- 第一作者使用实验室邮箱、项目邮箱、昵称邮箱，local-part 与姓名弱相关。
- 多位作者共享同一邮箱但 Step 6 还没有产生“明确的多对一确认 pair”。
- equal contribution 文本存在，但作者标记不足以可靠恢复 `co_first_authors`。

## Smoke 中表现最好/最差

- 表现最好：
  - `S007`：grouped email 展开后 4/4 命中，第一作者邮箱直接可用。
  - `S029`：7 个 pair 全部保留，`first_author_email` 稳定落到 `merty@stanford.edu`。
  - `S030`：长作者列表下仍能稳定得到 `Lei Huang -> huanglei22s@ict.ac.cn`。
- 当前最保守的情况：
  - `S010`：对象完整输出，但第一作者没有 confirmed pair，因此稳定保留 `null`。
  - `S026`：32 位作者、仅 1 个 confirmed pair；Step 7 仍能稳定生成完整对象，不会因首作者无 pair 而崩溃。
  - `shared_emails` 在本轮 smoke 中均为空，因为 Step 6 仍优先“一人一个主邮箱”的保守策略。

## Smoke 结果

- 本轮对 13 篇样本跑了 Step 7 smoke test。
- 结果：`success=13`，`failure=0`。
- 没有失败样本。
- 当前退出判断依据：
  - 能稳定生成结构化中间结果。
  - 没有 confirmed pair 时也不会崩溃。
  - `first_author_email` 只来自已确认 pair。

## Step 8 前还缺什么

- Step 8 需要把本轮中间对象映射到最终 API 输出字符串 / envelope。
- 需要做最终 schema 校验、错误处理与接口层拼装。
- 如果后续要支持更丰富的 `shared_emails`，应先扩展 Step 6 的“明确多对一匹配”规则，而不是在 Step 7 里反推。

## 明确未做的事

- 没有做 FastAPI。
- 没有做最终接口暴露。
- 没有做 Step 8 的最终 API 串联。
- 没有回改 Step 5 作者抽取逻辑。
- 没有回改 Step 6 匹配接受阈值。
