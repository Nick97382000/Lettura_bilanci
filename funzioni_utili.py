import pandas as pd

def norm(x):
    """
    pulisce la stringa passata in argomento, effettuando:
    - conversione a tringa
    - trasforma in minuscolo
    - sostituisce a capo con spazio
    - rimuove eventuali spazi multipli
    """
    x = str(x).lower().replace("\n", " ")
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


def match_testo(testo, include, exclude):
    """
    verifica che nel testo passato in argomento sia presente la stringa di include
    e non sia presente nessuna delle stringhe passate in exclude (include è singola)
    """
    testo = norm(testo)
    return include.lower() in testo and not any(e.lower() in testo for e in exclude)


def calcola_passivita_correnti(tabella, col_label, cols_valori):
    
    testi = tabella.iloc[:, col_label].astype(str).apply(norm)

    # inizio/fine blocco debiti
    idx_inizio = testi[testi.str.contains("d) debiti", na=False, regex=False)].index
    idx_fine = testi[testi.str.contains("e) ratei e risconti", na=False, regex=False)].index

    if len(idx_inizio) == 0 or len(idx_fine) == 0:
        return [None] * len(cols_valori)

    idx_inizio = idx_inizio[0]
    idx_fine = next((i for i in idx_fine if i > idx_inizio), None)

    if idx_fine is None:
        return [None] * len(cols_valori)

    sotto = tabella.loc[idx_inizio:idx_fine, [col_label] + cols_valori].copy()
    sotto["label_norm"] = sotto.iloc[:, 0].astype(str).apply(norm)


    alias_correnti = [
        "esigibili entro l'esercizio successivo",
        "sigibili entro l'esercizio successivo",
    ]

    mask = sotto["label_norm"].apply(lambda x: any(a in x for a in alias_correnti))
    righe_correnti = sotto.loc[mask].copy()


    if righe_correnti.empty:
        return [None] * len(cols_valori)

    for col in cols_valori:
        righe_correnti[col] = righe_correnti[col].apply(pulisci_numero)

    somme = righe_correnti[cols_valori].sum(axis=0, skipna=True).tolist()
    return [None] * len(cols_valori) if all(pd.isna(v) for v in somme) else somme
