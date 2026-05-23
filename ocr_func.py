import re
import pandas as pd
import pytesseract
from pdf2image import convert_from_path


def normalizza_testo(s):
    return " ".join(str(s).lower().split())


def ocr_data(img, lang="ita", psm=6):
    return pytesseract.image_to_data(
        img,
        lang=lang,
        output_type=pytesseract.Output.DICT,
        config=f"--psm {psm}"
    )


def estrai_testo_pagina(img, lang="ita"):
    testo = pytesseract.image_to_string(img, lang=lang, config="--psm 6")
    return normalizza_testo(testo)


def trova_pagina_iniziale(immagini, start_marker, lang="ita"):
    for i, img in enumerate(immagini):
        testo = estrai_testo_pagina(img, lang=lang)
        if start_marker in testo:
            return i
    return None


def estrai_date_e_posizioni(img, lang="ita"):
    data = ocr_data(img, lang=lang, psm=6)
    pattern = re.compile(r"\d{2}[-/]\d{2}[-/]\d{4}")

    trovate = []
    for i, txt in enumerate(data["text"]):
        txt = txt.strip()
        if pattern.fullmatch(txt):
            left = data["left"][i]
            top = data["top"][i]
            width = data["width"][i]
            height = data["height"][i]
            trovate.append({
                "text": txt,
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
                "x_center": left + width / 2
            })

    if len(trovate) < 2:
        return None

    trovate = sorted(trovate, key=lambda x: x["x_center"])
    return trovate[-2], trovate[-1]


def estrai_righe_area(img, lang="ita", psm=4):
    data = ocr_data(img, lang=lang, psm=psm)

    parole = []
    n = len(data["text"])
    for i in range(n):
        txt = data["text"][i].strip()
        if not txt:
            continue

        try:
            conf = float(data["conf"][i])
        except:
            conf = -1

        if conf < 20:
            continue

        parole.append({
            "text": txt,
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i]
        })

    if not parole:
        return []

    parole = sorted(parole, key=lambda x: (x["top"], x["left"]))

    righe = []
    corrente = [parole[0]]
    soglia_y = 10

    for p in parole[1:]:
        top_medio = sum(x["top"] for x in corrente) / len(corrente)
        if abs(p["top"] - top_medio) <= soglia_y:
            corrente.append(p)
        else:
            righe.append(corrente)
            corrente = [p]
    righe.append(corrente)

    risultato = []
    for r in righe:
        r = sorted(r, key=lambda x: x["left"])
        testo = " ".join(x["text"] for x in r).strip()
        top_medio = sum(x["top"] for x in r) / len(r)
        risultato.append({
            "text": testo,
            "top": top_medio
        })

    return risultato


def unisci_righe_per_top(label_rows, d1_rows, d2_rows, tolleranza=12):
    tutte_le_top = []

    for r in label_rows:
        tutte_le_top.append(r["top"])
    for r in d1_rows:
        tutte_le_top.append(r["top"])
    for r in d2_rows:
        tutte_le_top.append(r["top"])

    if not tutte_le_top:
        return []

    tutte_le_top = sorted(tutte_le_top)

    cluster = []
    gruppo = [tutte_le_top[0]]
    for t in tutte_le_top[1:]:
        if abs(t - sum(gruppo) / len(gruppo)) <= tolleranza:
            gruppo.append(t)
        else:
            cluster.append(sum(gruppo) / len(gruppo))
            gruppo = [t]
    cluster.append(sum(gruppo) / len(gruppo))

    def closest_text(rows, y, tol):
        candidati = [r for r in rows if abs(r["top"] - y) <= tol]
        if not candidati:
            return None
        candidati = sorted(candidati, key=lambda r: abs(r["top"] - y))
        return candidati[0]["text"]

    out = []
    for y in cluster:
        label = closest_text(label_rows, y, tolleranza)
        data1 = closest_text(d1_rows, y, tolleranza)
        data2 = closest_text(d2_rows, y, tolleranza)
        if label or data1 or data2:
            out.append([label, data1, data2])

    return out


def riga_spuria(label):
    if not label:
        return False

    l = normalizza_testo(label)
    patterns = [
        "bilancio di esercizio al",
        "generato automaticamente",
        "conforme alla tassonomia",
        "pag.",
        "gollinucci srl",
        "soggetta a direzione e coordinamento",
        "v.2."
    ]
    return any(p in l for p in patterns)


def estrai_righe_tabella_da_pagina(img, colonne, lang="ita"):
    w, h = img.size

    x1 = colonne["x1"]
    x2 = colonne["x2"]
    y_start = colonne["y_start"]

    area_label = img.crop((0, y_start, x1, h))
    area_d1 = img.crop((x1, y_start, x2, h))
    area_d2 = img.crop((x2, y_start, w, h))

    righe_label = estrai_righe_area(area_label, lang=lang, psm=4)
    righe_d1 = estrai_righe_area(area_d1, lang=lang, psm=4)
    righe_d2 = estrai_righe_area(area_d2, lang=lang, psm=4)

    righe = unisci_righe_per_top(righe_label, righe_d1, righe_d2, tolleranza=12)
    return righe


def trova_tabella_oic_multipaagina(
    pdf_path,
    start_marker="stato patrimoniale",
    end_marker="conto economico",
    lang="ita",
    dpi=300
):
    immagini = convert_from_path(pdf_path, dpi=dpi)

    start_marker = normalizza_testo(start_marker)
    end_marker = normalizza_testo(end_marker)

    pagina_start = trova_pagina_iniziale(immagini, start_marker, lang=lang)
    if pagina_start is None:
        return None

    # trova coordinate colonne sulla prima pagina utile
    date_pos = estrai_date_e_posizioni(immagini[pagina_start], lang=lang)
    if date_pos is None:
        return None

    d1, d2 = date_pos

    colonne = {
        "x1": int(d1["left"] - 40),
        "x2": int(d2["left"] - 40),
        "y_start": int(min(d1["top"], d2["top"]) + 25)
    }

    risultati = []
    collecting = False

    for i in range(pagina_start, len(immagini)):
        img = immagini[i]

        righe = estrai_righe_tabella_da_pagina(img, colonne, lang=lang)

        for label, data1, data2 in righe:
            label_norm = normalizza_testo(label or "")

            if not collecting:
                if start_marker in label_norm:
                    collecting = True
                continue

            if label and end_marker in label_norm:
                return pd.DataFrame(risultati, columns=["label", "data1", "data2"])

            if riga_spuria(label):
                continue

            if label is None and data1 is None and data2 is None:
                continue

            risultati.append([label, data1, data2])

    if risultati:
        return pd.DataFrame(risultati, columns=["label", "data1", "data2"])

    return None
