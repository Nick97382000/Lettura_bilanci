from utilities.clear_check_oic import * 
import pandas as pd
import numpy as np
import config as cf

def calcola_passivita_correnti(tabella, col_label, cols_valori,
                               iniz_deb, fin_deb, alias_correnti):
    """
    Calcola le passività correnti, in argomento vengono passati:
    - tabella: un DataFrame pandas.
    - col_label: indice della colonna che contiene le etichette testuali.
    - cols_valori: lista delle colonne che contengono i valori numerici da sommare.
    - inizio e fine del blocco debiti e alias

    l'algoritmo effettua i seguenti passaggi:
    - prende la colonna delle etichette e normalizza il testo
    - identifica inizio e fine del blocco debiti
    """
    testi = tabella.iloc[:, col_label].astype(str).apply(norm)

    # inizio/fine blocco debiti
    idx_inizio = testi[testi.str.contains(iniz_deb, na=False, regex=False)].index
    idx_fine = testi[testi.str.contains(fin_deb, na=False, regex=False)].index

    #ritorna none se non trova il blocco iniziale o finale
    if len(idx_inizio) == 0 or len(idx_fine) == 0:
        return [None] * len(cols_valori)

    #prende il primo elemento trovato corrispondente all'inizio blocco e come fine
    #il primo elemento della fine successivo all'elemento precedente
    idx_inizio = idx_inizio[0]
    idx_fine = next((i for i in idx_fine if i > idx_inizio), None)

    #se non c'è riga successiva all'inizio ritorna none
    if idx_fine is None:
        return [None] * len(cols_valori)

    #estrae la sottotabella interessata, tenendo solo la colonna delle etichette
    #e la colonna con i valori numerici da sommare; normalizza le etichette
    sotto = tabella.loc[idx_inizio:idx_fine, [col_label] + cols_valori].copy()
    sotto["label_norm"] = sotto.iloc[:, col_label].astype(str).apply(norm)

    #verifica se la riga contiene uno degli alias definiti e copia tali valori in
    #dataset a parte
    mask = sotto["label_norm"].apply(lambda x: any(a in x for a in alias_correnti))
    righe_correnti = sotto.loc[mask].copy()

    #se non trova righe restituisce none
    if righe_correnti.empty:
        return [None] * len(cols_valori)

    #pulisce i numeri presenti nelle righe
    for col in cols_valori:
        righe_correnti[col] = righe_correnti[col].apply(pulisci_numero)

    #calcola la somma e la restituisce
    somme = righe_correnti[cols_valori].sum(axis=0, skipna=True).tolist()
    return [None] * len(cols_valori) if all(pd.isna(v) for v in somme) else somme

def summary_tabella(tabella, labels_dict):
    """
    analizza la tabella oic, restituendo i valori di interesse indicati in labels_dict
    """
    #gestisco in modo diverso se la tabella ha 5 colonne o 3, se ne ha 5 unisco
    #le prime due colonne
    if tabella.shape[1] == 3:
        date = tabella.iloc[0, 1:3].tolist()

    elif tabella.shape[1] == 5:
        tabella.iloc[:,0] = (
            tabella.iloc[:,0].fillna("").astype(str).str.strip()
                .str.cat(tabella.iloc[:,1].fillna("").astype(str).str.strip(),
                            sep=" ")
        )
        # elimina la colonna 1
        tabella.drop(tabella.columns[1], axis=1, inplace=True)

        # ricavo le date sui nuovi indici 1 e 2
        date = tabella.iloc[0, 1:3].tolist()

    else:
        return pd.DataFrame()

    col_label = tabella.columns[0]
    cols_valori = tabella.columns[1:3].tolist()

    righe = {}
    col_testi = tabella.iloc[:, col_label].astype(str)

    #scorre sui nomi da estrarre, applicando le logiche di include ed exclude
    for nome_output, regola in labels_dict.items():
        trovato = False

        for include in regola["include"]:
            mask = col_testi.apply(lambda x: match_testo(x, include, regola["exclude"]))
            if not mask.any():
                continue

            for _, row in tabella.loc[mask, cols_valori].iterrows():
                valori = row.tolist()
                if riga_valida(valori):
                    righe[nome_output] = [pulisci_numero(v) for v in valori]
                    trovato = True
                    break

            if trovato:
                break

        if not trovato:
            righe[nome_output] = [None] * len(cols_valori)

    righe["passivita_correnti"] = calcola_passivita_correnti(tabella, col_label, cols_valori,
                                                             cf.iniz_deb, cf.fin_deb, cf.alias_correnti)

    return pd.DataFrame.from_dict(righe, orient="index", columns=date)

import pdfplumber

def trova_tabella_bilancio(pdf_path, keywords):
    """
    trova e restituisce la tabella bilancio OIC, in argomento:
    - pdf_path: indica il percorso del file pdf da analizzare
    - keywords indica le parole chiave che identificano la prima pagina del bilancio
    """
    #leggo il pdf ed estraggo le tabelle; per ogni tabella la converto in un unica
    #stringa e controllo che le keywords siano presenti al suo interno; in caso
    #positivo salvo l'indice della pagina di riferimento.
    with pdfplumber.open(pdf_path) as pdf:
        pagina_start = None
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for ii, t in enumerate(tables):
                testo = " ".join(
                    str(cell).lower()
                    for row in t
                    for cell in row
                    if cell
                )
                if all(kw in testo for kw in keywords):
                    pagina_start = i
                    break;
            if pagina_start is not None:
                break

        if pagina_start is None:
            return None

        #legge a partire dalla tabella iniziale di riferimento, continua a leggere
        #finchè sono presenti tabelle nelle pagine successive, unendo tutto il
        #contenuto in un dataframe pandas
        tutte_le_righe = []
        intestazione = None

        for i in range (pagina_start, len(pdf.pages)):
                tables = pdf.pages[i].extract_tables()

                if not tables:
                    break

                for t in tables:
                    righe = [r for r in t if any(c for c in r)]
                    tutte_le_righe.extend(righe)

        if tutte_le_righe:
            n_colonne = max(len(r) for r in tutte_le_righe)
            tutte_le_righe = [r + [None]*(n_colonne - len(r)) for r in tutte_le_righe]

            df = pd.DataFrame(tutte_le_righe)
            return df
    return None
