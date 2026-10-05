#!/usr/bin/env python3
"""Тест порчи: ловит ли sverka.py ошибки в журнале.

Запуск:  python3 porcha.py CHAT JOURNAL LEGEND [OUT]
Пример:  python3 porcha.py chat.md journal.md answers/legend.json answers/porcha.md

Каждая порча — одна правка копии журнала (оригинал не трогается). «Покраснело» = в выводе
sverka.py появилась новая строка с ❌/⚠️ по сравнению с прогоном на неиспорченном журнале.
"""
import os, re, subprocess, sys, tempfile

MARK = "## История и ограничения"
HERE = os.path.dirname(os.path.abspath(__file__))

def run(chat, journal_text, legend):
    with tempfile.TemporaryDirectory() as d:
        j = os.path.join(d, "journal.md")
        open(j, "w", encoding="utf-8").write(journal_text)
        r = subprocess.run([sys.executable, os.path.join(HERE, "sverka.py"), chat, j, legend],
                           capture_output=True, text=True)
    if r.returncode not in (0, 1):
        return None, r.stderr.strip().splitlines()[-1] if r.stderr else "упал"
    return {l for l in r.stdout.splitlines() if "❌" in l or "⚠️" in l}, None

def row(text, rid):
    return next(l for l in text.splitlines() if re.match(rf"\|\s*{rid}\s*\|", l))

def cells_set(line, i, val):
    c = line.split("|"); c[i + 1] = f" {val} "; return "|".join(c)

def main():
    chat, jour, leg = sys.argv[1:4]
    out_p = sys.argv[4] if len(sys.argv) > 4 else None
    J = open(jour, encoding="utf-8").read()
    base, err = run(chat, J, leg)
    assert err is None, err

    def edit(rid, i, val):
        r = row(J, rid); return J.replace(r, cells_set(r, i, val))

    def edit_cell(rid, i, f):
        r = row(J, rid); c = r.split("|"); c[i + 1] = f(c[i + 1]); return J.replace(r, "|".join(c))

    cases = [
        ("Цитата: изменено одно слово (D2)", edit_cell("D2", 5, lambda s: s.replace("интеграции", "интеграцию", 1))),
        ("Цитата: пересказ вместо дословной (D3)", edit("D3", 5, "«Олег выделил на направление 900 тысяч на квартал»")),
        ("Время сдвинуто на минуту (D5)", edit("D5", 3, "07.09.2026 10:03")),
        ("Время — дата из текста решения, а не сообщения (D11)", edit("D11", 3, "15.11.2026 16:50")),
        ("Автор не тот (D3: Олег → Ира)", edit("D3", 2, "Ира")),
        ("Номер сообщения не тот (D8: [090] → [091])", edit("D8", 4, "[091]")),
        ("Удалена строка решения легенды (D6, неявное Р6)", J.replace(row(J, "D6") + "\n", "")),
        ("Задублирована строка (D2 ещё раз, тот же id)", J.replace(row(J, "D2"), row(J, "D2") + "\n" + row(J, "D2"))),
        ("Задублирована строка под новым id (D2 → D15)", J.replace(row(J, "D14"), row(J, "D14") + "\n" + cells_set(row(J, "D2"), 0, "D15"))),
        ("Статус: отменённое помечено действующим (D7)", edit("D7", 7, "действует")),
        ("Статус: действующее помечено отменённым (D8, без «чем отменено»)", edit("D8", 7, "отменено")),
        ("«Чем отменено» заполнено у действующего (D2)", edit("D2", 8, "[153], Ира — отменено")),
        ("Отмена: не тот автор (D7: Ира → Олег)", edit_cell("D7", 8, lambda s: s.replace("Ира", "Олег", 1))),
        ("Отмена: не то сообщение (D7: [153] → [152])", edit_cell("D7", 8, lambda s: s.replace("[153]", "[152]", 1))),
        ("Тип: неявное помечено явным (D6)", edit("D6", 6, "явное")),
        ("Ловушка в журнале: шутка про NFT [029]", J.replace(row(J, "D14"), row(J, "D14") + "\n| D15 | Уходим в NFT | Маша | 02.09.2026 15:20 | [029] | «всё, решено, уходим в NFT» | явное | действует | |")),
        ("Ловушка в журнале: курсы 1С от Кати [049]", J.replace(row(J, "D14"), row(J, "D14") + "\n| D15 | Курсы по 1С | Катя | 04.09.2026 12:00 | [049] | «я решила, берём курсы» | явное | действует | |")),
        ("Из 5.3 убран ребрендинг (Н2)", re.sub(r"\n1\. \*\*Ребрендинг.*?\n(?=\d\. )", "\n", J, flags=re.S)),
        ("Раздел 5.3 удалён целиком", re.sub(r"## 5\.3.*?(?=\n## )", "", J, flags=re.S)),
        ("Таблица пустая (все строки удалены)", "\n".join(l for l in J.splitlines() if not re.match(r"\|\s*D\d+", l))),
    ]

    L = ["# Тест порчи: ловит ли sverka.py ошибки журнала\n",
         f"Базовый прогон на неиспорченном журнале: {len(base)} строк с ❌/⚠️ (известные расхождения из sverka.md). "
         "«Покраснело» = появилась новая строка с ❌/⚠️.\n",
         "| # | Порча | Покраснело? | Что выдала сверка (новое) |", "|---|---|---|---|"]
    caught = 0; missed = []
    for i, (name, text) in enumerate(cases, 1):
        if text == J:
            L.append(f"| {i} | {name} | ⚠️ порча не применилась | — |"); missed.append(name); continue
        res, err = run(chat, text, leg)
        if err:
            L.append(f"| {i} | {name} | ✅ скрипт упал | {err[:90]} |"); caught += 1; continue
        new = sorted(res - base)
        ok = bool(new)
        caught += ok
        if not ok: missed.append(name)
        shown = "; ".join(re.sub(r"\s*\|\s*", " ", x).strip()[:110] for x in new[:2]) or "ничего"
        L.append(f"| {i} | {name} | {'✅ да' if ok else '❌ НЕТ'} | {shown.replace('|', '/')} |")
    L.append(f"\n**Поймано {caught} из {len(cases)}.**")
    if missed:
        L.append("\nНе поймано:\n" + "\n".join(f"- {m}" for m in missed))
    out = "\n".join(L) + "\n"
    if out_p:
        try:  # раздел «История и ограничения» пишет человек — сохранить при перезапуске
            prev = open(out_p, encoding="utf-8").read()
            if MARK in prev: out += "\n" + prev[prev.index(MARK):]
        except FileNotFoundError:
            pass
        open(out_p, "w", encoding="utf-8").write(out)
    print(out)

if __name__ == "__main__":
    main()
