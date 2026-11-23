"""Build fixed prompts and run stateless, local, paired Qwen inference."""
import argparse
import hashlib
import json
import random
import re
import subprocess
import urllib.request
from pathlib import Path

from reference import changes, load_cases

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model"
SEED = 20261122
SYSTEM = (
    "Вы аналитик StatGazer. Отвечайте по предоставленным выдержкам и проверенным ячейкам. "
    "Дайте одну ясную фразу для клиента на русском. Начните её словом «Выше», «Ниже», "
    "«Без изменения» или «Недостаточно данных». Укажите величину в единицах уровней и базу "
    "сравнения. На отдельной строке напишите «Ячейки:» и вычитание идентификаторов двух "
    "ячеек, использованных для ответа. Если информации недостаточно, прямо скажите об этом."
)
QUESTIONS = {
    "monthly": "Как показатель изменился за последний месяц по текущей публикации?",
    "since": "Насколько последний опубликованный уровень отличается от уровня, который клиент видел в предыдущем выпуске?",
}
DECOMPOSITION = (
    "Разложите изменение между двумя публикациями на две части. Изменение за месяц "
    "по текущей публикации равно C − B. Пересмотр прошлого уровня равен B − A. "
    "Последний уровень минус последний уровень из предыдущего выпуска равен "
    "(C − B) + (B − A) = C − A. Выберите часть или сумму, о которой спрашивает клиент."
)

def dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def excerpt(case, which):
    path = ROOT / case[f"{which}_file"]
    if path.suffix == ".pdf":
        manifest = json.loads((ROOT / "bls/manifest.json").read_text())
        record = next(r for r in manifest if r["release_date"] == case[f"{which}_date"])
        page = str(record["table_page"])
        data = subprocess.check_output(["pdftotext", "-f", page, "-l", page, "-layout", str(path), "-"], text=True)
        lines = data.splitlines()
        end = next(i for i, s in enumerate(lines) if s.startswith("Total nonfarm"))
        return "\n".join(s.rstrip() for s in lines[:end+1])
    lines = path.read_text().splitlines()
    start = next(i for i,s in enumerate(lines) if "Industrial Production and Capacity Utilization:" in s and "Summary" in s)
    end = next(i for i,s in enumerate(lines[start:],start) if s.strip().startswith("Total index"))
    return "\n".join(s.rstrip() for s in lines[start:end+1] if not re.fullmatch(r"[\s|\-]+", s))

def packet(c):
    monthly, revision, since = changes(c)
    texts = []
    for which, title in (("previous", "Предыдущий выпуск"), ("current", "Текущий выпуск")):
        texts.append(f"{title} от {c[which+'_date']}, {c[which+'_url']}\n{excerpt(c,which)}")
    texts.append(f"Проверенные ячейки. Ряд: {c['series']}. Единицы уровней: {c['unit']}.\n"
                 f"A | выпуск {c['previous_date']} | месяц {c['prior_month']} | {c['previous_level']}\n"
                 f"B | выпуск {c['current_date']} | месяц {c['prior_month']} | {c['revised_level']}\n"
                 f"C | выпуск {c['current_date']} | месяц {c['current_month']} | {c['current_level']}\n"
                 f"Калькулятор по этим ячейкам в единицах уровней: B − A = {revision:+f}; "
                 f"C − A = {since:+f}; C − B = {monthly:+f}.")
    return "\n\n".join(texts)

def trial_id(case_id, question, arm):
    return digest(f"trial-v1/{case_id}/{question}/{arm}".encode())[:12]

def make_plan():
    packets, trials = {}, []
    for case in load_cases():
        cid = case["id"]
        packets[cid] = packet(case)
        for question, prompt in QUESTIONS.items():
            for arm in ("direct", "decomposition"):
                content = packets[cid] + "\n\n" + prompt
                if arm == "decomposition":
                    content += "\n" + DECOMPOSITION
                payload = {"model": "qwen3-4b", "messages": [{"role":"system","content":SYSTEM},
                           {"role":"user","content":content + "\n/no_think"}],
                           "temperature":0, "seed":SEED, "max_tokens":300,
                           "chat_template_kwargs":{"enable_thinking":False}, "stream":False}
                trials.append({"id":trial_id(cid,question,arm),"case":cid,"question":question,"arm":arm,
                               "packet_sha256":digest(packets[cid].encode()),"request":payload})
    random.Random(SEED).shuffle(trials)
    return packets, trials

def prepare():
    packets,trials = make_plan()
    for file,obj in [("packets.json",packets),("requests.json",trials)]:
        dest = MODEL / file
        content = dump(obj)
        if dest.exists() and dest.read_text() != content:
            raise ValueError(f"Saved {file} differs from the rebuilt experiment.")
        if not dest.exists():
            dest.write_text(content)
    return trials

def run(outdir):
    trials=prepare()
    outdir.mkdir(parents=True, exist_ok=True)
    for i,t in enumerate(trials,1):
        dest = outdir / (t["id"]+".json")
        if dest.exists():
            continue
        request=urllib.request.Request("http://127.0.0.1:18197/v1/chat/completions",
              data=json.dumps(t["request"],ensure_ascii=False).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = json.load(response)
        if not raw.get("choices") or "message" not in raw["choices"][0]:
            raise ValueError("Server did not return a model response")
        raw["statgazer_request_sha256"]=digest(dump(t["request"]).encode())
        atomic=dest.with_suffix(".tmp")
        atomic.write_text(dump(raw))
        atomic.replace(dest)
        print(f"{i}/{len(trials)} {t['id']}", flush=True)

def export_blind(outdir):
    trials = prepare()
    records=[]
    for t in sorted(trials,key=lambda r:r["id"]):
        raw=json.loads((outdir / (t["id"]+".json")).read_text())
        if raw["statgazer_request_sha256"]!=digest(dump(t["request"]).encode()):
            raise ValueError(t["id"])
        records.append({"id":t["id"],"text":raw["choices"][0]["message"].get("content","")})
    (outdir.parent / "blind.json").write_text(dump(records))

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action",choices=["prepare","run","blind"])
    ap.add_argument("--outdir",type=Path,default=MODEL / "responses")
    args=ap.parse_args()
    if args.action=="prepare":
        print(f"Verified {len(prepare())} requests.")
    elif args.action=="run":
        run(args.outdir)
    else:
        export_blind(args.outdir)
