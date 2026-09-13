#!/usr/bin/env python3
"""Translate source candidates not yet present in the full translation output.

This creates a machine-translation draft for the newly admitted candidates.
Existing translation rows, including REVIEW_REQUIRED rows, are copied without
any changes. The source phrase is translated as a complete phrase; common
source placeholders are expanded only in the request sent to the translator.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


API_URL = "https://api.mymemory.translated.net/get"
MANUAL_TRANSLATIONS = {
    "do sb. credit": "使某人增光；对某人有利",
    "for sth.'s sake": "看在某事的份上；为了某事",
    "die for": "为……而死；非常渴望……",
    "distinguish between...and...": "区分……和……",
    "fall on": "落在……上；袭击；由……承担；适逢（日期）",
    "fall to": "开始做……；落到……手中；轮到……",
    "fall upon": "落在……上；袭击；突然开始做……",
    "for all": "尽管；对于所有……",
    "follow out": "贯彻执行；把……进行到底",
    "for sb.'s sake": "看在某人的份上；为了某人",
    "get in sb.'s hair": "惹某人烦；打扰某人",
    "get on sb.'s nerves": "使某人烦恼；惹某人心烦",
    "out of sb.'s reach": "超出某人的能力或触及范围",
    "over sb.'s head": "超出某人的理解能力；在某人头顶上",
    "pick sb.'s brains": "向某人请教；借用某人的知识",
    "prove sb.'s guilt": "证明某人有罪",
    "pull sb.'s leg": "开某人的玩笑；愚弄某人",
    "sing sb.'s praises": "大肆赞扬某人",
    "sing sth.'s praises": "大肆赞扬某事物",
    "take sb.'s advice": "听取某人的建议",
    "take sb.'s place": "代替某人；取代某人的位置",
    "take sb.'s side": "站在某人一边",
    "to sb.'s amazement": "令某人惊讶的是",
    "to sb.'s delight": "令某人高兴的是",
    "to sb.'s disappointment": "令某人失望的是",
    "to sb.'s sorrow": "令某人悲伤的是",
    "to sb.'s surprise": "令某人惊讶的是",
    "turn sb.'s blood cold": "使某人毛骨悚然；使某人不寒而栗",
    "under sb.'s charge": "由某人负责；在某人的照管下",
    "under sb.'s direction": "在某人的指导下",
    "undermine sb.'s reputation": "损害某人的声誉",
    "as much...as": "和……一样多；尽可能多",
    "an insuperable difficulty": "无法克服的困难",
    "as...as...": "和……一样……",
    "assume sth. to be true": "假定某事是真的",
    "assure sb. of sth.": "向某人保证某事",
    "be confined to sp.": "被限制在某地",
    "be not much of a...": "算不上什么……；不太像一个……",
    "behind sb.'s back": "背着某人；在某人背后",
    "break sb.'s heart": "使某人心碎；使某人极度伤心",
    "cannot be too...": "再……也不为过；不能太……",
    "catch sb.'s eye": "引起某人的注意",
    "cause sb. to experience": "使某人经历……",
    "date back to": "追溯到……；始于……",
    "determination to do sth.": "做某事的决心",
    "expect sth. of sb.": "期望某人做某事；对某人有……期望",
    "in favor of": "支持……；赞成……；对……有利",
    "in favour of": "支持……；赞成……；对……有利",
    "feed sb. up": "把某人喂饱；给某人补充营养",
    "from...to...": "从……到……",
    "hardly...when...": "刚……就……",
    "in sb.'s debt": "欠某人的债；欠某人的人情",
    "in sb.'s hands": "掌握在某人手中",
    "in sb.'s presence": "在某人面前；有某人在场",
    "in sb.'s shoes": "处于某人的处境；设身处地",
    "in token of sth.": "作为……的象征",
    "inform sb. of sth.": "告知某人某事",
    "introduce sb. to sth.": "向某人介绍某事或某人",
    "jog sb.'s memory": "唤起某人的记忆",
    "know sth. from sth.": "辨别某事物与另一事物",
    "be made up of": "由……组成",
    "of no avail": "不起作用；徒劳无益",
    "not much of a...": "算不上什么……；不太像一个……",
    "not so...as...": "不像……那么……；与其说……不如说……",
    "one...the other...": "一个……另一个……",
    "to one's delight": "令某人高兴的是",
    "out of accord with": "与……不一致；与……不相符",
    "out of the question": "不可能；完全不考虑",
    "take sth. for granted": "认为……理所当然",
    "get rid of": "摆脱；去除；处理掉",
    "scarcely...when...": "刚……就……",
    "speak volumes for": "充分说明；有力证明",
    "for the sake of": "为了……；为了……的利益；看在……的份上",
    "too...to...": "太……而不能……",
    "whether...or...": "无论是……还是……",
    "between...and...": "在……和……之间",
    "blame sb. for": "因……责备某人；把……归咎于某人",
    "both...and...": "既……又……；两者都……",
    "be under the delusion that...": "误以为……；陷入……的错觉",
    "be under the illusion that...": "误以为……；抱有……的错觉",
    "bear...in mind": "牢记……；记住……",
    "beat...to the punch": "抢在……之前；先发制人",
    "bridge the gap between...and...": "弥合……与……之间的差距",
    "bring...into effect": "使……生效；实施……",
    "bring...into operation": "使……开始运行",
    "bring...into practice": "将……付诸实践",
    "bring...to a conclusion": "使……结束；使……得出结论",
    "call...in question": "对……提出质疑",
    "carry...into effect": "实施……；执行……",
    "carry...into practice": "将……付诸实践",
    "carve...out of": "从……中雕刻出或开辟出……",
    "cast...into prison": "把……投入监狱",
    "cause...to experience": "使……经历……",
    "go on doing...": "继续做……",
    "had rather...": "宁愿……",
    "had rather...than...": "宁愿……而不愿……",
    "had sooner...": "宁愿……",
    "had sooner...than...": "宁愿……而不愿……",
    "have...in common": "与……有共同点",
    "have...in common with": "与……有共同之处",
    "have...in common with...": "……与……有共同点",
    "have...to do with": "与……有关",
    "keep a balance between...and...": "在……与……之间保持平衡",
    "keep...in mind": "记住……；把……牢记在心",
    "keep...under close observation": "密切观察……；严密监视……",
    "keep...under observation": "观察……；监视……",
    "know...by heart": "熟记……；背熟……",
    "lay...to heart": "把……铭记于心；认真听取……",
    "lead a...life": "过着……的生活",
    "learn...by heart": "熟记……；背熟……",
    "learn...by oneself": "独自学习……；自学……",
    "let...out of": "把……从……放出",
    "live a...life": "过着……的生活",
    "look on...as...": "把……看作……",
    "look upon...as...": "把……看作……",
    "make...a top priority": "把……列为最优先事项",
    "narrow the gap between...and...": "缩小……与……之间的差距",
    "no less...than...": "不比……少；和……一样……",
    "no matter whether...or...": "不论是……还是……",
    "no more...than...": "不比……更多；和……一样不……",
    "no sooner...than": "一……就……",
    "not as...as": "不如……；不像……那么……",
    "not as...as...": "不如……；不像……那么……",
    "not only...but...": "不仅……而且……",
    "not only...but also...": "不仅……而且……",
    "not so much...as...": "与其说……不如说……",
    "not...any more": "不再……",
    "not...any more than": "不比……更……",
    "not...at all": "一点也不……",
    "not...in the slightest": "一点也不……；丝毫不……",
    "now that...": "既然……",
    "on a scale of...to...": "从……到……的比例或范围",
    "on a...scale": "按……的规模或程度",
    "one...the other...": "一个……另一个……",
    "pass on...to...": "把……传递给……",
    "persuade sb. to do": "说服某人做……",
    "prevent...from doing": "阻止……做……",
    "put...down to": "把……归因于……",
    "put...in action": "使……开始实施；启动……",
    "put...in force": "使……生效；实施……",
    "put...in motion": "启动……；使……运转",
    "put...in order": "整理……；使……井然有序",
    "put...in prison": "把……投入监狱",
    "put...into circulation": "使……流通",
    "put...into effect": "实施……；使……生效",
    "put...into operation": "使……投入运行",
    "put...into practice": "将……付诸实践",
    "put...on the stage": "把……搬上舞台",
    "put...to death": "处死……",
    "put...to use": "使用……；利用……",
    "practice doing": "练习做……",
    "range from...to...": "范围从……到……",
    "reckon...to be": "认为……是……",
    "refer to...as": "把……称为……",
    "refer to...as...": "把……称为……",
    "set...in motion": "启动……；使……运转",
    "set...on fire": "点燃……；使……着火",
    "so far as...is concerned": "就……而言",
    "so...as to": "如此……以至于……；以便……",
    "take...by surprise": "使……猝不及防；突袭……",
    "take...for a walk": "带……散步",
    "take...for example": "以……为例",
    "take...for granted": "想当然地认为……；把……视为理所当然",
    "take...into account": "考虑……；把……计入",
    "take...into consideration": "考虑……",
    "take...on oneself": "承担……；把……担在自己身上",
    "take...to heart": "把……放在心上",
    "take...upon oneself": "承担……；主动负责……",
    "the former...the latter...": "前者……后者……",
    "the more...the more": "越……越……",
    "the more...the more...": "越……越……",
    "the ratio of...to...": "……与……的比例",
    "the same...as": "与……相同；和……一样",
    "think of...as": "把……看作……",
    "think of...as...": "把……看作……",
    "transition from...to": "从……过渡到……",
    "vary from...to...": "从……到……不等；因……而异",
    "whether...or not": "是否……",
    "would rather...": "宁愿……",
    "would rather...than...": "宁愿……而不愿……",
    "would sooner...": "宁愿……",
    "would sooner...than...": "宁愿……而不愿……",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_review_decisions(path: Path | None) -> dict:
    if path is None:
        return {"corrections": {}, "approvals": [], "exclusions": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def translation_query(phrase: str) -> str:
    query = phrase
    query = query.replace("sb.'s", "someone's").replace("sb.s", "someone's")
    query = query.replace("sth.'s", "something's").replace("sth.s", "something's")
    query = query.replace("sb.", "someone").replace("sth.", "something").replace("sp.", "somewhere")
    return query


def translate(phrase: str, email: str | None = None) -> str:
    query = translation_query(phrase)
    params = urllib.parse.urlencode(
        {"q": query, "langpair": "en|zh-CN", **({"de": email} if email else {})},
        quote_via=urllib.parse.quote,
    )
    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"User-Agent": "IyricVocabularyBuilder-Dictionary/2ndla-translation"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("responseData", {}).get("translatedText", "").strip()
    if not result or result.casefold() == query.casefold():
        raise ValueError("translator returned no translated text")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("sources/2ndla/entries.jsonl"))
    parser.add_argument("--existing", type=Path, default=Path("translations/2ndla/translation-full-output.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("translations/2ndla/translation-full-output.jsonl"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--email", help="Optional contact email used by MyMemory for quota attribution.")
    parser.add_argument("--review-file", type=Path, help="Re-translate approved rows from a review decision file.")
    args = parser.parse_args()

    source_rows = load_jsonl(args.source)
    existing_rows = load_jsonl(args.existing)
    review_decisions = load_review_decisions(args.review_file)
    existing_by_id = {row["id"]: row for row in existing_rows}
    resolved_phrases = set(review_decisions.get("approvals", [])) | set(review_decisions.get("corrections", {}).values())
    retranslate_ids = {
        row["id"]
        for row in source_rows
        if row["canonicalPhrase"] in resolved_phrases
        and existing_by_id.get(row["id"], {}).get("translationStatus") == "REVIEW_REQUIRED"
    }
    new_rows = [row for row in source_rows if row["id"] not in existing_by_id or row["id"] in retranslate_ids]
    translated: dict[str, str] = {}
    failures: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(translate, row["canonicalPhrase"], args.email): row for row in new_rows}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                translated[row["id"]] = future.result()
            except Exception as error:  # Keep one failed request from losing the batch.
                failures[row["id"]] = str(error)
            if index % 50 == 0 or index == len(new_rows):
                print(f"processed={index}/{len(new_rows)} translated={len(translated)} failed={len(failures)}", flush=True)

    output_rows = []
    for row in source_rows:
        if row["id"] in existing_by_id and row["id"] not in retranslate_ids:
            output_rows.append(existing_by_id[row["id"]])
            continue
        meaning = translated.get(row["id"], "")
        output_rows.append(
            {
                "id": row["id"],
                "canonicalPhrase": row["canonicalPhrase"],
                "meaningZh": meaning,
                "usageNoteZh": "",
                "translationStatus": "GENERATED" if meaning else "REVIEW_REQUIRED",
                "confidence": "MEDIUM" if meaning else "LOW",
            }
        )
    for row in output_rows:
        manual_meaning = MANUAL_TRANSLATIONS.get(row["canonicalPhrase"])
        if manual_meaning:
            row["meaningZh"] = manual_meaning
            row["translationStatus"] = "GENERATED"
            row["confidence"] = "MEDIUM"
    args.output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in output_rows) + "\n",
        encoding="utf-8",
    )
    print(f"existing={len(existing_rows)} new={len(new_rows)} translated={len(translated)} failed={len(failures)} output={len(output_rows)}")
    if failures:
        for row in new_rows:
            if row["id"] in failures:
                print(f"failed {row['canonicalPhrase']!r}: {failures[row['id']]}")


if __name__ == "__main__":
    main()
