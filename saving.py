
import json
import os

output_dir = 'Lettura_bilanci/output'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created directory: {output_dir}")

# Funzione per rendere il dizionario serializzabile (converte LeafContent in stringa)
def make_serializable(data):
    if isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif hasattr(data, 'content_string'): # Riconosce oggetti LeafContent
        return data.content_string
    return data

output_filename = os.path.basename(sample_pdf_path).replace('.pdf', '_clustered_output.json')
output_path = os.path.join('Lettura_bilanci/output', output_filename)

# Preparazione dei dati
serializable_output = make_serializable(final_clustered_output)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(serializable_output, f, ensure_ascii=False, indent=4)

print(f"Clustered output salvato con successo in: {output_path}")
