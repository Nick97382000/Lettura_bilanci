import unicodedata
import pandas as pd
import numpy as np

def norm(x):
    """
    pulisce la stringa passata in argomento, effettuando:
    - conversione a stringa
    - trasforma in minuscolo
    - sostituisce a capo con spazio
    - sostituisco con un unico tipo di apostrofo o trattino
    - trasformo in generale in forma standardizzata NFKC
    - rimuove eventuali spazi multipli
    """
    x = str(x).lower()
    x = x.replace("\n", " ")
    x = x.replace("’", "'").replace("‘", "'").replace("`", "'")
    x = x.replace("–", "-").replace("—", "-")
    x = unicodedata.normalize("NFKC", x)
    return " ".join(x.split())

def riga_valida(valori):
    """
    verifica che nella riga valori sia presente almeno un valore non nullo
    """
    return any(pd.notna(v) and str(v).strip() != "" for v in valori)

def pulisci_numero(x):
    """
    prova a convertire un valore letto in numero float, effettuando:
    - se nullo ritorna nan
    - conversione a stringa
    - se inizia con parentesi lo interpreta come negativo
    - interpreta "." come separatore migliaia e "," per i decimali; converte a
      formato inglese
    - trasforma in float
    """
    if pd.isna(x):
        return np.nan
    x = str(x).strip()
    if x in ("", "-"):
        return np.nan

    negativo = x.startswith("(") and x.endswith(")")
    x = x.replace("(", "").replace(")", "").strip()

    if "," in x:
        x = x.replace(".", "").replace(",", ".")
    else:
        x = x.replace(".", "")

    try:
        val = float(x)
        return -val if negativo else val
    except:
        return np.nan



