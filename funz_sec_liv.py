from funzioni base import norm 

def match_testo(testo, include, exclude):
    """
    verifica che nel testo passato in argomento sia presente la stringa di include
    e non sia presente nessuna delle stringhe passate in exclude (include è singola)
    """
    testo = norm(testo)
    return include.lower() in testo and not any(e.lower() in testo for e in exclude)


def calcola_passivita_correnti(tabella, col_label, cols_valori,
                               iniz_deb, fin_deb, alias_correnti):
    """
    Calcola le passività correnti, in argomento vengono passati:
    - tabella: un DataFrame pandas.
    - col_label: indice della colonna che contiene le etichette testuali.
    - cols_valori: lista delle colonne che contengono i valori numerici da sommare.
    - eventuale inizio e fine del blocco debiti e alias

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
