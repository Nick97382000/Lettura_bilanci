
import json
import os

# Funzione per rendere il dizionario serializzabile (converte LeafContent in stringa)
def make_serializable(data):
    if isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif hasattr(data, 'content_string'): # Riconosce oggetti LeafContent
        return data.content_string
    return data

def save_json(input_pdf_path, output_dir, final_clustered_output):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    output_filename = os.path.basename(input_pdf_path).replace('.pdf', '_clustered_output.json')
    output_path = os.path.join(output_dir, output_filename)

    # Preparazione dei dati
    serializable_output = make_serializable(final_clustered_output)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_output, f, ensure_ascii=False, indent=4)

    print("saved " + input_pdf_path + " in " + output_dir)
    return 

from google.colab import userdata
import os
import subprocess

def push_to_github(repo_path, file_pattern, commit_message):
    """
    Esegue add, commit e push verso GitHub utilizzando il token memorizzato nei Secrets.
    """
    GH_TOKEN = userdata.get('GH_TOKEN')
    current_dir = os.getcwd()
    
    try:
        os.chdir(repo_path)
        
        # Configurazione identità (necessaria se non fatta a livello globale)
        subprocess.run(["git", "config", "user.email", "guerranicholas9738@gmail.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Nicholas Guerra"], check=True)
        
        # Git Add
        subprocess.run(["git", "add", file_pattern], check=True)
        
        # Git Commit (ignoriamo l'errore se non ci sono cambiamenti da committare)
        subprocess.run(["git", "commit", "-m", commit_message], capture_output=True)
        
        # Git Pull --rebase per evitare conflitti
        subprocess.run(["git", "pull", "--rebase"], check=True)
        
        # Git Push
        remote_url = f"https://oauth2:{GH_TOKEN}@github.com/Nick97382000/Lettura_bilanci.git"
        subprocess.run(["git", "push", remote_url], check=True)
        
        print(f"Push completato con successo: {commit_message}")
        
    except Exception as e:
        print(f"Errore durante il push: {e}")
    finally:
        os.chdir(current_dir)
