# Fill Workflow

- 文件用途：这是用户实际操作时唯一推荐流程，按这一个顺序完成样本录入、标注、备注和校验。
- 什么时候使用：每新增一篇论文样本时都按这里走，不需要先走其他前置流程。
- 我应该怎么维护：只有当第二步人工流程真的变化时才更新；默认以“直接写 `data/samples_v1.csv`”为中心。

## 使用原则

- `data/samples_v1.csv` 是唯一主标注表，默认直接写它。
- `data/sample_inventory.md` 不是必填，不是前置，只是可选补充记录。
- `data/annotation_notes/` 只在复杂样本、字段不确定或需要复核时才使用。

## 1. 选择一篇论文

做什么：
- 选一篇你想纳入样本集的论文。
- 目标是补足不同模板、版式和难点类型，不需要先做“值不值得收录”的单独流程。

填哪些文件：
- 这一步不用先填任何文件。

完成标志：
- 你已经确定下一篇要标注的 PDF。

常见错误：
- 还没决定论文就先创建多条空白记录，后面容易对不上文件。

## 2. 下载并重命名 PDF

做什么：
- 下载 PDF。
- 用 `SXXX_short_name.pdf` 的方式重命名，让文件名和 `sample_id` 对齐。

填哪些文件：
- 这一步还不用填表，只确定文件名。

完成标志：
- PDF 文件名已经稳定，不会再随意改。

常见错误：
- 先在主表里写了路径，后面又改文件名，导致 CSV 和真实文件不一致。

## 3. 放入 `papers/raw/`

做什么：
- 把 PDF 放到 `papers/raw/`。
- 后续 `pdf_path` 一律写相对路径，例如 `papers/raw/S001_example.pdf`。

填哪些文件：
- 暂无；只是把文件放到正确目录。

完成标志：
- 你能在 `papers/raw/` 找到该 PDF。

常见错误：
- PDF 在别的目录，CSV 却写成 `papers/raw/...`。

## 4. 直接在 `data/samples_v1.csv` 追加一行

做什么：
- 复制模板行，追加一行新样本记录。
- 先填 `sample_id`、`pdf_path`、`file_exists`、`annotation_status` 和基础占位值。

填哪些文件：
- `data/samples_v1.csv`

完成标志：
- 主表中已经有新样本的一整行。
- 所有 `*_json` 列都不是空白单元格。

常见错误：
- 忘记给 JSON 列填 `[]` 或 `null`。
- 还没放 PDF 就把 `file_exists` 写成 `true`。

## 5. 填写基础字段

做什么：
- 填 `source_format_guess`、`layout_guess`、`has_corresponding_author_marker`、`has_equal_contribution_note`、`has_shared_or_group_email`。
- 这些字段是覆盖标签，不是自动业务结果。

填哪些文件：
- `data/samples_v1.csv`

完成标志：
- 该行的基础标签已能反映这篇论文的大致类型。

常见错误：
- 把“看不清”留空；应该写 `unclear` 或按模板占位后尽快补齐。

## 6. 填写 authors 与 `first_author`

做什么：
- 先写 `ground_truth_authors_json`。
- 再写 `ground_truth_first_author_json`。
- `first_author` 永远来自作者顺序第一位。

填哪些文件：
- `data/samples_v1.csv`
- 必要时参考 `data/annotation_guide_v1.md`

完成标志：
- 作者顺序明确。
- `ground_truth_first_author_json.reason` 已写成 `first_by_author_order`。

常见错误：
- 把通讯作者写成 `first_author`。
- 因为看到共同一作说明，就改掉 V1 的 `first_author`。

## 7. 填写 emails / pairs / regions

做什么：
- 先写 `ground_truth_emails_json`。
- 再只填写明确的 `ground_truth_pairs_json`。
- 最后写 `ground_truth_email_regions_json`。

填哪些文件：
- `data/samples_v1.csv`

完成标志：
- 所有能确认的邮箱都已记录。
- 不确定的 pair 没有被强配。
- 需要时已给邮箱补上 `CN` / `OVERSEAS` / `UNKNOWN`。

常见错误：
- 为了让表更完整，硬填不确定的配对。
- region 没把握时乱猜，而不是填 `UNKNOWN`。

## 8. 如有模糊点，再创建单篇备注

做什么：
- 只有样本复杂、字段不确定、需要复核时，才复制 `data/annotation_notes/TEMPLATE_sample_note.md`。
- 改名为 `SXXX_sample_note.md` 并记录争议点。

填哪些文件：
- `data/annotation_notes/SXXX_sample_note.md`
- `data/samples_v1.csv` 的 `notes`

完成标志：
- 复杂判断有单独备注可追溯。
- `notes` 中有简短说明或文件指向。

常见错误：
- 每篇都建 note，反而增加维护负担。
- 有争议却不留说明，后面无法复核。

## 9. 更新 `data/sample_coverage_report.md`

做什么：
- 顺手更新样本数量、覆盖 checklist、最近新增样本和缺口。
- 这不是前置步骤，而是录入后或完成若干样本后做的统计维护。

填哪些文件：
- `data/sample_coverage_report.md`

完成标志：
- 你能从 coverage report 一眼看出当前还缺什么类型的样本。

常见错误：
- 长时间不更新，最后不知道样本池是否过度重复。

## 10. 运行 `scripts/validate_samples.py`

做什么：
- 运行 `python scripts/validate_samples.py`。
- 根据输出修正主表中的路径、状态、JSON 格式等问题。

填哪些文件：
- 可能回改 `data/samples_v1.csv`

完成标志：
- 脚本输出通过，没有错误行。

常见错误：
- 以为模板能看懂就不做验证，直到后续实现阶段才暴露格式问题。