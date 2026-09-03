# 2ndLA 原始短语词典 → SQLite 数据库规范化规则

## 1. 文档目的

本文档仅定义：

> 如何将 2ndLA 原始短语词典中的自然语言短语模板、占位符和省略号表达，规范化、编译并存储到 SQLite 数据库中。

目标：

- 保留原始词典信息；
- 避免运行时直接解析 `…`、`sb.`、`sth.` 等编辑记号；
- 将所有短语模板转换为统一、可执行的结构；
- 支持固定短语、可变短语、占位短语；
- 保证数据库结构稳定、可重建、可版本化；
- 方便后续扩展新的模板类型而不修改原始数据。

---

## 2. 输入数据

当前 2ndLA 数据源：

```text
entries.jsonl
translation-full-output.jsonl
manifest.json
```

其中可能存在：

```text
be all eyes
look forward to
add…to…
as…as
remind sb. of sth.
prevent sb. from doing sth.
keep one's eyes open
```

原始数据不得直接修改。

推荐目录：

```text
data-source/
└─ 2ndla/
   ├─ entries.jsonl
   ├─ translation-full-output.jsonl
   └─ manifest.json
```

构建阶段生成：

```text
phrases.db
manifest.json
ATTRIBUTION.txt
```

---

## 3. 总体转换流程

```text
原始 entry
→ 合并翻译
→ 基础清洗
→ 识别模板类型
→ 规范化 canonical form
→ 编译 pattern token
→ 选择 anchor
→ 写入 SQLite
→ 完整性校验
```

所有转换均发生在构建阶段。

运行时不得重新解析原始 JSONL。

---

## 4. 数据保留原则

每个短语在构建阶段必须保留三层信息：

```text
source_pattern
canonical_pattern
phrase_pattern_token
```

其中 `phrase_pattern_token` 是唯一的运行时可执行结构。`compiled_pattern` 不写入发布数据库，避免序列化结果和 token 表出现两份不一致的真相。

### 4.1 source_pattern

原始词典字符串，例如：

```text
add…to…
```

必须原样保留。

用途：

- 数据来源追踪；
- 调试；
- 重新编译；
- 前端必要时展示原词典形式。

### 4.2 canonical_pattern

统一后的规范可读形式，例如：

```text
add <SLOT> to <SLOT>
```

或：

```text
as <GAP> as
```

用途：

- 调试；
- 管理页面；
- 数据验证；
- 版本迁移。

### 4.3 phrase_pattern_token

构建阶段将模板拆分为 `phrase_pattern_token`，例如：

```text
LITERAL(add)
SLOT(OBJECT)
LITERAL(to)
SLOT(OBJECT)
```

运行时匹配只依赖 `phrase_pattern_token`。发布库不再保存 `compiled_pattern`。

---

## 5. 基础文本规范化

构建前统一执行：

```text
Unicode 规范化
统一英文引号
统一空格
去除首尾空白
连续空格压缩
统一省略号表示
统一占位符大小写
```

例如：

```text
add...to...
add … to …
add…to…
```

都应识别为同类模板。

但 `source_pattern` 必须保留输入原文。

---

## 6. 模板元素类型

第一版仅支持以下内部元素：

```text
LITERAL
GAP
SLOT
```

必要时保留 `slot_hint`。

### 6.1 LITERAL

固定词，例如：

```text
look
forward
to
```

存储：

```text
token_type = LITERAL
match_type = NORMALIZED 或 LEMMA
match_value = 对应值
```

### 6.2 GAP

表示未知但有限长度的中间内容。

原始来源：

```text
…
...
```

例如：

```text
as…as
```

转换：

```text
LITERAL(as)
GAP(min=1,max=3)
LITERAL(as)
```

### 6.3 SLOT

表示词典明确给出的语义或语法槽位，例如：

```text
sb.
sth.
one's
doing sth.
```

统一编译为 `SLOT`，并使用 `slot_hint` 保留语义提示。

第一版 `slot_hint` 可支持：

```text
PERSON
THING
POSSESSIVE
VERB
GERUND
OBJECT
GENERIC
```

`slot_hint` 第一版主要用于描述和后续扩展，不作为严格语义判定依据。

---

## 7. 原始记号转换规则

### 7.1 省略号

以下形式统一识别：

```text
…
...
……
```

若省略号位于两个固定词之间：

```text
as…as
```

转换：

```text
GAP(min_tokens=1,max_tokens=3)
```

若位于短语末尾，如：

```text
add…to…
```

应结合模板结构编译为槽位，而不是无界 GAP。

推荐：

```text
add <OBJECT> to <OBJECT>
```

### 7.2 sb.

识别：

```text
sb.
sb
somebody
someone
```

在词典模板语义明确时统一为：

```text
SLOT(slot_hint=PERSON)
```

默认：

```text
min_tokens = 1
max_tokens = 4
```

### 7.3 sth.

识别：

```text
sth.
sth
something
```

统一为：

```text
SLOT(slot_hint=THING)
```

默认：

```text
min_tokens = 1
max_tokens = 5
```

### 7.4 one's

识别：

```text
one's
oneself
```

根据模板语义分别映射为 `POSSESSIVE` 或 `REFLEXIVE`。

第一版可统一简化为：

```text
SLOT(slot_hint=POSSESSIVE)
```

### 7.5 doing sth.

拆分为：

```text
SLOT(slot_hint=GERUND)
SLOT(slot_hint=THING)
```

若原词典明显表达一个整体动作宾语，后续可扩展 `GERUND_PHRASE`，第一版不建议引入过多类型。

---

## 8. 固定短语处理

对于无占位符、无省略号短语：

```text
be all eyes
look like
give up
fall apart
```

直接编译为固定 token 序列。

但不能机械执行逐词 lemma 后拼接。

例如：

```text
be all eyes
```

应保存：

```text
canonical_phrase = be all eyes
```

pattern：

```text
LEMMA(be)
NORMALIZED(all)
NORMALIZED(eyes)
```

而不是：

```text
be all eye
```

原则：

> 单词层 lemma 归一和短语 canonical form 是两个不同概念。

---

## 9. 固定词的匹配类型

每个 LITERAL 应显式保存匹配方式。

推荐支持：

```text
LEMMA
NORMALIZED
SURFACE
```

### 9.1 动词核心词

优先使用 `LEMMA`。

例如：

```text
be
look
give
fall
```

可匹配词形变化。

### 9.2 固定复数、固定功能词

优先使用 `NORMALIZED`。

例如：

```text
eyes
all
to
of
```

防止固定形态被错误 lemma 化。

### 9.3 严格表面形式

使用 `SURFACE`。

第一版尽量少使用。

---

## 10. 推荐数据库结构

### 10.1 phrase_entry

```sql
CREATE TABLE phrase_entry (
    id INTEGER PRIMARY KEY,
    source_pattern TEXT NOT NULL,
    canonical_pattern TEXT NOT NULL,
    definition_en TEXT,
    definition_zh TEXT,
    usage_note_zh TEXT,
    phrase_type TEXT NOT NULL,
    source TEXT NOT NULL,
    source_entry_id TEXT UNIQUE NOT NULL,
    source_metadata_json TEXT,
    token_count_min INTEGER NOT NULL,
    token_count_max INTEGER NOT NULL,
    match_priority INTEGER NOT NULL DEFAULT 0
);
```

推荐 `phrase_type`：

```text
IDIOM
PHRASAL_VERB
FIXED_EXPRESSION
VERB_PREPOSITION
ADJECTIVE_PREPOSITION
PATTERN
OTHER
```

### 10.2 phrase_pattern_token

```sql
CREATE TABLE phrase_pattern_token (
    id INTEGER PRIMARY KEY,
    phrase_id INTEGER NOT NULL,
    pattern_position INTEGER NOT NULL,
    token_type TEXT NOT NULL,
    match_type TEXT,
    match_value TEXT,
    slot_hint TEXT,
    min_tokens INTEGER,
    max_tokens INTEGER,
    FOREIGN KEY (phrase_id) REFERENCES phrase_entry(id)
);
```

`token_type`：

```text
LITERAL
GAP
SLOT
```

### 10.3 phrase_anchor

```sql
CREATE TABLE phrase_anchor (
    phrase_id INTEGER NOT NULL,
    anchor_position INTEGER NOT NULL,
    anchor_type TEXT NOT NULL,
    anchor_value TEXT NOT NULL,
    PRIMARY KEY (phrase_id, anchor_position),
    FOREIGN KEY (phrase_id) REFERENCES phrase_entry(id)
);
```

---

## 11. 示例转换

### 示例 A：be all eyes

原始：

```text
be all eyes
```

phrase_entry：

```text
source_pattern    = be all eyes
canonical_pattern = be all eyes
phrase_type       = IDIOM
```

pattern：

```text
0 LITERAL LEMMA      be
1 LITERAL NORMALIZED all
2 LITERAL NORMALIZED eyes
```

anchor：

```text
eyes
```

### 示例 B：as…as

原始：

```text
as…as
```

canonical：

```text
as <GAP> as
```

pattern：

```text
0 LITERAL NORMALIZED as
1 GAP                min=1 max=3
2 LITERAL NORMALIZED as
```

### 示例 C：add…to…

原始：

```text
add…to…
```

canonical：

```text
add <OBJECT> to <OBJECT>
```

pattern：

```text
0 LITERAL LEMMA      add
1 SLOT OBJECT         min=1 max=4
2 LITERAL NORMALIZED to
3 SLOT OBJECT         min=1 max=4
```

### 示例 D：remind sb. of sth.

原始：

```text
remind sb. of sth.
```

canonical：

```text
remind <PERSON> of <THING>
```

pattern：

```text
0 LITERAL LEMMA      remind
1 SLOT PERSON         min=1 max=4
2 LITERAL NORMALIZED of
3 SLOT THING          min=1 max=5
```

### 示例 E：prevent sb. from doing sth.

原始：

```text
prevent sb. from doing sth.
```

canonical：

```text
prevent <PERSON> from <GERUND> <THING>
```

pattern：

```text
0 LITERAL LEMMA      prevent
1 SLOT PERSON         min=1 max=4
2 LITERAL NORMALIZED from
3 SLOT GERUND         min=1 max=3
4 SLOT THING          min=0 max=5
```

---

## 12. Anchor 生成规则

构建阶段为每个短语选择一个或多个锚点。

优先级：

```text
低频固定内容词
> 固定名词/形容词
> 动词
> 高频功能词
```

避免优先选择：

```text
be
to
of
all
as
```

示例：

```text
be all eyes       → eyes
look forward to   → forward
remind sb. of sth. → remind
```

若短语只有高频固定词，可以保留多个 anchor。

---

## 13. token_count 范围计算

构建时保存：

```text
token_count_min
token_count_max
```

固定短语：

```text
be all eyes
min = 3
max = 3
```

模板：

```text
as <GAP 1..3> as
min = 3
max = 5
```

模板：

```text
remind <PERSON 1..4> of <THING 1..5>
min = 4
max = 11
```

用于运行时快速排除不可能匹配的候选。

---

## 14. 构建期验证

每个 entry 写库前必须验证：

- `source_pattern` 和 `canonical_pattern` 非空；
- 至少有一个 `LITERAL`；
- GAP/SLOT 不允许无界；
- `min_tokens >= 0`；
- `max_tokens >= min_tokens`；
- 至少存在一个可用 anchor；
- `pattern_position` 连续；
- `source_entry_id` 可追溯；
- `source_metadata_json` 可解析，且保留来源列表和 URL；
- 中文翻译关联成功或明确为空；
- 不生成伪 lemma。

无法编译的条目写入构建侧产物：

```text
build/build-errors.jsonl
```

构建失败时终止发布，不将 `build_error` 表写入正式 SQLite。

---

## 15. 不应在数据库构建阶段做的事情

禁止：

- 根据歌词数据改变短语模板；
- 根据当前用户歌曲频率删短语；
- 将普通相邻词自动加入 `phrase_entry`；
- 把所有单词逐词 lemma 后重新拼短语；
- 运行 NLP 模型猜测新的词典短语；
- 修改原始 JSONL。

---

## 16. 版本管理

`lyric-dictionary.sqlite` 必须有独立版本。

manifest 推荐：

```json
{
  "packageId": "2ndla-phrases-zh",
  "version": "1.0.0",
  "schemaVersion": 1,
  "source": "2ndLA",
  "language": "en",
  "translationLanguage": "zh-CN",
  "database": "phrases.db",
  "entryCount": 0
}
```

短语编译规则变化时：

- 若仅数据内容变化：增加 package version；
- 若数据库结构或 pattern 语义变化：增加 schemaVersion。

---

## 17. 最终规范

数据库构建层只负责：

```text
原始词典表达
→ 保留原文
→ 规范 canonical
→ 编译成 LITERAL / GAP / SLOT
→ 保存匹配类型
→ 保存长度约束
→ 生成锚点
→ 写入 SQLite
```

运行时不得依赖：

```text
…
sb.
sth.
one's
```

这些原始字符串做业务判断。

它们只能作为：

```text
来源数据
展示数据
重新编译依据
```

真正执行匹配的结构为：

```text
phrase_entry
+
phrase_pattern_token
+
phrase_anchor
```

---

## 18. ECDICT 词典字段命名与映射

本节用于约束与 2ndLA 短语数据并存的 ECDICT 单词词典表。发布数据库保持一个 `lyric-dictionary.sqlite`，但单词表和短语表的职责分开。

2ndLA 的 `phrase_entry` 保存短语模板和中文释义；ECDICT 保存单词级词典信息。两者可以在应用层关联，但不应因为共用 SQLite 而复用含义模糊的字段名。

### 18.1 推荐字段映射

| ECDICT 原始字段 | 推荐 SQLite 字段 | 说明 |
|---|---|---|
| `word` | `word` | 保持原名 |
| `phonetic` | `phonetic` | 保持原名 |
| `definition` | `definition_en` | 英文释义 |
| `translation` | `translation_zh` | 中文翻译 |
| `pos` | `pos_profile` | 词性及语料占比，例如 `n:46/v:54` |
| `collins` | `collins_star` | Collins 星级 |
| `oxford` | `oxford_core` | 是否属于 Oxford 核心词汇 |
| `tag` | `tags` | 学习标签，例如 `cet4`、`cet6`、`ielts` |
| `bnc` | `bnc_rank` | BNC 词频顺序 |
| `frq` | `coca_rank` | COCA 词频顺序 |
| `exchange` | `morphology` | 词形变化及 lemma 关系 |

其中以下改名用于避免误解：

```text
definition  → definition_en
translation → translation_zh
pos         → pos_profile
frq         → coca_rank
exchange    → morphology
```

`exchange` 不能只理解为复数或时态列表。它还可能保存 lemma，以及当前词与 lemma 的形态关系。因此第一版保留原始编码并存入 `morphology TEXT`，由应用层的 `MorphologyParser` 解析；暂不拆出独立的词形关系表。

### 18.2 推荐 ECDICT 单词表

```sql
CREATE TABLE word_entry (
    word            TEXT COLLATE NOCASE PRIMARY KEY,
    phonetic        TEXT,
    definition_en   TEXT,
    translation_zh  TEXT,
    pos_profile     TEXT,
    collins_star    INTEGER,
    oxford_core     INTEGER,
    tags            TEXT,
    bnc_rank        INTEGER,
    coca_rank       INTEGER,
    morphology      TEXT
) WITHOUT ROWID;
```

建议索引：

```sql
CREATE UNIQUE INDEX idx_word_word
ON word_entry(word COLLATE NOCASE);

CREATE INDEX idx_word_bnc
ON word_entry(bnc_rank)
WHERE bnc_rank IS NOT NULL;

CREATE INDEX idx_word_coca
ON word_entry(coca_rank)
WHERE coca_rank IS NOT NULL;
```

如果当前没有按 BNC 或 COCA 排序、筛选的功能，可以不创建后两个索引，但字段应保留。

### 18.3 大小写与规范化

词条表使用 `word` 直接作为主键并采用 `WITHOUT ROWID`：

```sql
word TEXT COLLATE NOCASE PRIMARY KEY
```

这样可以支持大小写无关查询，并避免整数 rowid 与 `UNIQUE(word)` 双重存储。不额外增加 `normalized_word`。只有当运行时需要频繁读取预计算规范词形，或数据不再统一大小写时，才增加独立字段。

### 18.4 与 2ndLA 短语表的边界

2ndLA 短语表继续使用：

```text
source_pattern
canonical_pattern
definition_en
definition_zh
```

其中 `definition_zh` 表示短语或句型的中文释义；ECDICT 的 `translation_zh` 表示单词词条的中文翻译。两者名称不同是有意区分，避免把单词翻译和短语释义混为一谈。短语运行时结构只来自 `phrase_pattern_token`，不再保存 `compiled_pattern`。

ECDICT 的推荐表与 2ndLA 的推荐表关系如下：

```text
word_entry             → 单词、词性、词频、词形关系
phrase_entry           → 短语模板、占位符、省略号结构
phrase_pattern_token   → 短语运行时匹配结构
phrase_anchor          → 短语检索锚点
```

ECDICT 原始定义可参考 [ECDICT README](https://github.com/skywind3000/ECDICT/blob/master/README.md)，原始 SQLite 实现可参考 [ECDICT stardict.py](https://github.com/skywind3000/ECDICT/blob/master/stardict.py)。

### 18.5 发布数据库收口规则

正式发布库只保留以下五个实体：

```text
word_entry
phrase_entry
phrase_pattern_token
phrase_anchor
dictionary_meta
```

`phrase_entry` 的最终运行时字段为：

```text
id
source_pattern
canonical_pattern
definition_en
definition_zh
usage_note_zh
phrase_type
source
source_entry_id
source_metadata_json
token_count_min
token_count_max
match_priority
```

其中：

- `compiled_pattern` 不进入发布库，`phrase_pattern_token` 是唯一的可执行匹配结构；
- `translation_status`、`confidence` 属于构建 QA 信息，移入构建报告；
- `is_active` 不进入版本化只读数据库，发布时只写入有效条目；
- `phrase_entry.license` 不重复保存，来源许可证写入 `dictionary_meta`；
- `source_forms_json`、`source_lists_json`、`source_urls_json` 合并为 `source_metadata_json`；
- `priority` 改名为 `match_priority`，明确它只表示匹配优先级。

`phrase_pattern_token` 必须增加以下唯一索引：

```sql
CREATE UNIQUE INDEX idx_phrase_pattern_position
ON phrase_pattern_token(phrase_id, pattern_position);
```

检索索引使用组合字段：

```sql
CREATE INDEX idx_phrase_token_match
ON phrase_pattern_token(match_type, match_value);

CREATE INDEX idx_phrase_anchor_lookup
ON phrase_anchor(anchor_type, anchor_value);
```

`phrase_anchor` 保留 `(phrase_id, anchor_position)` 作为主键，不限制一个短语只能有一个 anchor。这样可以支持未来为同一个模板保存多个候选锚点。

### 18.6 发布库与构建产物边界

发布库是干净的、只读的、可校验的运行时资源包。以下内容不写入正式 SQLite：

```text
build_error
translation_status
confidence
构建日志
```

构建失败记录放在独立目录：

```text
build/
├─ build-report.json
├─ build-errors.jsonl
└─ build-summary.json
```

构建成功后，数据库只包含可运行条目，不保留 `dictionary` 兼容视图。应用直接使用：

```text
word_entry
phrase_entry
```

### 18.7 `dictionary_meta` 最低元数据

`dictionary_meta` 继续使用 `key/value` 结构，至少记录：

```text
package.version
schema.version
build.time

ecdict.commit
ecdict.license
ecdict.entry_count

2ndla.commit
2ndla.license
2ndla.entry_count

pattern.compiler.version
lemma.rules.version
```

`pattern.compiler.version` 和 `lemma.rules.version` 用于确认词形处理、短语编译规则及数据库内容所对应的版本。

### 18.8 存储组织选择

`word_entry` 的 `WITHOUT ROWID` 方案已经通过同一批 ECDICT 数据完成 A/B 验证：

```text
普通 rowid 版：       336,109,568 bytes，单词精确查询中位数约 21.91 ms
WITHOUT ROWID 版：    241,405,952 bytes，单词精确查询中位数约 15.47 ms
```

因此正式发布库采用 `WITHOUT ROWID`。批量查询测试约为 4.04 ms 对 4.55 ms，差异较小；完整性检查均为 `ok`。构建脚本保留 `--word-without-rowid` 参数，以便重建和复核。
