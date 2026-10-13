#!/usr/bin/env python3
"""El Salvador: laws and decrees of the Asamblea Legislativa's documentation centre
(https://www.asamblea.gob.sv/leyes-y-decretos). Every norm has a record page
/leyes-y-decretos/view/<id> (title, type, dates, Diario Oficial data) linking the current text
as PDF (/sites/default/files/documents/decretos/<uuid>.pdf).

  pages:    view/1..N (stops after a long run of "REFERENCIA NO ENCONTRADA")
  texts:    download each PDF, verify, extract text -> $RAW/text/<id>.json, delete the PDF
  convert:  -> constitucion/, codigos/, leyes/<year>/, decretos/<year>/, reglamentos/<year>/ ...
"""
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date

import requests
import yaml
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sv_pdfmd as P  # noqa: E402

RAW = os.environ.get("RAW", "/Users/magicaltux/projects/lawcodex/_raw/sv")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
SITE = "https://www.asamblea.gob.sv"
TODAY = date.today().isoformat()
s = requests.Session()
s.headers["User-Agent"] = UA
_last = [0.0]
# www.asamblea.gob.sv does not send its intermediate certificate; add it (from the
# certificate's AIA URL) to certifi's bundle so that TLS verification still happens.
INTERMEDIATE = "http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt"


def ensure_bundle():
    import ssl
    import certifi
    path = os.path.join(RAW, "ca-bundle.pem")
    if not os.path.exists(path):
        der = requests.get(INTERMEDIATE, headers={"User-Agent": UA}, timeout=60).content
        pem = der.decode() if der.startswith(b"-----BEGIN") else ssl.DER_cert_to_PEM_cert(der)
        open(path, "w").write(open(certifi.where()).read() + "\n" + pem)
    s.verify = path


def get(url, binary=False):
    for k in range(5):
        w = 1.0 - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        try:
            r = s.get(url, timeout=(30, 600))
            if r.status_code == 200:
                return r.content if binary else r.content.decode("utf-8", "replace")
            if r.status_code == 404:
                return None
            print("HTTP", r.status_code, url, file=sys.stderr, flush=True)
        except requests.RequestException as e:
            print("ERR", url, e, file=sys.stderr, flush=True)
        time.sleep(15 * (k + 1))
    return None


def slug(t, n=80):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n].rstrip("-")


def parse_view(html):
    soup = BeautifulSoup(html, "lxml")
    txt = re.sub(r"\s+", " ", soup.get_text(" "))
    if "REFERENCIA NO ENCONTRADA" in txt:
        return None
    m = re.search(r"Breadcrumb Home (.+?) Datos de(?:l| la) (\w+):", txt)
    rec = {"title": m.group(1).strip() if m else None, "kind": m.group(2) if m else None}
    for k, lab in (("fecha_emision", "Fecha de Emisión:"), ("materia", "Materia:"), ("numero", "Numero del decreto:"),
                   ("submateria", "Sub-Materia:"), ("tipo", "Tipo:"), ("rama", "Rama del derecho:")):
        m = re.search(re.escape(lab) + r"\s*(.*?)\s+(?:Materia:|Numero del decreto:|Sub-Materia:|Tipo:|Rama del derecho:|Resumen:|Datos de Publicación:)", txt)
        rec[k] = m.group(1).strip() if m else None
    m = re.search(r"Resumen:\s*(.*?)\s+Datos de Publicación:", txt)
    rec["resumen"] = m.group(1).strip() if m else None
    m = re.search(r"Fecha de Publicación:\s*(\S*)\s*(\S*)\s*(\d{2}/\d{2}/\d{4})", txt)
    if m:
        rec["diario_oficial"], rec["tomo"], rec["fecha_publicacion"] = m.group(1), m.group(2), m.group(3)
    pdf = re.findall(r'href ?="(https?://www\.asamblea\.gob\.sv/sites/default/files/documents/decretos/[^"]+)"', html)
    rec["pdf"] = pdf[0] if pdf else None
    return rec


def _pool(items, fn, workers=3, label="", every=500):
    """Run fn over items with up to 3 parallel connections (each paced at 1 request/s)."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    local = threading.local()

    def lget(url, binary=False):
        if not hasattr(local, "s"):
            local.s = requests.Session()
            local.s.headers["User-Agent"] = UA
            local.s.verify = s.verify
            local.last = 0.0
        for k in range(5):
            w = 1.0 - (time.time() - local.last)
            if w > 0:
                time.sleep(w)
            local.last = time.time()
            try:
                r = local.s.get(url, timeout=(30, 600))
                if r.status_code == 200:
                    return r.content if binary else r.content.decode("utf-8", "replace")
                if r.status_code == 404:
                    return None
                print("HTTP", r.status_code, url, file=sys.stderr, flush=True)
            except requests.RequestException as e:
                print("ERR", url, e, file=sys.stderr, flush=True)
            time.sleep(15 * (k + 1))
        return None

    n = 0
    with ThreadPoolExecutor(workers) as ex:
        for _ in ex.map(lambda it: fn(it, lget), items):
            n += 1
            if n % every == 0:
                print(label, n, len(items), flush=True)


def pages(maxid=9000):
    d = os.path.join(RAW, "view")
    os.makedirs(d, exist_ok=True)

    def one(i, lget):
        p = os.path.join(d, f"{i}.json")
        if os.path.exists(p):
            return
        html = lget(f"{SITE}/leyes-y-decretos/view/{i}")
        if html is None:
            return  # transient failure: retry on next run
        json.dump(parse_view(html), open(p, "w"), ensure_ascii=False)

    _pool(list(range(1, maxid)), one, label="view")
    recs = []
    for i in range(1, maxid):
        p = os.path.join(d, f"{i}.json")
        rec = json.load(open(p)) if os.path.exists(p) else None
        if rec:
            rec["id"] = i
            recs.append(rec)
    json.dump(recs, open(os.path.join(RAW, "list.json"), "w"), ensure_ascii=False, indent=0)
    print("records", len(recs))


def texts():
    d = os.path.join(RAW, "text")
    os.makedirs(d, exist_ok=True)
    rows = [r for r in json.load(open(os.path.join(RAW, "list.json"))) if r.get("pdf")]

    def one(r, lget):
        out = os.path.join(d, f"{r['id']}.json")
        if os.path.exists(out):
            return
        tmp = os.path.join(RAW, f"tmp-{r['id']}.pdf")
        res = {"pages": None}
        for k in range(3):
            c = lget(r["pdf"].replace(" ", "%20"), binary=True)
            if not c:
                res["error"] = "download failed"
                break
            k0 = c.find(b"%PDF-", 0, 1024)
            if k0 > 0:  # many files carry a short binary prefix before the PDF header
                c = c[k0:]
            open(tmp, "wb").write(c)
            if P.pdf_ok(tmp):
                try:
                    res = {"pages": P.extract_pages(tmp)}
                except Exception as e:
                    res = {"pages": None, "error": str(e)}
                break
            res["error"] = "incomplete pdf"
        json.dump(res, open(out, "w"), ensure_ascii=False)
        if os.path.exists(tmp):
            os.remove(tmp)

    _pool(rows, one, label="texts", every=200)


def dmy(x):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", x or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def folder_for(r):
    t = (r.get("tipo") or r.get("kind") or "").lower()
    title = (r.get("title") or "").lower()
    if "constituci" in t or re.match(r"constituci[óo]n de la rep[úu]blica", title):
        return "constitucion", "constitution"
    if t.startswith("código") or t.startswith("codigo") or title.startswith("código"):
        return "codigos", "code"
    if t.startswith("ley"):
        return "leyes", "act"
    if "reglamento" in t:
        return "reglamentos", "regulation"
    if "tratado" in t or "convenio" in t:
        return "tratados", "treaty"
    return "decretos", "decree"


def convert():
    st = {}
    skipped = []
    used = set()
    for r in json.load(open(os.path.join(RAW, "list.json"))):
        p = os.path.join(RAW, "text", f"{r['id']}.json")
        pg = json.load(open(p)).get("pages") if os.path.exists(p) else None
        if not pg:
            skipped.append((r["id"], r.get("title"), "sin PDF / descarga fallida"))
            st["nopdf"] = st.get("nopdf", 0) + 1
            continue
        empty = sum(1 for t in pg if len(t.strip()) < 150)
        if empty > 0.5 * len(pg):
            skipped.append((r["id"], r.get("title"), "PDF escaneado (sin capa de texto)"))
            st["scanned"] = st.get("scanned", 0) + 1
            continue
        folder, typ = folder_for(r)
        d = dmy(r.get("fecha_emision"))
        year = d[:4] if d else "sin-fecha"
        title = (r.get("title") or f"Decreto {r.get('numero')}").strip().rstrip(".")
        sub = "" if folder in ("constitucion", "codigos") else f"{year}/"
        fn = f"{folder}/{sub}{slug(title, 70)}-{r['id']}.md"
        md = P.lines_to_md(P.clean_pages(pg))
        front = {"title": title, "identifier": f"Decreto Legislativo N° {r.get('numero')}" if r.get("numero") else None,
                 "type": typ, "jurisdiction": "sv", "language": "es", "date": d,
                 "diario_oficial": f"D.O. N° {r.get('diario_oficial')}, Tomo {r.get('tomo')}, {r.get('fecha_publicacion')}" if r.get("fecha_publicacion") else None,
                 "materia": r.get("materia"), "status": "unknown",
                 "source": f"{SITE}/leyes-y-decretos/view/{r['id']}", "source_pdf": r.get("pdf"), "retrieved": TODAY}
        fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000).strip()
        path = os.path.join(REPO, fn)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pre = "> Texto del documento PDF del Centro de Documentación Legislativa de la Asamblea Legislativa."
        if r.get("resumen"):
            pre += "\n>\n> Resumen (Asamblea Legislativa): " + r["resumen"]
        open(path, "w", encoding="utf-8").write("\n".join(["---", fm, "---", "", f"# {title}", "", pre, "", md, ""]))
        st[folder] = st.get(folder, 0) + 1
    json.dump(skipped, open(os.path.join(RAW, "skipped.json"), "w"), ensure_ascii=False, indent=0)
    print(st)


if __name__ == "__main__":
    ensure_bundle()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("pages", "all"):
        pages()
    if cmd in ("texts", "all"):
        texts()
    if cmd in ("convert", "all"):
        convert()
