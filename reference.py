"""Calculate the two point-estimate comparisons and render the client examples offline."""
import argparse
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MONTHS = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
          "сентябрь", "октябрь", "ноябрь", "декабрь")
GENITIVE = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
            "сентября", "октября", "ноября", "декабря")
AGENCIES = {"thousand jobs": "BLS", "index points": "ФРС"}
MEASURES = {
    "thousand jobs": "оценка занятости вне сельского хозяйства США",
    "index points": "оценка индекса промышленного производства США",
}


def load_cases():
    """Read the archived source registers. Begin with the BLS example and its G.17 counterpart."""
    bls = json.loads((ROOT / "bls/cases.json").read_text())
    g17 = json.loads((ROOT / "g17/cases.json").read_text())
    return [bls[0], g17[0], *bls[1:], *g17[1:]]


def levels(case):
    return tuple(Decimal(case[key]) for key in ("previous_level", "revised_level", "current_level"))


def differences(previous, revised, current):
    return current - revised, revised - previous, current - previous


def changes(case):
    """Return published monthly change, revision to the previous month, change since last release."""
    return differences(*levels(case))


def number(value, signed=False):
    """Keep the printed precision and decimal comma. Zero has no directional sign."""
    sign = "−" if value < 0 else "+" if signed and value > 0 else ""
    return sign + format(abs(value), "f").replace(".", ",")


def month_name(iso_month):
    year, month = map(int, iso_month.split("-"))
    return f"{MONTHS[month - 1]} {year} г."


def day_name(iso_date):
    parsed = date.fromisoformat(iso_date)
    return f"{parsed.day} {GENITIVE[parsed.month - 1]} {parsed.year} г."


def quantity(value, unit):
    magnitude = abs(value)
    if unit == "thousand jobs":
        return f"{number(magnitude)} тыс. рабочих мест"
    if magnitude != magnitude.to_integral_value():
        noun = "пункта"
    elif 11 <= int(magnitude) % 100 <= 14 or int(magnitude) % 10 not in (1, 2, 3, 4):
        noun = "пунктов"
    else:
        noun = "пункт" if int(magnitude) % 10 == 1 else "пункта"
    return f"{number(magnitude)} {noun} индекса"


def template(case, question):
    """Return a client sentence in Russian for question 'monthly' or 'since'."""
    if question not in ("monthly", "since"):
        raise ValueError("question must be 'monthly' or 'since'")
    monthly, _, since = changes(case)
    delta = monthly if question == "monthly" else since
    unit = case["unit"]
    intro = (f"По данным {AGENCIES[unit]} от {day_name(case['current_date'])}, "
             f"{MEASURES[unit]} с сезонной корректировкой за {month_name(case['current_month'])}")
    prior_month = month_name(case["prior_month"])
    source = ("в том же выпуске" if question == "monthly"
              else f"в выпуске от {day_name(case['previous_date']).removesuffix('.')}")
    if delta == 0:
        return f"{intro} совпала с оценкой за {prior_month} {source} с точностью публикации."
    direction = "выше" if delta > 0 else "ниже"
    return f"{intro} оказалась на {quantity(delta, unit)} {direction} оценки за {prior_month} {source}."


def validate(cases):
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Repeated release-pair ID.")
    for case in cases:
        previous_publication = date.fromisoformat(case["previous_date"])
        current_publication = date.fromisoformat(case["current_date"])
        previous_month = date.fromisoformat(case["prior_month"] + "-01")
        current_month = date.fromisoformat(case["current_month"] + "-01")
        month_gap = 12 * (current_month.year - previous_month.year) + current_month.month - previous_month.month
        if month_gap != 1 or previous_publication >= current_publication:
            raise ValueError(f"Unexpected reference month or release date in {case['id']}")
        if case["unit"] not in AGENCIES:
            raise ValueError(f"Unsupported unit in {case['id']}")
        for key in ("previous_file", "current_file"):
            if not (ROOT / case[key]).is_file():
                raise FileNotFoundError(case[key])
        monthly, revision, since = changes(case)
        if monthly + revision != since:
            raise ArithmeticError(case["id"])
        if check := case.get("archive_crosscheck"):
            full = [Decimal(value) for value in check["levels"]]
            rounded = [value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) for value in full]
            if tuple(rounded) != levels(case):
                raise ValueError(f"Archive values disagree with the printed levels in {case['id']}")


def source_link(case, role, text):
    return f"[{text}]({case[role + '_url']}) ([копия]({case[role + '_file']}))"


def describe(case):
    previous, revised, current = levels(case)
    monthly, revision, since = changes(case)
    unit = "тыс. рабочих мест" if case["unit"] == "thousand jobs" else "пункты индекса"
    agency = AGENCIES[case["unit"]]
    name = "занятость вне сельского хозяйства" if agency == "BLS" else "промышленное производство"
    previous_source = source_link(case, "previous", day_name(case["previous_date"]))
    current_source = source_link(case, "current", day_name(case["current_date"]))
    lines = [
        f"## {agency} · {name} · {month_name(case['current_month'])}",
        "",
        f"Последовательные выпуски — {previous_source} и {current_source}.",
        "",
        f"**Строка и колонки.** {case['locator']}",
        "",
        f"| Величина ({unit}) | Вычитание опубликованных уровней | Разница |",
        "|---|---:|---:|",
        f"| За месяц по текущей публикации (C − B) | {number(current)} − {number(revised)} | {number(monthly, True)} |",
        f"| Пересмотр прошлого уровня (B − A) | {number(revised)} − {number(previous)} | {number(revision, True)} |",
        f"| От последнего уровня предыдущего выпуска (C − A) | {number(current)} − {number(previous)} | {number(since, True)} |",
        "",
        f"**Ответ на первый вопрос.** {template(case, 'monthly')}",
        "",
        f"**Ответ на второй вопрос.** {template(case, 'since')}",
    ]
    if check := case.get("archive_crosscheck"):
        exact = [Decimal(x) for x in check["levels"]]
        deltas = differences(*exact)
        level_text = " / ".join(number(x) for x in exact)
        delta_text = " / ".join(number(x, True) for x in deltas)
        sign = lambda x: (x > 0) - (x < 0)
        direction_text = ("Направления обоих клиентских ответов совпадают на обеих точностях."
                          if [sign(x) for x in (deltas[0], deltas[2])] == [sign(monthly), sign(since)]
                          else "Направление зависит от доступной точности.")
        percent = number(Decimal(check["official_monthly_percent"]), True)
        lines.extend([
            "",
            f"**Проверка точности.** Уровни A, B, C в архиве G.17 равны {level_text}. "
            f"Три соответствующие разницы в порядке строк таблицы равны {delta_text} пункта индекса. "
            f"{direction_text} ФРС также напечатала темп за месяц {percent}% относительно уточнённого уровня. "
            "[Архив винтажей G.17](g17/revision-vintages.txt)",
        ])
    return lines


def render(cases):
    lines = [
        "# Два вопроса к двум последовательным выпускам",
        "",
        "1. Как показатель изменился за последний месяц по текущей публикации?",
        "2. Насколько последний опубликованный уровень отличается от уровня, который клиент видел в предыдущем выпуске?",
        "",
        "A — последний уровень в предыдущем выпуске. B — оценка того же месяца в текущем выпуске. "
        "C — уровень нового месяца в текущем выпуске. Для каждой пары разность C − A равна сумме C − B и B − A. "
        "Направление относится к опубликованной точечной оценке. Сам по себе знак не устанавливает статистическую значимость движения.",
        "",
        "Оба запроса получают один пакет из двух выпусков и трёх подписанных уровней. Для промышленного производства используем "
        "печатную точность индекса (2017 = 100, один десятичный знак), поэтому ответ измерен в пунктах индекса. "
        "Архив ФРС с четырьмя знаками даёт отдельную проверку округления. Нулевой печатный пересмотр может скрывать малую поправку. "
        "[Архив ФРС](https://www.federalreserve.gov/releases/g17/download.htm)",
    ]
    for case in cases:
        lines.extend(["", *describe(case)])
    same_direction = [case for case in cases if changes(case)[0] * changes(case)[2] > 0]
    differing_amount = [case for case in same_direction if changes(case)[0] != changes(case)[2]]
    names = ", ".join(f"{AGENCIES[case['unit']]} за {month_name(case['current_month'])}" for case in differing_amount).rstrip(".")
    lines.extend(["", "## Как читать контрольные случаи", "",
                  f"На {len(same_direction)} парах знаки двух ответов совпадают. "
                  f"Одинаковое направление при разных величинах дают следующие данные — {names}. "
                  "Верный знак в таком случае сам по себе не доказывает, что система выбрала правильный период сравнения."])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate inputs and check the generated Markdown")
    options = parser.parse_args()
    all_cases = load_cases()
    validate(all_cases)
    output = render(all_cases)
    target = ROOT / "examples.md"
    if options.check:
        if target.read_text() != output:
            raise SystemExit("examples.md differs from the reference calculation.")
        print(f"Checked {len(all_cases)} release pairs and {2 * len(all_cases)} client answers.")
    else:
        target.write_text(output)
        print(f"Wrote {target.name}.")
