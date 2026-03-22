# Annotation Guide V1

- 文件用途：`data/samples_v1.csv` 的填写规则速查手册。
- 什么时候使用：你已经打开主标注表，准备直接填写某一行时使用。
- 我应该怎么维护：只保留 V1 必要规则，和 Step 1 的冻结定义保持一致。

## 核心规则

- `first_author` 永远是作者顺序第一位。
- 通讯作者不改变 `first_author`。
- 共同一作不改变 V1 的 `first_author`。
- 不确定的 pair 不要强配。
- 不确定的信息可以保守留空：数组用 `[]`，对象用 `null`，说明写进 `notes`。

## authors 怎么填

规则：
- 按论文作者出现顺序填写。
- 至少保留 `author_raw`、`author_norm`、`author_index`。
- `author_index` 从 `0` 开始。

最短例子：
```json
[{"author_raw":"Author One*","author_norm":"Author One","source_page":1,"author_index":0,"markers":["*"]}]
```

## `first_author` 怎么填

规则：
- 直接取作者顺序第一位。
- `reason` 固定写 `first_by_author_order`。
- 只有作者顺序无法判断时才写 `null`。

最短例子：
```json
{"author_raw":"Author One*","author_norm":"Author One","source_page":1,"reason":"first_by_author_order"}
```

## `co_first_authors` 什么时候填

规则：
- 只有 PDF 有明确 equal contribution / co-first authors 证据时才填。
- 没证据就填 `[]`。
- 即使填写了 co-first，`first_author` 仍然不变。

最短例子：
```json
[{"author_raw":"Author Two*","author_norm":"Author Two","source_page":1,"author_index":1,"markers":["*"]}]
```

## emails 怎么填

规则：
- 只填你能从 PDF 直接确认的邮箱。
- 共享邮箱或团队邮箱也可以先列入邮箱数组。

最短例子：
```json
[{"email":"author.one@example.com","source_page":1}]
```

## pairs 怎么填

规则：
- 只填写证据明确的作者-邮箱对应关系。
- 不确定就不要强配，宁可填 `[]`。
- `author_norm` 必须引用作者标准名。

最短例子：
```json
[{"author_norm":"Author One","email":"author.one@example.com","region":"OVERSEAS","match_reason":"manual_ground_truth_direct_match"}]
```

## regions 怎么填

规则：
- 这是邮箱级别字段，不是作者级别字段。
- 允许值只有 `CN`、`OVERSEAS`、`UNKNOWN`。
- 没把握就填 `UNKNOWN`，不要猜。

最短例子：
```json
[{"email":"author.one@example.com","region":"OVERSEAS"}]
```

## `notes` 什么时候写

规则：
- 作者顺序无法判断时写。
- 看到了疑似 co-first 但证据不足时写。
- 共享邮箱无法唯一归属时写。
- 你故意保守不填 pair 或 region 时写。
- 如果另建了单篇 note 文件，也在这里留一句指向。

最短例子：
```text
Shared email exists but cannot be uniquely assigned; see S001_sample_note.md.
```