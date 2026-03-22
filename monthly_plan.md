# 项目阶段计划（步骤式｜轻量微服务｜作者-邮箱匹配 + 海内外分类 + 第一作者提取）

## 0. 项目边界与目标
- **不做整个平台/体系**，只交付一个**可被上层系统调用的单功能微服务**。
- **输入**：PDF 文件路径（本地路径或挂载路径）。
- **输出**：邮箱结构化字符串（JSON dumps 后的字符串），包含：
  1. 邮箱抽取
  2. 作者-邮箱匹配
  3. 邮箱地域（CN / OVERSEAS / UNKNOWN）
  4. **第一作者提取（first_author）**
- **对外**：提供一个稳定 API，给上层直接调用。
- **说明**：
  - V1 中的 `first_author` 默认指**作者顺序上的第一作者**。
  - 对于共同一作（co-first authors / equal contribution），第一版不作为硬性验收项，但预留字段和调试能力，支持后续增强。

---

## 1. 冻结 API 与输出 Schema（第一步先“定接口”）
**目标**：把“输入/输出/错误码/字段命名”定下来，后续实现围绕它迭代，不反复改接口。

**产出**
- API 文档 v1（请求/响应/错误码/示例）。
- 输出 JSON Schema（包含字段解释）。
- **明确 `first_author` 字段定义**。
- **预留 `co_first_authors` / `equal_contribution_detected` 扩展字段**。

**建议输出主结构**
```json
{
  "authors": [],
  "first_author": {
    "author_raw": "",
    "author_norm": "",
    "source_page": 1,
    "reason": "first_by_author_order"
  },
  "co_first_authors": [],
  "equal_contribution_detected": false,
  "emails": [],
  "pairs": [],
  "shared_emails": [],
  "unmatched_authors": [],
  "unmatched_emails": [],
  "stats": {}
}
```

**退出标准**
- 上层师能用示例请求跑通并理解返回数据结构。
- 字段命名稳定（后续仅允许“新增字段”，尽量不改旧字段含义）。
- **上层明确接受 `first_author` 的 V1 定义为“作者顺序上的第一作者”**。

**预计交付时间**
- 3月8日（大约一周）

---

## 2. 样本与真值准备（科研式推进：先有数据）
**目标**：准备一个小而多样的测试集，用于每次迭代回归。

**做法**
- 先收集 10 篇（格式尽量多样：IEEE/ACM/Elsevier/arXiv、两栏/一栏、首页脚注邮箱、通讯作者标记等）。
- 逐步扩展到 20–30 篇。
- **样本中尽量覆盖：**
  - 作者顺序清晰的论文
  - 存在通讯作者标记的论文
  - 存在共同一作说明的论文
  - 多作者共享邮箱 / 分组邮箱的论文

**产出**
- `samples_v1.csv`：每篇论文的：
  - 真实作者列表
  - **真实第一作者**
  - 可选：真实共同一作列表
  - 真实邮箱列表
  - 真实作者-邮箱配对
  - 邮箱地域标签

**退出标准**
- 任意一次改动都能在样本集上快速回归（至少跑 10 篇）。
- **能够单独评估 first_author 提取是否正确**。

**预计交付时间**
- 3月15日（大约一周）

---

## 3. PDF 文本抽取模块
**目标**：稳定抽取“首页+（必要时）前两页”的文本，包含页码信息，便于定位邮箱与作者块。

**实现方式**
- 优先：PyMuPDF（fitz）抽取文本
- 兜底：pdfplumber
- 需要保存：
  - `pages[i].text`
  - （可选）`blocks/lines` 的位置信息（后续做邻近度匹配更稳）

**产出**
- `pdf_extract.py`：`extract_pages(pdf_path, max_pages=2) -> List[PageText]`

**退出标准**
- 对样本集中的绝大多数 PDF：能拿到“可读文本”，且不会频繁崩溃。

**预计交付时间**
- 3月22日（大约一周）

---

## 4. 邮箱候选抽取与规范化（高召回优先）
**目标**：尽量不漏抽，先把所有可能邮箱找出来，再逐步提高精度。

**需要覆盖的典型写法**
- 常规：`alice@xx.edu`
- 分组展开：`{alice,bob}@xx.edu`、`alice,bob@xx.edu`
- 换行/断词：`alice@xx.\nedu`
- 轻度混淆：`alice [at] xx.edu`、`alice(at)xx.edu`、`alice at xx dot edu`

**产出**
- `email_extract.py`：`extract_emails(text) -> List[EmailCandidate]`
- 规范化函数：去空格/换行、统一小写、分组展开。

**退出标准**
- 在样本集上邮箱召回率达到一个“能用的水平”，并输出未识别到的典型模式用于补规则。

**预计交付时间**
- 3月29日（大约一周）

---

## 5. 作者抽取与标准化（先能拿到作者序列）
**目标**：从首页作者区域拿到“有序作者列表”，并做标准化（去脚标、统一格式）；在此基础上，**提取第一作者**。

**实现方式**
1. 规则优先：从标题下方的一段文本中解析作者行（论文模板通常比较固定）。
2. 去噪：去掉 `*`, `†`, `1`, `2`, `,` 等脚注符号及多余空格。
3. 保留：`author_raw` 和 `author_norm` 两个字段（排错很关键）。
4. **保留作者顺序**。
5. **默认将作者序列中的第一个作者作为 `first_author`**。
6. 可选增强：识别共同一作相关标记，如：
   - `* equal contribution`
   - `† these authors contributed equally`
   - `co-first authors`

**产出**
- `author_extract.py`：`extract_authors(pages) -> List[Author]`
- **`extract_first_author(authors, context) -> FirstAuthorResult`**
  - 或直接在作者抽取阶段返回 `authors + first_author`
- 每个作者建议保留：
  - `author_raw`
  - `author_norm`
  - `source_page`
  - `author_index`
  - `markers`（如 `*`, `†`, `1`）
- `first_author` 建议保留：
  - `author_raw`
  - `author_norm`
  - `source_page`
  - `reason`
  - `confidence`

**退出标准**
- 样本集中大部分论文能给出合理作者列表（允许少量失败，先标记 UNKNOWN）。
- **在作者顺序清晰的样本中，first_author 提取结果稳定**。
- 对存在疑似共同一作的样本，至少能在 debug 中保留相关线索。

**预计交付时间**
- 4月5日（大约一周）

---

## 6. 作者-邮箱匹配（规则打分 + 可解释）
**目标**：把“邮箱列表”提升为“作者-邮箱配对”，并能解释匹配依据。

**补充说明**
- `first_author` 不依赖邮箱匹配才能产出，**优先根据作者序列单独产出**。
- 若 `first_author` 成功匹配到邮箱，可在结果中补充：
  - `first_author_email`
  - `first_author_region`

**推荐的匹配信号（从强到弱）**
- 脚注/符号对应：作者名后 `*` 与邮箱附近 `*` 对应
- 邻近度：邮箱出现在作者块/单位块附近
- 用户名相似度：`alice.wang` ↔ `Alice Wang`（首字母、姓氏、拼音近似等）
- 顺序假设：当出现 `a,b,c@domain` 且作者也按 a,b,c 顺序出现，可作为弱规则

**冲突处理**
- 多作者共享一个邮箱：允许 many-to-one（把同一个 email 分配给多个 author，或单独放在 `shared_emails`）
- 单作者多个邮箱：允许 one-to-many
- 不确定就不要强配：输出 `UNKNOWN`，并在 debug 中给出原因
- **若 first_author 存在但其邮箱无法确定，仍保留 `first_author`，邮箱字段可为空**

**产出**
- `matcher.py`：`match(authors, emails, context) -> List[Pair]`

**退出标准**
- 在样本集上，作者-邮箱配对准确率达到“可交付的第一版”（并且错误可解释、可复现）。
- **即使邮箱未成功匹配，first_author 也应能独立输出**。

**预计交付时间**
- 4月12日（大约一周）

---

## 7. 邮箱地域分类（CN / OVERSEAS / UNKNOWN）
**目标**：对每个邮箱给出地域标签，规则简单、可配置。

**建议规则（可配置表）**
- `CN`：
  - 域名以 `.cn` 结尾（含 `.edu.cn` / `.ac.cn` / `.com.cn` 等）
  - 或属于常见国内邮箱域名（如 `qq.com`, `163.com`, `126.com`, `aliyun.com`, `sina.com`, `sohu.com`, `foxmail.com`, `139.com`, `189.cn`, `21cn.com` 等）
- 其他大多数情况：`OVERSEAS`
- 无法解析/不规范：`UNKNOWN`

> 注：`.hk/.mo/.tw` 默认可按 OVERSEAS 处理；如果上游定义需要并入“境内”，可在配置表中切换。

**产出**
- `geo_classifier.py`：`classify_email_region(email) -> (region, reason)`

**退出标准**
- 对样本集的地域标签基本稳定，且“理由可追踪”。

**预计交付时间**
- 4月19日（大约一周）

---

## 8. Pipeline 串联 + 微服务化交付（让上层师能直接调用）
**目标**：把以上模块串成一条可运行流水线，并封装为 API 服务。

**API**
- `POST /extract-author-emails`
- 入参：`pdf_path`
- 出参：
  - `structured_email_string`（json.dumps 之后的字符串）
  - `stats`
  - `code`
  - `message`

**新增要求**
- `structured_email_string` 中应显式包含：
  - `first_author`
  - 可选：`co_first_authors`
  - 可选：`equal_contribution_detected`
  - 可选：`first_author_email`
  - 可选：`first_author_region`

**工程化要点**
- 参数校验、错误码齐全（路径不存在 / 解析失败 / 没有邮箱 / 内部异常）
- 日志：每一步输出关键统计（作者数、邮箱数、匹配数、unknown 数）
- **日志中增加：是否成功提取 first_author**
- 可选：`debug=true` 时返回更多中间信息（不影响默认接口简洁）

**产出**
- 可运行服务
- `README`（启动、示例请求、错误码说明）
- 一份简短评测报告（样本集指标 + 典型错误）
- **增加一项 first_author 评测结果**

**退出标准**
- 上层可在本地或服务器上启动服务并通过 curl/SDK 调用拿到稳定结果。
- **first_author 在样本集上达到基础可用水平**。

**预计交付时间**
- 4月26日（大约一周）

---

## 9. 迭代策略
- 每次只改一个点：比如“增加一种邮箱写法”或“优化一种匹配冲突”
- 每次改完必跑样本回归（先 10 篇，后 20–30 篇）
- 记录 Top 错误类型（前 5 个），优先修最常见的
- **单独记录 first_author 错误类型，例如：**
  - 作者块解析错误
  - 第一作者与机构行混淆
  - 共同一作识别失败
  - 脚注符号误判

---

## 10. 最终交付清单
1. API 服务可运行（含依赖与启动命令）
2. `POST /extract-author-emails` 接口稳定
3. 输出 `structured_email_string`（结构化字符串）
4. **输出 `first_author` 字段**
5. 样本集与评测报告（至少 20 篇更好）
6. 文档：使用说明、错误码、已知限制、后续可优化点
7. **补充说明：V1 中 `first_author` 的定义与共同一作支持范围**

---

## 已知限制（建议同时写入 README）
> 当前版本中的 `first_author` 默认表示作者顺序上的第一作者。对于 `equal contribution`、`co-first authors`、脚注声明等复杂情况，第一版优先保留标记与调试信息，后续再做增强识别。
