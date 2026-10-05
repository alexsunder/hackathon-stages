#!/usr/bin/env python3
"""Сверка журнала решений с легендой (ключом ответов).

Запуск:  python3 sverka.py CHAT JOURNAL LEGEND [OUT]
Пример:  python3 sverka.py chat.md journal.md answers/legend.json answers/sverka.md

Журнал сопоставляется с легендой по номеру сообщения, на котором держится решение.
Проверяется: найдено / пропущено / лишнее, тип, статус, отмены (кто и каким сообщением),
нерешённые темы, ловушки, дословность цитат и совпадение времени/автора с чатом.
"""
import json, re, sys

MARK = "<!-- РУЧНОЙ РАЗБОР: всё ниже пишет человек, скрипт это сохраняет -->"

def load_chat(path):
    msgs = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\[(\d{3})\] (\d\d\.\d\d\.\d{4} \d\d:\d\d) · ([^:]+): (.*)$", line.rstrip("\n"))
        if m:
            msgs[int(m[1])] = {"time": m[2], "who": m[3], "text": m[4]}
    return msgs

def load_journal(path):
    text = open(path, encoding="utf-8").read()
    rows = []
    for line in text.splitlines():
        if not re.match(r"\|\s*D\d+\s*\|", line):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        nums = [int(n) for n in re.findall(r"\[(\d{3})\]", c[8])]
        rows.append({
            "id": c[0], "what": c[1], "who": c[2], "when": c[3],
            "msg": int(re.search(r"\d{3}", c[4])[0]),
            "quote": c[5].strip("«»\" "), "type": c[6],
            "status": "отменено" if c[7].startswith("отмен") else "действует",
            "cancel_raw": c[8],
            "cancel_msg": nums[0] if nums else None,
            "cancel_who": (re.search(r"\]\s*,\s*([А-ЯЁA-Z][а-яёa-z]+)", c[8]) or [None, None])[1],
        })
    m = re.search(r"## 5\.3.*?(?=\n## )", text, re.S)
    undecided_text = m[0] if m else ""
    return rows, undecided_text

def nums_in(text):
    out = set()
    for a, b in re.findall(r"\[(\d{3})\](?:\s*[–-]\s*\[(\d{3})\])?", text):
        a = int(a); b = int(b) if b else a
        out.update(range(a, b + 1))
    return out

def main():
    chat_p, jour_p, leg_p = sys.argv[1:4]
    out_p = sys.argv[4] if len(sys.argv) > 4 else None
    chat = load_chat(chat_p)
    rows, und_text = load_journal(jour_p)
    leg = json.load(open(leg_p, encoding="utf-8"))
    by_msg = {r["msg"]: r for r in rows}
    L = []; p = L.append
    score = {}

    p("# Сверка журнала с легендой\n")
    p(f"Журнал: {len(rows)} строк. Легенда: {len(leg['decisions'])} решений, "
      f"{len(leg['undecided'])} нерешённых темы, {len(leg['decoys'])} ловушки.\n")

    # 1. Решения
    p("## 1. Решения легенды → журнал\n")
    p("| Легенда | Сообщение | Журнал | Тип | Статус | Отмена (кто, сообщение) |")
    p("|---|---|---|---|---|---|")
    found = miss = type_ok = st_ok = canc_ok = canc_total = 0
    matched = set()
    for d in leg["decisions"]:
        r = by_msg.get(d["msg"])
        if not r:
            miss += 1
            p(f"| {d['id']} {d['what']} | [{d['msg']:03d}] | ❌ не найдено | | | |")
            continue
        found += 1; matched.add(r["id"])
        t = r["type"] == d["type"]; s = r["status"] == d["status"]
        type_ok += t; st_ok += s
        cell = "—"
        if d["cancelled_by"]:
            canc_total += 1
            cb = d["cancelled_by"]
            ok = r["cancel_msg"] == cb["msg"] and r["cancel_who"] == cb["who"]
            canc_ok += ok
            cell = (f"{'✅' if ok else '❌'} журнал: {r['cancel_who']}, [{r['cancel_msg'] or 0:03d}]"
                    f" · ключ: {cb['who']}, [{cb['msg']:03d}]")
        p(f"| {d['id']} {d['what']} | [{d['msg']:03d}] | {r['id']} | "
          f"{'✅' if t else '❌'} {r['type']} | {'✅' if s else '❌'} {r['status']} | {cell} |")
    extra = [r for r in rows if r["id"] not in matched]
    p(f"\nНайдено {found} из {len(leg['decisions'])}, пропущено {miss}, лишних строк {len(extra)}. "
      f"Тип верен {type_ok}/{found}, статус верен {st_ok}/{found}, отмены верны {canc_ok}/{canc_total}.\n")
    if extra:
        p("Лишние строки (в легенде таких решений нет):\n")
        for r in extra:
            p(f"- {r['id']} [{r['msg']:03d}] {r['who']}: {r['what']} — {r['type']}, {r['status']}")
        p("")

    # 2. Нерешённые
    p("## 2. «Обсуждали, но не решили»\n")
    und_nums = nums_in(und_text)
    und_ok = 0
    for u in leg["undecided"]:
        hit = sorted(set(u["msgs"]) & und_nums)
        ok = len(hit) >= 2
        und_ok += ok
        p(f"- {'✅' if ok else '❌'} {u['id']} {u['what']} ({u['how']}) — в разделе 5.3 журнала "
          f"упомянуты сообщения легенды: {', '.join(f'[{n:03d}]' for n in hit) or 'нет'}")
    # решения журнала, которые в ключе — нерешённые темы
    for r in rows:
        for u in leg["undecided"]:
            if r["msg"] in u["msgs"]:
                p(f"- ⚠️ строка {r['id']} [{r['msg']:03d}] опирается на сообщение нерешённой темы {u['id']}")
    p("")

    # 3. Ловушки
    p("## 3. Ловушки\n")
    dec_ok = 0
    for x in leg["decoys"]:
        bad = [r["id"] for r in rows if r["msg"] in x["msgs"]]
        dec_ok += not bad
        p(f"- {'✅ не попала' if not bad else '❌ попала: ' + ', '.join(bad)} — {x['id']} {x['what']}")
    p("")

    # 4. Опора строк
    p("## 4. Опора каждой строки журнала (цитата, время, автор — по chat.md)\n")
    p("| id | Сообщение | Цитата дословно | Время | Автор | Слов в цитате |")
    p("|---|---|---|---|---|---|")
    sup_ok = 0
    for r in rows:
        m = chat.get(r["msg"])
        q = bool(m) and r["quote"] in m["text"]
        t = bool(m) and r["when"] == m["time"]
        a = bool(m) and m["who"] in r["who"]
        w = len(r["quote"].split())
        sup_ok += q and t and a
        p(f"| {r['id']} | [{r['msg']:03d}] | {'✅' if q else '❌'} | {'✅' if t else '❌'} | "
          f"{'✅' if a else '❌'} | {w}{'' if 5 <= w <= 25 else ' ⚠️'} |")
    p(f"\nОпора подтверждена у {sup_ok} из {len(rows)} строк.\n")

    # 4а. Форма журнала (не из критерия, но без неё сверка слепа к дублям и противоречиям)
    p("## 4а. Форма журнала\n")
    form = []
    from collections import Counter
    for kind, key in (("id", "id"), ("сообщение", "msg")):
        for v, n in Counter(r[key] for r in rows).items():
            if n > 1:
                form.append(f"повтор {kind} {v if kind == 'id' else f'[{v:03d}]'} — {n} строк")
    for r in rows:
        if r["status"] == "действует" and r["cancel_raw"]:
            form.append(f"{r['id']}: статус «действует», но «чем отменено» заполнено")
        if r["status"] == "отменено" and not r["cancel_msg"]:
            form.append(f"{r['id']}: статус «отменено», но нет номера отменяющего сообщения")
    for f in form:
        p(f"- ❌ {f}")
    if not form:
        p("- ✅ id и номера сообщений не повторяются; «чем отменено» заполнено ровно у отменённых")
    p("")

    # 5. Итог по порогу успеха
    p("## 5. Порог успеха (из критерия)\n")
    checks = [
        ("Найдены все решения легенды", miss == 0, f"{found}/{len(leg['decisions'])}"),
        ("Ни одной лишней строки", not extra, f"лишних {len(extra)}"),
        ("Статусы верны", st_ok == found, f"{st_ok}/{found}"),
        ("Отмены верны (кто и каким сообщением)", canc_ok == canc_total, f"{canc_ok}/{canc_total}"),
        ("Неявное решение распознано", all(by_msg.get(d['msg'], {}).get('type') == 'неявное'
             for d in leg['decisions'] if d['type'] == 'неявное'), ""),
        ("Нерешённые темы в списке", und_ok == len(leg["undecided"]), f"{und_ok}/{len(leg['undecided'])}"),
        ("Ловушки не попали", dec_ok == len(leg["decoys"]), f"{dec_ok}/{len(leg['decoys'])}"),
        ("У каждой строки цитата и время", sup_ok == len(rows), f"{sup_ok}/{len(rows)}"),
    ]
    for name, ok, note in checks:
        p(f"- {'✅' if ok else '❌'} {name}{' — ' + note if note else ''}")
    passed = sum(ok for _, ok, _ in checks)
    p(f"\n**Итого: {passed} из {len(checks)} проверок пройдено.**")

    out = "\n".join(L) + "\n"
    if out_p:
        # ручной разбор (после маркера) сохраняется при повторном запуске
        try:
            prev = open(out_p, encoding="utf-8").read()
            if MARK in prev:
                out += "\n" + prev[prev.index(MARK):]
        except FileNotFoundError:
            pass
        open(out_p, "w", encoding="utf-8").write(out)
    print(out)
    return 0 if passed == len(checks) and not form else 1

if __name__ == "__main__":
    sys.exit(main())
