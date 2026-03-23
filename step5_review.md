# Step 5 Review

- 本轮只实现了 Step 5：作者抽取模块与作者列表 smoke 验证。
- 没有进入 Step 6/7/8。
- 没有实现作者-邮箱匹配、地域分类、微服务 API 串联。
- 没有改动 Step 1 冻结的 API 语义，也没有改动样本文件名或 `pdf_path` 约定。

## 本轮实现了什么

- 新增 [`author_extract.py`](./author_extract.py)，提供：
  - `AuthorCandidate`
  - `extract_authors_from_text(text: str)`
  - `extract_authors_from_pages(pages)`
  - `extract_authors_from_pdf(pdf_path, max_pages=2)`
- 抽取逻辑基于 [`pdf_extract.py`](./pdf_extract.py) 的 `extract_pages(...)` 输出工作，优先使用首页 `lines`，必要时用 `blocks` 兜底。
- 采用“首页优先、必要时第二页、单页失败不拖垮整份 PDF”的策略。
- 输出字段覆盖：
  - `raw`
  - `normalized`
  - `page_number`
  - `author_index`
  - `markers`
  - `confidence`
  - `source_snippet`
- 新增 [`scripts/run_author_extract_smoke.py`](./scripts/run_author_extract_smoke.py)，支持从 `data/samples_v1.csv` 选取样本并汇总 smoke 结果。

## 当前支持的作者区写法

- 标题下方单行作者列表。
- 多作者逗号分隔列表。
- `and` 结尾的最后一位作者。
- 名字后带 `*`、`†`、`‡`、`x`、单字母脚注、数字上标/脚注序号。
- 多行长作者列表。
- 作者名被换行截断后在下一行续接的情况。
- 单个作者单独占行、邮箱单独占行的版式。
- equal contribution / corresponding / project lead 等脚注说明与作者区相邻但需要过滤的情况。

## 当前的保守过滤

- 过滤邮箱、URL、`Corresponding author`、`Correspondence`、`These authors contributed equally`、`Co-first authors` 等说明行。
- 过滤明显机构/单位行，如包含 `University`、`Department`、`Institute`、`School`、`Laboratory`、`Academy`、`Group` 等关键词的行。
- 过滤行首带机构编号的 affiliation 行，如 `1School ...`、`5Amazon ...`。
- 过滤明显地点/国家续行，如 `... China`、`... USA`、`... Province` 这类机构延续文本。
- `normalized` 会保留人名主体并清理脚注、重复空格，以及少量 PDF 噪声标点。

## 仍可能失败的写法

- OCR 很差、标题和作者块粘连严重的 PDF。
- 作者名完全没有分隔符、也没有脚注标记的超紧凑排版。
- 非拉丁字母作者名或高度混排的作者区。
- 机构与作者名共用一行、且没有明显模板边界的特殊排版。
- 极端脚注符号或非常规上标字符未被当前规则覆盖的样本。

## Smoke 结果

- 本轮对 20 篇样本跑了 smoke test。
- 结果：`success=20`，`failure=0`。
- 判定规则：抽到非空作者列表，且与真值相比首作者正确，并达到最小有序重合阈值。

代表样本：

- 表现最好：
  - `S003`：跨行断开的长作者列表，11/11 命中。
  - `S026`：32 位超长作者列表，32/32 命中。
  - `S029`：作者与邮箱交错排布，7/7 命中。
- 当前最脆弱但已通过：
  - `S013`：作者区后紧跟多行 affiliation，且含特殊字符姓名；本轮通过行首机构编号过滤和 `normalized` 清洗后恢复到 17/17。
  - `S007`：无逗号紧凑作者行，依赖脚注符号边界拆分。

## Step 6 前还缺什么

- Step 6 需要消费当前作者列表输出，但不要回改 Step 5 语义。
- 作者-邮箱匹配应直接使用本轮产出的：
  - `normalized`
  - `markers`
  - `author_index`
  - `page_number`
  - `source_snippet`
- 进入 Step 6 前，建议再补少量更难的 PDF：
  - OCR 较差样本
  - 非常规模板样本
  - 非英文作者区样本
- 若 Step 6 需要更强的名字归一化，应只新增 matcher 内部对比规则，不要改变 Step 5 的 `raw` 含义。

## 明确未做的事

- 没有做作者-邮箱匹配。
- 没有做 `first_author` 最终业务拼装。
- 没有做地域分类。
- 没有做 API 串联或服务化输出。
