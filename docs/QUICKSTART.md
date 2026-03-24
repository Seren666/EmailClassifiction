# Quickstart

## 1 分钟跑通

1. 安装依赖：

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

2. 启动服务：

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

3. 最省事的两种方式：

- 浏览器打开 `http://127.0.0.1:8000/`
- 命令行执行：

```powershell
.\call_api.ps1 "<ABSOLUTE_PDF_PATH>"
```

或：

```bash
python client.py "<ABSOLUTE_PDF_PATH>"
```

4. 如果使用浏览器，也可以打开：

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

5. 唯一必填项：

- `pdf_path`

示意：

```text
<ABSOLUTE_PDF_PATH>
```

6. 执行后先看：

- `code`
- `first_author`
- `first_author_email`

提示：

- 首页 `/` 适合最省操作的本地测试
- `call_api.ps1` 和 `client.py` 适合最省事的命令行调用
- `first_author` 在 V1 中永远表示作者顺序第一位
