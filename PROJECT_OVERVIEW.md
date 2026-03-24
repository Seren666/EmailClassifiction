# Project Overview

## 1. 项目简介

这个项目的用途，是从论文 PDF 的前部页面中提取作者、邮箱和作者-邮箱对应关系，并返回一个结构化结果，重点给出 `first_author`、`first_author_email` 和相关统计信息。

它当前是一个本地可运行的微服务。调用方提交一个 `pdf_path`，服务读取本地或挂载路径上的 PDF，运行一条规则驱动的抽取与匹配流水线，然后通过 HTTP API 返回统一 envelope：

- 输入：`pdf_path`
- 输出：`structured_email_string`、`stats`、`code`、`message`

其中 `structured_email_string` 里承载的是核心结构化结果，包含作者列表、邮箱列表、确认匹配对、第一作者信息、未匹配项和统计信息。

这个项目解决的核心问题不是“理解整篇论文”，而是把论文首页附近常见的作者区信息，稳定地转成可消费的结构化数据，尤其是给出保守、可解释的第一作者及其邮箱结果。

## 2. 快速建立整体认知

可以把这个项目理解成一条从 `pdf_path` 到 JSON 的本地规则流水线。入口在 `app.py`，它接收 API 请求、校验路径、调用 `pipeline.py`，并把结果包装成稳定的 V1 响应格式。`pipeline.py` 不做复杂业务推断，它的职责是按顺序把各个模块串起来。首先，`pdf_extract.py` 读取 PDF 的前几页文本，并尽量保留页面文本、行和块等可供后续规则使用的信息。接着，`email_extract.py` 从这些文本里找邮箱候选，包括普通邮箱、分组邮箱和部分混淆写法。然后，`author_extract.py` 从首页作者区附近抽取作者列表，并给作者顺序编号。之后，`author_email_match.py` 根据姓名、邮箱 local-part、顺序、相邻性和标记信息，保守地产生“已确认 pair”。最后，`assemble_structured_output.py` 把作者、邮箱、pair 和统计信息组装成最终结构化对象，并补出 `first_author`、`first_author_email`、`first_author_region` 等字段，API 再把它序列化后返回。

## 3. 整体架构 / 流水线

### 3.1 分层视角

#### API 层

`app.py` 暴露 `POST /extract-author-emails`。这一层负责：

- 接收请求体中的 `pdf_path`
- 做请求校验和路径存在性校验
- 调用 pipeline
- 把内部结构化对象包装为稳定的外层响应
- 把内部异常映射成固定错误码

这一层存在的意义，是把“可直接给人或系统调用的接口约定”和“内部抽取逻辑”分开，避免后续维护时 API 契约和规则实现互相缠绕。

#### pipeline 串联层

`pipeline.py` 是总调度层。它负责按照固定顺序执行：

1. PDF 文本抽取
2. 作者抽取
3. 邮箱抽取
4. 作者-邮箱匹配
5. 结构化结果组装

它还负责中间统计、错误归类和日志摘要。这样拆分后，每个模块都可以单独 smoke、单独替换、单独调规则，而不需要从 API 层直接追业务细节。

#### PDF 文本抽取层

`pdf_extract.py` 从 PDF 中抽取页面文本。默认上限是前两页，优先使用 `PyMuPDF(fitz)`，必要时回退到 `pdfplumber`。输出是 `PageText` 列表，每页除了 `text` 以外，还尽量保留：

- `page_number`
- `extractor_used`
- `blocks`
- `lines`
- `error`

这样做的原因，是后续作者抽取和匹配规则不仅依赖纯文本，也会利用页面中的行顺序、块位置等信息。

#### 邮箱抽取层

`email_extract.py` 从页面文本里提取 `EmailCandidate`。它处理的不只是标准 `name@example.com`，还覆盖了部分论文首页常见写法，例如：

- `{alice,bob}@example.edu`
- `alice/bob@example.edu`
- `alice [at] example [dot] edu`

输出是邮箱候选列表，每个候选都带有来源页码、匹配类型、置信度和源片段，供后续匹配使用。

#### 作者抽取层

`author_extract.py` 从页面顶部的作者区里提取 `AuthorCandidate`。它优先看行级信息，必要时退回块级信息，并尽量在正文开始前截断。输出不仅包含作者名，还包含：

- 作者顺序 `author_index`
- 作者脚注标记 `markers`
- 来源页码
- 源片段

这一层的关键目标不是“理解所有人物实体”，而是尽量稳定恢复作者序列，因为 V1 的 `first_author` 语义直接依赖作者顺序。

#### 作者-邮箱匹配层

`author_email_match.py` 基于作者候选和邮箱候选生成 `AuthorEmailPair`。它使用的是可解释规则，不是黑盒模型。主要依据包括：

- 姓名和邮箱 local-part 的字面对应
- 缩写模式
- grouped email 展开后的对应关系
- 页面内相邻关系
- 作者顺序和邮箱顺序
- 对应作者标记与 correspondence hint

输出的 `pairs` 是“已确认 pair”，不是所有可能 pair，也不是模糊候选池。

#### 结构化组装层

`assemble_structured_output.py` 把前面各层输出整理为统一结构，包括：

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

这一层存在的意义，是把“抽取结果”和“对外消费的结构化语义”分开。前面的模块聚焦发现候选和确认匹配，这一层负责把结果解释成 V1 对外字段。

### 3.2 数据如何从 `pdf_path` 流到最终 JSON

可以把主链路理解成下面这条流：

`pdf_path`
-> `app.py` 校验请求和路径
-> `pipeline.py` 调度
-> `pdf_extract.py` 产出 `pages`
-> `author_extract.py` 产出 `authors`
-> `email_extract.py` 产出 `emails`
-> `author_email_match.py` 产出已确认 `pairs`
-> `assemble_structured_output.py` 组装结构化对象
-> `app.py` 把结构化对象序列化进 `structured_email_string`
-> API 返回最终 JSON envelope

各层的典型输入输出如下：

- API 层输入：HTTP JSON，请求体里只有 `pdf_path`
- pipeline 层输入：文件路径；输出：包含 pages、authors、emails、pairs、structured_output、stats 的运行结果
- PDF 层输入：PDF 文件路径；输出：`PageText[]`
- 邮箱层输入：`PageText[]`；输出：`EmailCandidate[]`
- 作者层输入：`PageText[]`；输出：`AuthorCandidate[]`
- 匹配层输入：`AuthorCandidate[] + EmailCandidate[] + pages`；输出：`AuthorEmailPair[]`
- 组装层输入：authors、emails、pairs、pages；输出：结构化 payload

### 3.3 为什么要分成这些模块

这样拆分主要是为了维护成本可控：

- PDF 抽取问题和邮箱规则问题本质不同，不应该混在一起改
- 作者抽取和作者-邮箱匹配是两个不同阶段，拆开后更容易定位误差
- API 契约是稳定面，内部规则是可迭代面，必须分层
- 每层都能单独 smoke 和回归，不需要每次从 HTTP 接口整链调试

## 4. 各模块职责说明

### `app.py`

这是服务入口和对外交付层。接手者如果要看“接口怎么收请求、怎么回错误码、为什么返回 `structured_email_string` 而不是对象”，应该先看这里。它定义 FastAPI 应用、请求模型、首页极简 UI、错误码映射，以及调用 `run_pipeline` 后如何包装成功或失败响应。

关键职责：

- 暴露 `GET /` 极简页面和 `POST /extract-author-emails`
- 校验 `pdf_path` 是否存在且是文件
- 把 pipeline 结果包装成 `structured_email_string + stats + code + message`
- 把异常映射成 `INVALID_REQUEST`、`PATH_NOT_FOUND`、`PARSE_FAILED`、`NO_EMAIL_FOUND`、`INTERNAL_ERROR`

### `pipeline.py`

这是项目内部的总装配线。接手者如果要理解“整体流程怎么跑、哪里决定错误码、为什么没有邮箱时直接返回 `NO_EMAIL_FOUND`”，应该重点看这里。它不负责具体抽取算法，而是决定各模块的执行顺序、失败边界和最终统计来源。

关键职责：

- 串联 `extract_pages`、`extract_authors_from_pages`、`extract_emails_from_pages`、`match_authors_and_emails`、`assemble_structured_output`
- 维护默认页数上限 `DEFAULT_MAX_PAGES = 2`
- 生成运行期统计和 `PipelineRunResult`
- 在关键阶段抛出 `PipelineError`

### `pdf_extract.py`

这是 PDF 页面文本入口。接手者如果遇到“PDF 能打开但抽不出字”“不同 PDF 提取器表现不一致”“为什么作者抽取依赖行和块”，应来看这里。它负责把前几页 PDF 转成后续规则可消费的页面对象。

关键职责：

- 读取 PDF 并限制最大页数
- 优先使用 `fitz`，必要时回退 `pdfplumber`
- 输出包含文本、行、块和错误信息的 `PageText`
- 提供简单可解释的文本可读性判断

### `email_extract.py`

这是邮箱候选抽取器。接手者如果要改邮箱规则、补 grouped email、增加混淆邮箱支持，应来看这里。它的输出不是最终邮箱归属，而是“邮箱候选池”。

关键职责：

- 从文本中提取普通邮箱、分组邮箱和部分混淆邮箱
- 展开 `{a,b}@domain`、`a/b@domain` 等写法
- 去重并保留来源页、匹配类型、置信度、源片段
- 过滤明显噪声邮箱

### `author_extract.py`

这是作者列表抽取器。接手者如果要改“作者区识别”“作者顺序恢复”“作者脚注标记保留”等逻辑，应来看这里。它的目标是稳定抽出作者序列，而不是做通用实体识别。

关键职责：

- 从页面顶部优先抽取作者区
- 使用行级解析，必要时退回块级解析
- 过滤摘要、单位、正文、URL、邮箱等非作者噪声
- 给作者赋 `author_index`，保留 `markers`

### `author_email_match.py`

这是保守匹配器。接手者如果要改“为什么某个作者没有邮箱”“为什么没有强行补第一作者邮箱”“如何接受或拒绝某个 pair”，应该先看这里。最终 `pairs` 是否成立，主要由这一层决定。

关键职责：

- 基于姓名与邮箱 local-part 规则生成匹配证据
- 使用相邻性、顺序、marker、correspondence hint 做加分
- 拒绝低置信度或边界过近的模糊匹配
- 输出已确认 `AuthorEmailPair`

### `assemble_structured_output.py`

这是结构化语义组装器。接手者如果要改最终 payload 字段、`first_author` 语义、`first_author_email` 产出条件、地域分类或未匹配项输出，应来看这里。它不负责发现候选，只负责把已有结果组织成对外可解释的结构。

关键职责：

- 构建最终 payload 字段
- 根据作者顺序生成 `first_author`
- 只从 confirmed pair 中生成 `first_author_email`
- 按保守域名规则给已确认邮箱分类地域
- 生成 `shared_emails`、`unmatched_authors`、`unmatched_emails` 和 `stats`

### `call_api.ps1`

这是面向 PowerShell 使用者的轻量调用包装脚本。它不改变接口语义，只是把请求发送和结果展示变得更省事。接手者如果要看“命令行下如何最直接验证当前服务”，可以看这里。

关键职责：

- 接收 PDF 路径参数并调用 `POST /extract-author-emails`
- 解析 `structured_email_string`
- 默认只打印摘要字段
- 可选打印完整响应

### `client.py`

这是 Python 版轻量客户端。它和 `call_api.ps1` 的定位类似，但更适合 Python 用户或跨平台命令行环境。接手者如果要快速写自动化调用或复用请求逻辑，可以先参考这里。

关键职责：

- 通过 `requests` 调用本地 API
- 解析 `structured_email_string`
- 打印 `first_author`、`first_author_email`、`first_author_region`
- 支持自定义 `base-url` 和完整响应输出

### `README.md`

这是运行与调用说明的主文档。接手者如果要先把服务跑起来、知道接口怎么调、知道错误码和常见限制，应该先看它。它的定位偏“怎么用”，不是“为什么这样设计”。

关键职责：

- 说明项目用途、依赖安装和启动方式
- 说明浏览器、Swagger、PowerShell、curl、Python 等调用方法
- 解释顶层响应和错误码
- 记录 V1 关键限制和 FAQ

### `docs/QUICKSTART.md`

仓库中实际存在的快速文档位于 `docs/QUICKSTART.md`。它的定位是“一分钟跑通”，适合第一次验证环境是否正常。接手者如果只想先确认服务能用，再进入代码，可以先看它。

关键职责：

- 用最短路径说明安装、启动和最简调用
- 提醒唯一必填字段是 `pdf_path`
- 指明最先该看 `code`、`first_author`、`first_author_email`
- 强调 V1 中 `first_author` 的固定语义

## 5. 核心数据流说明

### `authors`

`authors` 是作者抽取层产出的有序作者列表。它来自 `author_extract.py`，已经带上作者顺序、页码、标记和源片段。后续 `first_author` 的判断直接依赖这个列表的顺序。

### `first_author`

`first_author` 不是另外再猜出来的人，而是最终组装层从 `authors[0]` 直接拿到的“作者顺序第一位”。它来自最终组装，但语义基础来自作者抽取结果。

### `emails`

`emails` 是邮箱抽取层识别出的邮箱候选列表，来源于 `email_extract.py`。它表示“看到过这些邮箱”，不等于“这些邮箱都已经知道归属给谁”。

### `pairs`

`pairs` 是匹配层最终确认下来的作者-邮箱对应关系，来源于 `author_email_match.py`。只有通过规则阈值且没有冲突的 pair 才会出现在这里，所以它表示“已确认关系”，不是“猜测关系”。

### `first_author_email`

`first_author_email` 来自最终组装层，但它只会从 `pairs` 中查找“第一作者对应的已确认邮箱”。如果第一作者没有 confirmed pair，这个字段就保持 `null`。

### `first_author_region`

`first_author_region` 只在 `first_author_email` 已存在时才会生成。它来源于最终组装层对已确认邮箱域名做的保守地域分类，不是从 PDF 中直接抽出来的字段。

### `unmatched_authors`

`unmatched_authors` 是作者列表里那些没有进入已确认 `pairs` 的作者。它来自最终组装层通过“作者全集减去已配对作者”得到，作用是告诉维护者和调用方：这些作者不是没抽到，而是没能确认邮箱归属。

### `unmatched_emails`

`unmatched_emails` 是邮箱候选列表里那些没有进入已确认 `pairs` 的邮箱。它来自最终组装层通过“邮箱全集减去已配对邮箱”得到，作用是告诉维护者和调用方：这些邮箱被看到了，但当前规则没有确认归属作者。

### `stats`

`stats` 是最终结果的摘要计数，主要由组装层输出，外层 envelope 会直接复用。它用来快速判断这一轮结果的规模和状态，例如作者数、邮箱数、pair 数、未匹配数量以及是否找到第一作者。当前运行结果里还会带有 `has_first_author_email` 这样的辅助标记，但核心理解可以先抓住“它是摘要而不是明细”。

### 字段来源关系一图看懂

- 抽取层产生：`authors`、`emails`
- 匹配层产生：`pairs`
- 组装层派生：`first_author`、`first_author_email`、`first_author_region`、`unmatched_authors`、`unmatched_emails`、`stats`

## 6. `first_author` / `first_author_email` 是怎么得到的

先看 `first_author`。作者抽取成功后，作者列表会被按作者顺序编号，组装层直接把列表第一位作为 `first_author`，并给出 `reason = first_by_author_order`。这里没有通讯作者优先、没有共同一作改写、没有根据邮箱反推作者顺序。

再看 `first_author_email`。匹配层先独立产出一组已确认 `pairs`。组装层再去这些 `pairs` 中找“作者名等于 `first_author.author_norm` 的那一条”。只有找到已确认 pair，才会写入 `first_author_email`；否则保持 `null`。随后，只有当 `first_author_email` 存在时，才继续用邮箱域名做 `first_author_region` 判断。

可以简化成下面这条规则链：

`authors[0]`
-> `first_author`
-> 在 `pairs` 里找第一作者对应项
-> 找到则写 `first_author_email`
-> 再基于这个邮箱写 `first_author_region`

## 7. 当前版本的关键规则

### 1. `first_author` 永远表示作者顺序上的第一作者

这样设计，是为了把 V1 语义固定住，避免“第一作者”“通讯作者”“共同一作主作者”三个概念混在一起。对接方和维护者都能明确知道：只要作者列表顺序没变，`first_author` 的含义就不变。

### 2. `first_author` 不是通讯作者

这样设计，是为了防止首页常见的 correspondence 标记把语义带偏。通讯作者常常有星号或专门脚注，但这不等于作者顺序第一位。当前项目把“通讯关系”和“第一作者定义”严格拆开，属于明确约束，不是遗漏。

### 3. 共同一作不会改变 V1 的 `first_author` 语义

这样设计，是为了先把外部字段语义冻结。项目已经预留了 `co_first_authors` 和 `equal_contribution_detected`，但 V1 不会因为检测到共同一作文本，就改写 `first_author`。这样后续即使增强共同一作处理，也不需要回滚旧接口含义。

### 4. `first_author_email` 只来自已确认 `pair`

这样设计，是为了保证这个字段一旦出现，就有明确证据链。接手维护时要把它理解为“确认结果”，不是“系统尽量给一个邮箱”。这能降低误报，特别是在首页存在 grouped email、脚注邮箱或共享邮箱时。

### 5. 不会为了补 `first_author_email` 反向强配

这样设计，是为了让系统在证据不足时宁可返回 `null`。如果为了业务完整性强行从邮箱顺序、通讯作者说明或弱相邻性反推第一作者邮箱，错误会比缺失更难维护和解释。

### 6. 地域分类只基于已确认邮箱做保守判断

这样设计，是因为地域分类本来就是附加字段，不应该凌驾于匹配正确性之上。只有邮箱已经确认，才谈得上根据域名粗分 `CN`、`OVERSEAS` 或 `UNKNOWN`。这避免了“邮箱都不确定，却先给地域标签”的误导。

### 7. 当前默认只看首页和必要时前两页

这样设计，是基于论文作者区和邮箱区通常集中在首页附近，且这是性价比最高的抽取范围。代码中默认页数上限是 `2`，说明当前工程目标是覆盖首页及其紧邻补充页，而不是扫描整篇论文。

### 8. 这是规则工程 + 样本集回归迭代，不是训练参数化模型

这样设计，是为了保持结果可解释、可调试、可局部修复。当前实现依赖规则、正则、阈值和样本集 smoke 回归，没有训练流程、模型文件或参数学习环节。接手者维护时应该优先从规则和样本回归角度思考，而不是去找不存在的训练管线。

## 8. 当前版本没有做什么

为了防止接手者误判边界，下面这些事情当前版本没有覆盖：

- 不是 OCR 项目。对 OCR 很差或纯扫描 PDF，当前提取可能失败。
- 不是通用论文理解系统。它不做摘要理解、机构理解、作者角色全面推理。
- 没有做复杂部署工程。当前定位是本地可运行微服务。
- 没有做上传文件接口。输入是已有 PDF 的路径，不是浏览器上传。
- 没有做 URL 拉取输入。不会自己下载远程 PDF。
- 没有做登录鉴权。接口默认面向本地或受控环境使用。
- 没有做生产级监控、告警、链路追踪。
- 不是机器学习训练型系统。没有训练、微调、权重管理或在线学习。

## 9. 如何阅读这个项目（给新接手者的阅读顺序）

推荐按下面顺序看：

1. `README.md`
2. `docs/QUICKSTART.md`
3. `app.py`
4. `pipeline.py`
5. `pdf_extract.py`
6. `email_extract.py`
7. `author_extract.py`
8. `author_email_match.py`
9. `assemble_structured_output.py`
10. `step8_review.md`

为什么这样看：

1. 先看 `README.md`
   看完应该知道项目输入输出、怎么启动、怎么调用、错误码有哪些、V1 的对外边界是什么。

2. 再看 `docs/QUICKSTART.md`
   看完应该能用最短路径把服务跑起来，并知道最先看哪些返回字段。

3. 再看 `app.py`
   看完应该知道服务入口、外层响应格式、错误码映射和 `structured_email_string` 的包装方式。

4. 然后看 `pipeline.py`
   看完应该知道整条内部流水线如何串起来，哪里决定中途失败，哪里产生统计。

5. 再按“先抽取、后匹配、再组装”的顺序看各模块
   看完后应该能回答：作者从哪里来，邮箱从哪里来，pair 从哪里来，最终结果在哪里拼。

6. 最后看 `step8_review.md`
   看完应该能对齐当前版本的交付范围、已验证点和已知限制，避免把现在的行为误判成 bug。

## 10. 如何验证自己已经看懂了

接手者至少应当能完成下面这个最小 checklist：

- 能用一句话说明项目是做“论文 PDF 作者邮箱结构化抽取”的本地微服务
- 能说清输入是 `pdf_path`，输出外层是 envelope，内层在 `structured_email_string`
- 能说清整条流程是“抽文本 -> 抽邮箱 -> 抽作者 -> 做匹配 -> 组装结果 -> API 返回”
- 能说明 `first_author` 指的是作者顺序第一位，不是通讯作者
- 能说明 `first_author_email` 只来自已确认 `pairs`
- 能指出作者抽取在 `author_extract.py`
- 能指出邮箱抽取在 `email_extract.py`
- 能指出作者-邮箱匹配在 `author_email_match.py`
- 能指出最终 payload 组装在 `assemble_structured_output.py`
- 能本地启动服务并通过首页、`call_api.ps1` 或 `client.py` 拿到结果

## 11. 当前限制与未来扩展方向

### 当前限制

- 默认只覆盖首页及前两页范围，超出范围的邮箱和脚注可能看不到
- 对扫描质量差、OCR 噪声重的 PDF 不够稳
- `shared_emails` 仍然偏保守，依赖明确的确认 pair
- 共同一作只做保留字段和辅助检测，不改写 V1 `first_author`
- `first_author_region` 只是域名级粗分类，不是精细地域识别
- 外层仍以 `structured_email_string` 传内层结果，客户端需要二次解析

### 未来最可能的扩展方向

- 支持上传文件或 URL 输入，而不只接受本地路径
- 增加容器化和 Docker 交付
- 部署到服务器并补齐基础运维能力
- 引入更强的 OCR 支持，提高扫描 PDF 的可用性
- 增强 shared email 和多对一关系处理
- 扩展更多论文模板和版式兼容规则

这里的重点是“说明可能扩展什么”，不是要求本轮实现这些能力。
