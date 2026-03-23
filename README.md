# Author Email Extraction Service

## 项目用途

这是一个本地可运行的轻量微服务，用于从论文 PDF 中抽取作者、邮箱、作者-邮箱匹配结果，并输出一个 JSON 字符串形式的结构化结果。

V1 的 `first_author` 语义已经冻结为：作者顺序上的第一作者，不是通讯作者，也不是共同一作推断结果。

## 依赖安装

```bash
python -m pip install -r requirements.txt
```

## 启动命令

推荐使用：

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

服务启动后，接口地址为：

```text
POST /extract-author-emails
```

## curl 请求示例

```bash
curl -X POST "http://127.0.0.1:8000/extract-author-emails" ^
  -H "Content-Type: application/json" ^
  -d "{\"pdf_path\":\"E:/VScode/EmailClassifiction/papers/raw/S001_scientometrics_google_scholar_profiles.pdf\"}"
```

## 成功响应示例

```json
{
  "structured_email_string": "{\"authors\":[{\"author_raw\":\"Ariel Alexi1*\",\"author_norm\":\"Ariel Alexi\"}],\"first_author\":{\"author_raw\":\"Ariel Alexi1*\",\"author_norm\":\"Ariel Alexi\",\"source_page\":1,\"reason\":\"first_by_author_order\",\"confidence\":0.96},\"co_first_authors\":[],\"equal_contribution_detected\":false,\"emails\":[{\"email\":\"ariel.147@gmail.com\",\"source_page\":1,\"pattern_type\":\"standard_email\",\"confidence\":0.99,\"source_snippet\":\"ariel.147@gmail.com\",\"region\":\"OVERSEAS\"}],\"pairs\":[{\"author_norm\":\"Ariel Alexi\",\"email\":\"ariel.147@gmail.com\",\"match_reason\":\"exact_localpart_match\",\"source_page\":1,\"confidence\":0.99,\"notes\":\"local_part=ariel matched a unique name token candidate; unique '*' marker under correspondence hint; author order matches email order on page\",\"region\":\"OVERSEAS\"}],\"shared_emails\":[],\"unmatched_authors\":[{\"author_norm\":\"Teddy Lazebnik\",\"reason\":\"no_confirmed_email_match\",\"author_index\":1,\"source_page\":1}],\"unmatched_emails\":[],\"first_author_email\":\"ariel.147@gmail.com\",\"first_author_region\":\"OVERSEAS\",\"stats\":{\"author_count\":3,\"email_count\":1,\"pair_count\":1,\"shared_email_count\":0,\"unmatched_author_count\":2,\"unmatched_email_count\":0,\"first_author_found\":true,\"has_first_author_email\":true}}",
  "stats": {
    "author_count": 3,
    "email_count": 1,
    "pair_count": 1,
    "shared_email_count": 0,
    "unmatched_author_count": 2,
    "unmatched_email_count": 0,
    "first_author_found": true,
    "has_first_author_email": true
  },
  "code": "OK",
  "message": "success"
}
```

## 错误码说明

- `INVALID_REQUEST`
  请求体缺失、不是对象、缺少 `pdf_path`，或 `pdf_path` 为空字符串。
- `PATH_NOT_FOUND`
  `pdf_path` 不存在，或路径不可访问。
- `PARSE_FAILED`
  PDF 存在，但解析或抽取链路失败。
- `NO_EMAIL_FOUND`
  PDF 已解析，但没有抽取到任何邮箱候选。
- `INTERNAL_ERROR`
  未预期的内部异常。

错误响应中：

- `structured_email_string` 固定为空字符串 `""`
- `stats` 仍然存在

## 已知限制

- `first_author` 在 V1 中始终表示作者顺序上的第一作者。
- 不会为了补 `first_author_email` 去反向强配邮箱。
- `first_author_region` 只基于已确认的 `first_author_email` 做保守判断。
- 共同一作与 equal contribution 目前只保留检测和中间字段，不作为强业务结论。
- OCR 很差、首页结构异常或邮箱不在前两页的 PDF，结果仍可能不完整。

## 如何运行 smoke test

Step 8 API smoke：

```bash
python -X utf8 scripts/run_api_smoke.py --limit 13 --show-samples 2
```

Step 7 结构化结果 smoke：

```bash
python -X utf8 scripts/run_step7_smoke.py --limit 13 --show-samples 2
```
