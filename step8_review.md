# Step 8 Review

- 本轮只实现了 Step 8：Pipeline 串联与微服务化交付。
- 没有回改 Step 3 / 4 / 5 / 6 / 7 的核心语义。
- 没有新增新的抽取算法模块。

## 本轮实现了什么

- 新增 [`pipeline.py`](./pipeline.py)，把以下模块串联到一条可调用流水线中：
  - [`pdf_extract.py`](./pdf_extract.py)
  - [`email_extract.py`](./email_extract.py)
  - [`author_extract.py`](./author_extract.py)
  - [`author_email_match.py`](./author_email_match.py)
  - [`assemble_structured_output.py`](./assemble_structured_output.py)
- 新增 [`app.py`](./app.py)，提供：
  - `POST /extract-author-emails`
  - 统一 envelope 包装
  - 稳定错误码映射
  - 参数校验、路径校验、异常捕获
- 新增 [`README.md`](./README.md)，提供安装、启动、调用、错误码、限制与 smoke 用法说明。
- 新增 [`scripts/run_api_smoke.py`](./scripts/run_api_smoke.py)，用于 API 层 smoke 与 schema 校验。

## 已串联的模块

- PDF 首页 / 前两页文本抽取
- 邮箱候选抽取
- 作者列表抽取
- 作者-邮箱保守匹配
- Step 7 结构化中间结果组装
- API envelope 包装

## 已覆盖的错误码

- `INVALID_REQUEST`
- `PATH_NOT_FOUND`
- `PARSE_FAILED`
- `NO_EMAIL_FOUND`
- `INTERNAL_ERROR`

## README 提供了什么

- 项目用途
- 依赖安装命令
- FastAPI 启动命令
- `curl` 请求示例
- 成功响应示例
- 错误码说明
- 已知限制
- `first_author` 的 V1 定义说明
- smoke test 运行方式

## Smoke 表现

- API 正样本 smoke：13/13 成功。
- schema 校验：
  - 外层 response envelope 全部通过。
  - `structured_email_string` 反序列化后的 inner payload 全部通过 `output.schema.json`。
- 错误码 smoke：
  - `INVALID_REQUEST`、`PATH_NOT_FOUND`、`PARSE_FAILED`、`NO_EMAIL_FOUND` 均已验证通过。
- 额外做了一次真实 HTTP 通路检查：
  - 用 `uvicorn` 启动本地服务后，对 `POST /extract-author-emails` 发起请求并成功返回 `OK` envelope。

## 当前版本已知限制

- API 默认只看首页与必要时前两页。
- `shared_emails` 仍取决于 Step 6 是否形成明确的多作者共享邮箱确认 pair。
- `first_author_region` 仍是非常保守的域名规则，并不等于精细地域识别。
- 如果邮箱根本不在前两页，或 local-part 与姓名弱相关，`first_author_email` 可能保持 `null`。
