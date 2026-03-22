# Step 2 Review

- 文件用途：说明当前 Step 2 已经把 30 篇 paper pool 和草稿样本位落地到什么程度。
- 什么时候使用：你想快速确认现在还需要做哪些人工动作时使用。
- 我应该怎么维护：继续把 Step 2 限定在模板、草稿和人工校对准备上，不提前进入第 3 步。

## 当前状态

- 已建立 `data/paper_pool_30.md`，整理 30 篇 paper pool。
- 已建立 `data/download_checklist_30.md`，列出 30 个预期 PDF 文件名。
- 已把 30 个 draft rows 落到 `data/samples_v1.csv`。
- 当前多数样本仍然只是 `web-preannotated draft`，不是已完成真值。
- 真正 `done` 之前，仍需要 PDF 到位后逐篇核对首屏作者区和邮箱区。

## 这样做的目的

- 把后续工作压缩到“下载 PDF + 少量核对补充 + 跑校验脚本”。
- 先把公开可确认的作者顺序、已知邮箱和少量直接 pair 保守写入主表。
- 对不能直接确认的字段继续保守留空，避免后续返工。

## 你接下来真正要做的事

1. 按 `data/download_checklist_30.md` 下载 PDF 到 `papers/raw/`。
2. 打开 `data/samples_v1.csv`，逐篇核对和补完尚未确认的字段。
3. 需要时再补单篇备注。
4. 运行 `python scripts/validate_samples.py`。

## 当前没有做什么

- 没有进入第 3 步。
- 没有 PDF 解析。
- 没有邮箱抽取。
- 没有作者抽取。
- 没有作者-邮箱匹配。
- 没有地域分类业务实现。
