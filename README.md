# Lyric Vocabulary Dictionary

独立维护 Lyric Vocabulary Builder 使用的单词与短语词典。本项目负责保存词典来源、清洗结果、翻译审核结果，并生成供应用读取的 SQLite 发布包。

## 目录

```text
sources/
  ecdict/       # ECDICT 原始压缩包、许可证和导入快照
  2ndla/        # 2ndLA 原始列表、许可证及初步整理数据
processing/
  scripts/      # 抓取、整理、校验脚本
  prompts/      # 翻译任务提示词
translations/
  2ndla/        # 机器翻译、复核和待处理结果
release/
  *.sqlite      # 发布给 LyricVocabularyBuilder 的 SQLite
  manifest.json # 版本、来源、schema 和校验信息
docs/
  source-comparison.md # 上游原始数据与本地整理差异
```

## 数据边界

- `sources/` 和 `translations/` 是维护材料，不由主应用直接读取。
- ECDICT 的单词数据只用于单词查询和 lemma 校验。
- 2ndLA 的短语必须以完整短语作为翻译单位，不能使用 ECDICT 单词释义拼接短语释义。
- 残缺、模板化、歧义或未审核条目应保留为待复核状态。

## SQLite 发布约定

发布 SQLite 至少应包含：

```text
dictionary_entry       # ECDICT 单词表，使用明确字段名
dictionary             # 兼容主项目旧字段名的只读视图
phrase_entry           # 短语主表
phrase_pattern_token   # 短语匹配 token
phrase_anchor          # 短语检索锚点
dictionary_meta        # 版本、来源、许可证和生成信息
```

SQLite 发布前应更新 `release/manifest.json`，记录 schema 版本、来源版本、条目数量、生成时间和 SHA-256。主项目通过 `APP_DICTIONARY_DB_URL` 指向该文件；词典项目不需要修改主项目代码即可发布数据更新。

构建发布库：

```text
python3 processing/scripts/build_sqlite.py \
  --ecdict-csv /path/to/extracted/stardict.csv
```

默认生成 `release/lyric-dictionary.sqlite` 和 `release/manifest.json`。构建脚本会在短语无法编译时生成 `release/build_error.jsonl` 并终止，不会静默丢弃条目。

`sources/ecdict/ecdict.sqlite` 作为本地源文件保留并被 Git 忽略；由于文件体积较大，正式共享应使用 Git LFS、Release 附件或对象存储，并在 manifest 中记录下载地址和校验值。

## 与主项目协作

主项目：`IyricVocabularyBuilder`

- 不保存原始 JSON、处理中间文件或翻译批次。
- 主项目开发环境默认读取本地 Git 忽略的 ECDICT SQLite 副本；无词库运行仍可使用 no-dictionary profile。
- 带词典运行时，将发布 SQLite 放在本地目录，并设置：

```text
APP_DICTIONARY_ENABLED=true
APP_DICTIONARY_DB_URL=jdbc:sqlite:/absolute/path/lyric-dictionary.sqlite
```

无词典运行：

```text
SPRING_PROFILES_ACTIVE=dev,no-dictionary
```

## 许可证与来源

各来源数据的许可证和署名要求以对应来源声明及 `release/manifest.json` 为准。ECDICT 来源为 [skywind3000/ECDICT](https://github.com/skywind3000/ECDICT)。
