import pandas as pd
import numpy as np
import config as cf
from funz_sec_liv import *

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

