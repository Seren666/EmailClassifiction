# Sample Coverage Report

- 文件用途：跟踪当前 30 篇 paper pool 的草稿覆盖情况。
- 什么时候使用：下载 PDF 前安排批次，或补完若干篇样本后回看覆盖面时使用。
- 我应该怎么维护：这里统计的是 `paper pool / draft coverage`，不是“已完成真值标注”的最终统计。

## 当前统计

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| 当前样本位数量 | 30 | 当前已在 `data/samples_v1.csv` 中落了 30 个草稿样本位 |
| high priority | 10 | 适合先做 deep annotation |
| medium priority | 10 | 第二批处理 |
| normal priority | 10 | 第三批处理 |

## 覆盖 Checklist（draft estimate）

| 覆盖项 | 状态 | 当前样本 ID | 备注 |
| --- | --- | --- | --- |
| 作者顺序清晰 | covered | S001-S013, S015-S026, S028-S030 | 28/30 篇已从公开线索拿到 ordered authors；S014、S027 仍待 PDF 确认 |
| 通讯作者标记 | covered | S001, S002, S003, S004, S005, S006, S009, S010, S013, S014, S015, S016 | 来自 `corresponding_author` 或 `multiple_corresponding_emails` 信号 |
| 共同一作说明 | covered | S001, S002, S004, S006, S007, S008, S009, S010, S011, S012, S013, S015 | 这里只表示 draft pool 已覆盖，不代表 co-first 真值已完成 |
| 共享邮箱 / 分组邮箱 | covered | S005, S006, S007, S008, S009, S010, S014 | grouped email 覆盖已具备 |
| IEEE | pending |  | 当前 30 篇清单全部是 arXiv 预期来源 |
| ACM | pending |  | 当前 30 篇清单全部是 arXiv 预期来源 |
| Elsevier | pending |  | 当前 30 篇清单全部是 arXiv 预期来源 |
| arXiv | covered | S001-S030 | 当前 pool 全部为 arXiv |
| one-column | pending |  | PDF 未下载前统一保守写 `layout_guess=unknown` |
| two-column | pending |  | PDF 未下载前统一保守写 `layout_guess=unknown` |

## Ready for deep annotation now

| sample_id | title | why ready now |
| --- | --- | --- |
| S001 | The Scientometrics and Reciprocality Underlying Co-Authorship Panels in Google Scholar Profiles | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S002 | iCub Detecting Gazed Objects: A Pipeline Estimating Human Attention | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S003 | A MapReduce Approach to Effectively Utilize Long Context Information in Retrieval Augmented Language Models | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S004 | Jekyll-and-Hyde Tipping Point in an AI’s Behavior | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S005 | WritingBench: A Comprehensive Benchmark for Generative Writing | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S006 | EvolveSearch: An Iterative Self-Evolving Search Agent | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S007 | AGENTLESS: Demystifying LLM-based Software Engineering Agents | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S008 | Graph-Augmented Relation Extraction Model with LLMs-Generated Support Document | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S009 | MemBench: Towards More Comprehensive Evaluation on the Memory of LLM-based Agents | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |
| S010 | AMR-Transformer: Enabling Efficient Long-range Interaction for Complex Neural Fluid Simulation | high priority with stronger public signals; PDF到位后可直接核对作者区和邮箱区 |

## 当前最缺的样本类型

- 非 arXiv 来源样本仍然缺失，后续若扩池需要补 IEEE / ACM / Elsevier。
- 版式信息仍然缺失，PDF 到位后需要补 `one-column` / `two-column`。
- S014 和 S027 的 ordered authors 仍待从 PDF 首屏确认。
- 所有 co-first 作者列表当前都保守写成 `[]`，需要 PDF 到位后逐篇核对。
- 多数 pair 仍是保守空值，只有少数直接公开线索样本做了局部预填。
