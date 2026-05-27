#definisco valori da includere o escludere nella ricerca del campo specifico
campi_bilancio = {
    "totale_attivo": {
        "include": ["Totale attivo"],
        "exclude": ["circolante"]
    },

    "patrimonio_netto": {
        "include": ["Totale patrimonio netto"],
        "exclude": []
    },

    "totale_attivo_circolante": {
        "include": ["Totale attivo circolante"],
        "exclude": []
    },

    "Totale_disponibilità_liquide": {
        "include": ["Totale disponibilità liquide", "IV - Disponibilità liquide"],
        "exclude": ["esercizio"]
    },

    "Totale_debiti": {
        "include": ["Totale debiti"],
        "exclude": ["verso", "rappresentati", "tributari"]
    },

    "Totale_rimanenze": {
        "include": ["Totale rimanenze", "I - Rimanenze"],
        "exclude": []
    },

    "Totale_crediti_verso_clienti": {
        "include": ["Totale crediti verso clienti", "II - Crediti", "1) Verso clienti"],
        "exclude": []
    },

    "Totale_debiti_verso_fornitori": {
        "include": ["Totale debiti verso fornitori", "Debiti verso fornitori per merci e servizi"],
        "exclude": []
    },

    "Totale_debiti_verso_banche": {
        "include": ["Totale debiti verso banche"],
        "exclude": []
    },

    "avviamento": {
        "include": ["avviamento"],
        "exclude": []
    },

    "ricavi_vendite_e_prestazioni": {
        "include": ["ricavi delle vendite e delle prestazioni"],
        "exclude": []
    },

    "Utile_perdita_esercizio": {
        "include": ["Utile (perdita) dell'esercizio"],
        "exclude": []
    },

    "Risultato_prima_delle_imposte": {
        "include": ["Risultato prima delle imposte"],
        "exclude": []
    },

    "Totale_ammortamenti_e_svalutazioni": {
        "include": ["Totale ammortamenti e svalutazioni"],
        "exclude": []
    },

    "Totale_interessi_e_altri_oneri": {
        "include": ["Totale interessi e altri oneri finanziari", "Totale interessi ed altri oneri finanziari"],
        "exclude": []
    },

    "immobilizzazioni_immateriali": {
        "include": ["Totale immobilizzazioni immateriali", "I - Immobilizzazioni immateriali"],
        "exclude": []
    },

    "immobilizzazioni_materiali": {
        "include": ["Totale immobilizzazioni materiali", "II - Immobilizzazioni materiali"],
        "exclude": []
    },

    "immobilizzazioni_finanziarie": {
        "include": ["Totale immobilizzazioni finanziarie", "III - Immobilizzazioni finanziarie"],
        "exclude": []
    },

    "Flusso_finanziario_attivita_operativa": {
        "include": ["Flusso finanziario dell'attività operativa"],
        "exclude": []
    },

    "Flusso_finanziario_attività_investimento": {
        "include": ["Flusso finanziario dell'attività di investimento", "Totale flusso finanziario dell'attività di investimento"],
        "exclude": []
    },

    "Flusso_finanziario_attività_finanziamento": {
        "include": ["Flusso finanziario dell'attività di finanziamento", "Totale flusso finanziario dell'attività di finanziamento"],
        "exclude": []
    },

  }


#definisco keywords per identificare prima pagina tabella OIC
keywords_first_page = ["immobilizzazioni immateriali", "crediti",
            "immobilizzazioni materiali", "immobilizzazioni finanziarie"]

iniz_deb = "d) debiti"
fin_deb = "e) ratei e risconti"
alias_correnti = ["esigibili entro l'esercizio successivo",
                  "sigibili entro l'esercizio successivo"]
