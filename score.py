"""Audit saved inference and score the client-facing sentences without a judge model."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from reference import day_name, load_cases, month_name, template

ROOT = Path(__file__).resolve().parent
ARMS = {"direct": "Прямой запрос", "decomposition": "С разложением", "template": "Программный шаблон"}
QUESTIONS = {"monthly": "За месяц", "since": "С предыдущего выпуска"}
DIRECTIONS = {"up": "выше", "down": "ниже", "flat": "без изменения", "unanswered": "нет ответа"}
UNITS = {"index points": "п. индекса", "thousand jobs": "тыс. мест"}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def indexed(records, label):
    index = {r["id"]: r for r in records}
    require(len(index) == len(records), f"Duplicate IDs in {label}")
    return index


def sign(delta):
    return "up" if delta > 0 else "down" if delta < 0 else "flat"


def gold(case, question):
    # Compute from the source cells independently of reference.template().
    now = Decimal(case["current_level"])
    a, b = Decimal(case["previous_level"]), Decimal(case["revised_level"])
    delta = now - (b if question == "monthly" else a)
    return {"direction": sign(delta), "amount": abs(delta), "unit": case["unit"],
            "pair": "C-B" if question == "monthly" else "C-A",
            "discordant": sign(now - a) != sign(now - b)}


def parse_template(case, sentence):
    base = re.search(r"(в том же выпуске|в выпуске от [^.]+ г)(?:\.| с точностью публикации\.)$", sentence)
    if not base:
        raise ValueError(f"Cannot identify the template's baseline: {sentence}")
    label = base.group(1)
    if label != "в том же выпуске":
        require(label == "в выпуске от " + day_name(case["previous_date"]).rstrip("."),
                "Template cites a different prior release date")
    require(month_name(case["prior_month"]) + " " + label in sentence, "Prior reference month mismatch")
    pair = "C-B" if label == "в том же выпуске" else "C-A"
    if " совпала с оценкой за " in sentence:
        unit = "index points" if "индекса промышленного производства" in sentence else "thousand jobs"
        return {"direction": "flat", "amount": Decimal(0), "unit": unit, "pair": pair}
    m = re.search(r"оказалась на (\d+(?:,\d+)?) (тыс\. рабочих мест|пункт(?:а|ов)? индекса) (выше|ниже) оценки за ", sentence)
    require(m is not None, f"Cannot parse template direction or amount: {sentence}")
    return {"direction": "up" if m[3] == "выше" else "down",
            "amount": Decimal(m[1].replace(",", ".")),
            "unit": "thousand jobs" if m[2].startswith("тыс.") else "index points", "pair": pair}



def audit_direction(text, rating, trial):
    """Check unambiguous opening words; keep model text and adjudication observable."""
    lead = re.split(r"(?i)\bячейки\s*[:：]", text, maxsplit=1)[0]
    lead = re.sub(r'[*_~`«»„“”"]', "", lead).strip()
    lead = re.sub(r"^[\s'›>•─—–-]+", "", lead)
    tokens = {"выше": "up", "ниже": "down", "без изменения": "flat", "недостаточно данных": "unanswered"}
    opening = re.match(r"(?i)^(выше|ниже|без изменения|недостаточно данных)\b", lead)
    if opening is None:
        return "reviewed"
    initial = tokens[opening[1].lower()]
    # If a second direction occurs, the words may refer to a different month
    # or the reported revision. Even those legitimate contrasts go to review.
    tail = lead[opening.end():]
    meanings = {
        "up": r"выше|рост(?:а|ом)?|вырос\w*|увеличил\w*|повысил\w*",
        "down": r"ниже|снижени\w*|падени\w*|упал\w*|снизил\w*|уменьшил\w*",
        "flat": r"без изменени\w*|не изменил\w*|не поменял\w*|совпал\w*",
        "unanswered": r"недостаточно данных|данных недостаточно|невозможно определить",
    }
    negated_opening = re.match(r"^[,:;\s]+не\b", tail, re.I)
    conflict = bool(negated_opening) or any(
        meaning != initial and re.search(r"\b(?:" + pattern + r")\b", tail, re.I)
        for meaning, pattern in meanings.items()
    )
    # A signed numerical claim opposing the lead word also deserves review.
    polarity = r"[−–-]" if initial == "up" else r"\+" if initial == "down" else None
    zero_change = re.search(r"\bна\s+[+−-]?0+(?:[.,]0+)?(?![\d.,])", tail, re.I)
    if initial in {"up", "down"} and zero_change:
        conflict = True
    if polarity and re.search(r"(?<![\w.])" + polarity + r"\s*\d", tail):
        conflict = True
    if conflict:
        note = rating.get("note")
        require(isinstance(note, str) and len(note.strip()) >= 12,
                f"Explain the possibly conflicting client directions in the note for {trial}")
        return "reviewed"
    require(rating["direction"] == initial, f"Transcription differs from the canonical opening for {trial}")
    return "automatic"


def validated_ratings(cases):
    for line in (ROOT / "model/design.sha256").read_text().splitlines():
        expected, path = line.split(maxsplit=1)
        require(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, f"Design hash mismatch: {path}")
    requests = indexed(read("model/requests.json"), "requests")
    blind = indexed(read("model/blind.json"), "blind")
    ratings = indexed(read("model/ratings.json"), "ratings")
    packets = read("model/packets.json")
    raw_dir = ROOT / "model/responses"
    require(set(p.stem for p in raw_dir.glob("*.json")) == requests.keys() == blind.keys() == ratings.keys(),
            "IDs differ between requests, responses, blind export and ratings")
    design = {(c["id"], q, a) for c in cases for q in QUESTIONS for a in ("direct", "decomposition")}
    require(len(design) == len(requests) and {(t["case"], t["question"], t["arm"]) for t in requests.values()} == design,
            "Missing or duplicated case × question × arm")
    output = {}
    for trial, t in requests.items():
        payload = t["request"]
        packet = packets[t["case"]]
        require(t["packet_sha256"] == hashlib.sha256(packet.encode()).hexdigest() and
                payload["messages"][1]["content"].startswith(packet + "\n\n"), f"Packet differs in {trial}")
        raw = read(f"model/responses/{trial}.json")
        encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
        require(raw["statgazer_request_sha256"] == hashlib.sha256(encoded).hexdigest(), f"Request differs: {trial}")
        text = raw["choices"][0]["message"].get("content", "")
        require(text == blind[trial]["text"], f"Blind text differs from raw response: {trial}")
        r = dict(ratings[trial])
        require(r["direction"] in DIRECTIONS and r["unit"] in [None, *UNITS], f"Invalid direction or unit: {trial}")
        require(r["pair"] is None or isinstance(r["pair"], str) and r["pair"].strip(), f"Invalid pair: {trial}")
        if r["amount"] is not None:
            require(isinstance(r["amount"], str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", r["amount"]),
                    f"Expected an unsigned decimal string as amount: {trial}")
            r["amount"] = Decimal(r["amount"])
        trace = re.split(r"(?i)\bячейки\s*[:：]", text, maxsplit=1)[-1]
        expression = r"([ABC])\s*[-−–]\s*([ABC])\s*=\s*([+−-]?\d+(?:[.,]\d+)?)"
        candidates = re.findall(expression, trace)
        r["multiple_pairs"] = len(candidates) > 1
        if r["multiple_pairs"]:
            require(r["amount"] is not None and r.get("note"), f"Explain pair choice: {trial}")
            signed = -r["amount"] if r["direction"] == "down" else r["amount"]
            matches = [f"{left}-{right}" for left, right, value in candidates
                       if Decimal(value.replace("−","-").replace(",",".")) == signed]
            require(matches == [r["pair"]], f"Ambiguous reconstruction of the pair: {trial}")
        r["direction_check"] = audit_direction(text, r, trial)
        output[t["case"], t["question"], t["arm"]] = r
    return output


def ratio(n, d):
    if not d:
        return f"{n}/{d} (н/о)"
    pct = f"{100*n/d:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{n}/{d} ({pct}%)"


def summarize(rows):
    n = len(rows)
    a = sum(r["direction"] != "unanswered" for r in rows)
    e = sum(r["error"] for r in rows)
    return [ratio(e, a), ratio(a, n), ratio(e, n)]


def full_report():
    cases = load_cases()
    ratings = validated_ratings(cases)
    rows = []
    for c in cases:
        for q in QUESTIONS:
            g = gold(c, q)
            for arm in ARMS:
                if arm == "template":
                    r = parse_template(c, template(c, q))
                    require(all(r[k] == g[k] for k in r), f"Template phrase disagrees with cells in {c['id']}/{q}")
                else:
                    r = ratings[c["id"], q, arm]
                rows.append({**r, "case": c["id"], "q": q, "arm": arm, "gold": g,
                             "source": "BLS" if c["unit"] == "thousand jobs" else "G.17",
                             "error": r["direction"] not in {"unanswered",g["direction"]}})
    lines = ["# Направление клиентского ответа", "",
             "N — все задания, A — ответы с однозначным направлением, E — неверные направления среди них. "
             "Доля E/A рассчитана среди выданных ответов, охват A/N и риск сообщить неверное направление E/N — по всем заданиям. "
             "Величина и единицы засчитаны при точном совпадении модуля и единиц с печатными уровнями. "
             "Заявленная пара проверена в порядке вычитания. Обе дополнительные проверки имеют знаменатель N.", "",
             "| Способ | Неверное направление E/A | Охват A/N | Неверно на задание E/N | Величина и единицы | Указанная или восстановленная пара |",
             "|---|---:|---:|---:|---:|---:|"]
    for arm, label in ARMS.items():
        group = [r for r in rows if r["arm"] == arm]
        right_amount = sum(r["amount"] == r["gold"]["amount"] and r["unit"] == r["gold"]["unit"] for r in group)
        right_pair = sum(r["pair"] == r["gold"]["pair"] for r in group)
        lines.append("| " + " | ".join([label, *summarize(group), ratio(right_amount,len(group)), ratio(right_pair,len(group))]) + " |")
    multi = [r for r in rows if r.get("multiple_pairs")]
    counted = sum(r["pair"] == r["gold"]["pair"] for r in multi)
    sensitivity = (f"При строгом учёте только явно выбранных пар пришлось бы вычесть {counted} верных сопоставлений. "
                   if counted else "Все восстановленные пары оказались ошибочными. Если считать их неуказанными, итоговые числа верных пар те же. ")
    lines.extend(["", f"В {len(multi)} ответах модель перечислила несколько вычитаний. Пара восстановлена по единственному "
                  "совпадению числовой разницы, включая знак, с величиной в клиентской фразе. "
                  + sensitivity + "Альтернативы сохранены в [примечаниях к разметке](model/ratings.json).", "",
                  "## Подгруппы выбранных выпусков", "",
                  "В каждой ячейке приведены E/A и A/N. Разбивка по знакам относится к двум правильным ответам одной пары выпусков. "
                  "Разбиения пересекаются, наблюдения внутри пары связаны.", "",
                  "| Подгруппа | Прямой запрос | С разложением | Шаблон |", "|---|---:|---:|---:|"])
    groupings = [("q", key, value) for key,value in QUESTIONS.items()] + [("source", v, v) for v in ["BLS", "G.17"]]
    groupings.extend([("discordant", True, "Знаки различаются"), ("discordant", False, "Знаки совпадают")])
    for field, value, label in groupings:
        subset = [r for r in rows if (r["gold"]["discordant"] if field == "discordant" else r[field]) == value]
        cells = [" · ".join(summarize([r for r in subset if r["arm"] == a])[:2]) for a in ARMS]
        lines.append("| " + " | ".join([label, *cells]) + " |")
    paired = {}
    for r in rows:
        paired.setdefault((r["case"],r["q"]), {})[r["arm"]] = r
    transitions = Counter()
    for trials in paired.values():
        direct, decomposed = trials["direct"], trials["decomposition"]
        if "unanswered" in (direct["direction"],decomposed["direction"]):
            transitions["unpaired"] += 1
        else:
            transitions[direct["error"],decomposed["error"]] += 1
    both = len(paired) - transitions["unpaired"]
    checks = Counter(r["direction_check"] for r in rows if r["arm"] != "template")
    lines.extend(["", "## Парное сравнение запросов", "",
        f"Оба условия дали направление в {both} из {len(paired)} заданий. При добавлении разложения исправлено "
        f"ошибок — {transitions[True, False]}, появилось новых — {transitions[False, True]}. "
        f"Пар с двумя верными ответами — {transitions[False, False]}, с двумя неверными — {transitions[True, True]}. "
        f"Заданий без ответа хотя бы в одном условии — {transitions['unpaired']}.", "",
        "## Проверка каждой фразы", "",
        f"Фразы размечал ИИ-ассистент, которому не показывали условие, вопрос и эталон. "
        f"Для {checks['automatic']} из {sum(checks.values())} модельных фраз запись направления независимо совпала с "
        f"однозначным началом клиентской фразы при машинной проверке. Число фраз, для которых потребовалась "
        f"интерпретация ассистента, — {checks['reviewed']}. Пояснения к потенциально противоречивым фразам доступны в [журнале](model/ratings.json).", "",
        "Ссылки ведут к дословным выходам модели. Для шаблона показан разбор самой клиентской фразы. "
        "Проверить полный текст фраз, входные уровни и выпуски можно в [разобранных примерах](examples.md). "
        "В колонках величина указана по модулю, направление записано отдельно. Прочерк означает отсутствие признака.", "",
        "| Пара и вопрос | Способ | Эталон | Фраза | Пара ячеек | Источник |",
        "|---|---|---|---|---|---|"])
    def rendered(record):
        amount = "—" if record["amount"] is None else format(record["amount"],"f").replace(".",",")
        return " ".join([DIRECTIONS[record["direction"]],amount,UNITS.get(record["unit"],"—")])
    for r in rows:
        g = r["gold"]
        src = f"[{r['id']}](model/responses/{r['id']}.json)" if r["arm"] != "template" else "[фраза](examples.md)"
        lines.append(f"| {r['case']} · {QUESTIONS[r['q']]} | {ARMS[r['arm']]} | {rendered(g)} ({g['pair']}) | "
                     f"{rendered(r)} | {r['pair'] or '—'} | {src} |")
    lines.extend(["", "Выбраны известные случаи с расхождением знаков и контрольные пары. Эти доли описывают данный набор, "
                  "одну версию модели, две формулировки и зафиксированный способ предъявления чисел."])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare regenerated report with the saved file")
    args = parser.parse_args()
    result = full_report()
    target = ROOT / "results.md"
    if args.check:
        require(target.read_text(encoding="utf-8") == result, "results.md differs from the regenerated report")
        print("Checked research design, raw responses, ratings IDs, template phrases and results.md.")
    else:
        target.write_text(result, encoding="utf-8")
        print("Wrote results.md.")
