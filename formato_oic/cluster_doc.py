import numpy as np
import pandas as pd
import re
import fitz

class LeafContent:
    def __init__(self, content_string, df_chunk, components=None):
        self.content_string = content_string
        self.df_chunk = df_chunk
        self.components = components if components is not None else []

    def __len__(self):
        return len(self.content_string)

    def __str__(self):
        return self.content_string

def clean_page_numbers_from_title(title_text):
    pattern = r'\b(pag\.?:?|page)\s*\d+\s*(di|of)?\s*\d*\b'
    cleaned_title = re.sub(pattern, '', title_text, flags=re.IGNORECASE).strip()
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def is_valid_title(title_text):
    text = title_text.strip()
    if not text: return False
    if len(text) <= 1: return False
    if text.isdigit(): return False
    if len(re.sub(r'[^a-zA-Z0-9]', '', text)) < 2: return False
    return True

def extract_text_with_styles_pymupdf(pdf_path):
    all_text_info = []
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            text_data = page.get_text("dict")
            for block in text_data['blocks']:
                if block['type'] == 0:
                    for line in block['lines']:
                        for span in line['spans']:
                            text = span['text'].strip()
                            if text:
                                all_text_info.append({
                                    'page': page_num + 1,
                                    'text': text,
                                    'fontname': span['font'],
                                    'size': span['size'],
                                    'x0': span['bbox'][0], 'y0': span['bbox'][1],
                                    'x1': span['bbox'][2], 'y1': span['bbox'][3]
                                })
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'doc' in locals(): doc.close()
    return pd.DataFrame(all_text_info)

def identify_main_sections_meta(text_df, title_size_threshold_multiplier=1.6, positional_title_size_threshold_multiplier=1.2, y0_page_top_threshold=100):
    if text_df.empty: return [], 0
    size_counts = text_df['size'].value_counts()
    common_sizes = size_counts[size_counts > 5].index.tolist()
    median_body_font_size = pd.Series(common_sizes).median() if common_sizes else text_df['size'].median()
    primary_threshold = median_body_font_size * title_size_threshold_multiplier
    positional_threshold = median_body_font_size * positional_title_size_threshold_multiplier
    potential_title_blocks = []
    temp_buffer = []
    start_idx = -1
    previous_page = -1
    for i, row in text_df.iterrows():
        is_candidate = (row['size'] > primary_threshold) or (row['page'] != previous_page and row['y0'] < y0_page_top_threshold and row['size'] > positional_threshold)
        previous_page = row['page']
        if is_candidate:
            if not temp_buffer: start_idx = i
            temp_buffer.append(row['text'])
        else:
            if temp_buffer:
                full_t = " ".join(temp_buffer).strip()
                if len(full_t) < 120 and is_valid_title(full_t):
                    potential_title_blocks.append((start_idx, i - 1, full_t))
                temp_buffer = []
    last_nota_idx = -1
    for s_idx, _, t_text in potential_title_blocks:
        if "nota" in t_text.lower(): last_nota_idx = s_idx
    sections_meta = []
    curr_t, curr_start = None, -1
    found_first = False
    for s_idx, _, t_text in potential_title_blocks:
        cleaned = clean_page_numbers_from_title(t_text)
        if cleaned and (s_idx >= last_nota_idx or "nota" in cleaned.lower()):
            if not found_first: found_first = True
            if curr_t is not None:
                sections_meta.append({'title': curr_t, 'start_idx': curr_start, 'end_idx': s_idx - 1})
            curr_t, curr_start = cleaned, s_idx
    if curr_t and found_first:
        sections_meta.append({'title': curr_t, 'start_idx': curr_start, 'end_idx': len(text_df) - 1})
    return sections_meta, median_body_font_size

def _cluster_text_elements_by_font(df_to_cluster, median_body_font_size, title_multiplier=1.1):
    if df_to_cluster.empty: return []
    threshold = median_body_font_size * title_multiplier
    clusters = []
    curr_rows = []
    curr_title = "Initial Content"
    buffer = []
    for idx, row in df_to_cluster.iterrows():
        if row['size'] > threshold:
            buffer.append(row)
        else:
            if buffer:
                title_text = " ".join([r['text'] for r in buffer]).strip()
                cleaned = clean_page_numbers_from_title(title_text)
                if cleaned and len(cleaned) < 120 and is_valid_title(cleaned):
                    if curr_rows:
                        df_slice = pd.DataFrame(curr_rows).reset_index(drop=True)
                        clusters.append({'title': curr_title, 'df_slice': df_slice, 'components': [{'title': curr_title, 'text': " ".join(df_slice['text'].astype(str))}]})
                    curr_title, curr_rows = cleaned, []
                else:
                    curr_rows.extend(buffer)
                buffer = []
            curr_rows.append(row)
    if buffer:
        title_text = " ".join([r['text'] for r in buffer]).strip()
        cleaned = clean_page_numbers_from_title(title_text)
        if cleaned and len(cleaned) < 120 and is_valid_title(cleaned):
            if curr_rows:
                df_slice = pd.DataFrame(curr_rows).reset_index(drop=True)
                clusters.append({'title': curr_title, 'df_slice': df_slice, 'components': [{'title': curr_title, 'text': " ".join(df_slice['text'].astype(str))}]})
            df_slice_buf = pd.DataFrame(buffer).reset_index(drop=True)
            clusters.append({'title': cleaned, 'df_slice': df_slice_buf, 'components': [{'title': cleaned, 'text': " ".join(df_slice_buf['text'].astype(str))}]})
        else:
            curr_rows.extend(buffer)
    if curr_rows:
        df_slice = pd.DataFrame(curr_rows).reset_index(drop=True)
        clusters.append({'title': curr_title, 'df_slice': df_slice, 'components': [{'title': curr_title, 'text': " ".join(df_slice['text'].astype(str))}]})
    return clusters

def _subsection_content_length(subsection):
    return len(" ".join(subsection['df_slice']['text'].astype(str)))

def _merge_two_clusters(first, second):
    if first['title'].endswith('Initial Content') and second['title'].endswith('Initial Content'):
        title = first['title']
    elif first['title'].endswith('Initial Content'):
        title = second['title']
    elif second['title'].endswith('Initial Content'):
        title = first['title']
    else:
        title = f"{first['title']} / {second['title']}"
    merged_df = pd.concat([first['df_slice'], second['df_slice']], ignore_index=True)
    merged_comp = first['components'] + second['components']
    return {'title': title, 'df_slice': merged_df, 'components': merged_comp}

def _merge_short_subsections(subsections, min_len=1000):
    if not subsections: return []
    merged_sections = list(subsections)
    while True:
        changed = False
        normalized = []
        i = 0
        while i < len(merged_sections):
            current = merged_sections[i]
            if _subsection_content_length(current) >= min_len or len(merged_sections) == 1:
                normalized.append(current)
                i += 1
                continue
            if i < len(merged_sections) - 1:
                merged_sections[i + 1] = _merge_two_clusters(current, merged_sections[i + 1])
                changed = True
                i += 1
            elif normalized:
                normalized.append(_merge_two_clusters(normalized.pop(), current))
                changed = True
                i += 1
            else:
                normalized.append(current)
                i += 1
        merged_sections = normalized
        if not changed: break
    return merged_sections
def _split_text_by_sentence_recursive(item, min_len=1000, target_len=2000):
    """
    Divide ricorsivamente un item in blocchi di circa target_len basandosi sui punti fermi.
    Assicura che ogni frammento abbia una lista di componenti con titoli 'Part 1', 'Part 2' ecc.
    """
    full_text = " ".join(item['df_slice']['text'].astype(str))
    total_len = len(full_text)

    if total_len <= target_len + min_len:
        if 'components' not in item or not item['components']:
            item['components'] = [{'title': item['title'], 'text': full_text}]
        return [item]

    matches = list(re.finditer(r'\.\s', full_text))
    if not matches:
        if 'components' not in item or not item['components']:
            item['components'] = [{'title': item['title'], 'text': full_text}]
        return [item]

    best_match = None
    for m in matches:
        if m.end() >= min_len and m.end() <= target_len + 500:
            best_match = m
        if m.end() > target_len: break

    if not best_match:
        for m in matches:
            if m.end() >= min_len:
                best_match = m
                break

    if not best_match or (total_len - best_match.end()) < min_len:
        if 'components' not in item or not item['components']:
            item['components'] = [{'title': item['title'], 'text': full_text}]
        return [item]

    split_pos = best_match.end()
    df = item['df_slice']
    lengths = df['text'].astype(str).str.len().cumsum()
    split_row_idx = (lengths <= split_pos).sum()

    p1_df = df.iloc[:split_row_idx].copy()
    p2_df = df.iloc[split_row_idx:].copy()

    if p1_df.empty or p2_df.empty: return [item]

    clean_title = item['title'].split(' (Part')[0]
    
    part1 = {
        'title': f"{item['title']} (Part)",
        'df_slice': p1_df,
        'components': [{'title': f"{clean_title} - Part 1", 'text': " ".join(p1_df['text'].astype(str))}]
    }
    
    remaining_item = {
        'title': item['title'],
        'df_slice': p2_df,
        'components': [{'title': f"{clean_title} - Part 2", 'text': " ".join(p2_df['text'].astype(str))}]
    }

    return [part1] + _split_text_by_sentence_recursive(remaining_item, min_len, target_len)

def _split_large_subsection(clusters, parent_title, min_len=1000, max_len=2000):
    """
    Divide una sub-section molto grande (> 3000 caratteri) usando i cluster (titoli) come punti di rottura naturali.
    Tenta di mantenere i risultati nel range min_len-max_len.
    """
    result_parts = []
    current_part_clusters = []
    current_part_length = 0
    part_counter = 1

    for cluster in clusters:
        cluster_len = len(" ".join(cluster['df_slice']['text'].astype(str)))

        # Se aggiungere questo cluster superherebbe max_len, e abbiamo già almeno min_len:
        if current_part_length + cluster_len > max_len and current_part_length >= min_len and current_part_clusters:
            # Salva la parte corrente
            part_title = f"{parent_title} (Part {part_counter})"
            if current_part_clusters[0].get('title') and not current_part_clusters[0]['title'].startswith('Initial'):
                part_title = f"{parent_title} / {current_part_clusters[0]['title']}"

            part_df = pd.concat([c['df_slice'] for c in current_part_clusters], ignore_index=True)
            part_comp = []
            for c in current_part_clusters:
                part_comp.extend(c['components'])
            result_parts.append({'title': part_title, 'df_slice': part_df, 'components': part_comp})

            # Inizia una nuova parte
            current_part_clusters = [cluster]
            current_part_length = cluster_len
            part_counter += 1
        else:
            # Aggiungi il cluster alla parte corrente
            current_part_clusters.append(cluster)
            current_part_length += cluster_len

    # Aggiungi l'ultima parte
    if current_part_clusters:
        part_title = f"{parent_title} (Part {part_counter})"
        if current_part_clusters[0].get('title') and not current_part_clusters[0]['title'].startswith('Initial'):
            part_title = f"{parent_title} / {current_part_clusters[0]['title']}"

        part_df = pd.concat([c['df_slice'] for c in current_part_clusters], ignore_index=True)
        part_comp = []
        for c in current_part_clusters:
            part_comp.extend(c['components'])
        result_parts.append({'title': part_title, 'df_slice': part_df, 'components': part_comp})

    return result_parts if result_parts else [{'title': parent_title, 'df_slice': pd.concat([c['df_slice'] for c in clusters], ignore_index=True), 'components': [item for c in clusters for item in c['components']]}]
    
def merge_and_split_subsections(subsections, min_len=1000, max_len=2000, median_font=11):
    if not subsections: return []

    # 1. Unione sezioni troppo corte con limite di sicurezza a 3000 caratteri
    merged = []
    for item in subsections:
        item_text = " ".join(item['df_slice']['text'].astype(str))
        item_len = len(item_text)
        
        if merged:
            prev = merged[-1]
            prev_text = " ".join(prev['df_slice']['text'].astype(str))
            combined_len = len(prev_text) + item_len
            
            # Se la sezione precedente è corta E l'unione non supera i 3000 caratteri
            if len(prev_text) < min_len and combined_len <= 3000:
                if not item['title'].endswith('Initial Content'):
                    prev['title'] = f"{prev['title']} / {item['title']}"
                prev['df_slice'] = pd.concat([prev['df_slice'], item['df_slice']], ignore_index=True)
                
                new_comp = {'title': item['title'], 'text': item_text}
                if 'components' not in prev: prev['components'] = []
                prev['components'].append(new_comp)
                continue

        # Se non può essere unito (o perché prev è già lungo o perché l'unione eccede 3000)
        if 'components' not in item:
            item['components'] = [{'title': item['title'], 'text': item_text}]
        merged.append(item)

    # 2. Splitting delle sezioni che risultano ancora troppo lunghe (> max_len)
    final_list = []
    for item in merged:
        content_str = " ".join(item['df_slice']['text'].astype(str))
        curr_len = len(content_str)

        if curr_len <= max_len:
            final_list.append(item)
            continue

        # Prova split strutturale basato su font/titoli
        internal = _cluster_text_elements_by_font(item['df_slice'], median_font, title_multiplier=1.05)
        
        if len(internal) > 1:
            parts = _split_large_subsection(internal, item['title'], min_len, max_len)
            for p in parts:
                p_str = " ".join(p['df_slice']['text'].astype(str))
                if len(p_str) > 3000: # Se ancora troppo grande dopo split strutturale
                    final_list.extend(_split_text_by_sentence_recursive(p, min_len, max_len))
                else:
                    if 'components' not in p or not p['components']:
                        p['components'] = [{'title': p['title'], 'text': p_str}]
                    final_list.append(p)
        else:
            # Split ricorsivo per frasi per blocchi monolitici
            final_list.extend(_split_text_by_sentence_recursive(item, min_len, max_len))

    return final_list

def process_to_two_levels(text_df, sections_meta, median_font, min_subsection_len=1000):
    main_sections = []
    for meta in sections_meta:
        chunk = text_df.loc[meta['start_idx']:meta['end_idx']].copy()
        clusters = _cluster_text_elements_by_font(chunk, median_font, title_multiplier=1.15)
        processed_subs = merge_and_split_subsections(clusters, min_len=1000, max_len=2000, median_font=median_font)
        main_sections.append({'title': meta['title'], 'subs': processed_subs})
    for main_section in main_sections: main_section['subs'] = _merge_short_subsections(main_section['subs'], min_subsection_len)
    output = {}
    for main_section in main_sections:
        main_t = main_section['title']
        output[main_t] = {}
        for sub_idx, sub in enumerate(main_section['subs']):
            output[main_t][f"Sub-section-{sub_idx + 1}"] = {
                "original_descriptive_title": sub['title'],
                "llm_section_title": f"Sub-section-{sub_idx + 1} Placeholder",
                "components_breakdown": sub['components']
            }
    return output

def display_two_levels(data):
    for main_t, subs in data.items():
        print(f"\n{'='*60}\nMAIN SECTION: {main_t}\n{'='*60}")
        for sub_t, leaf_dict in subs.items():
            # Calcolo lunghezza totale basandoci sui componenti
            total_c_len = sum(len(c.get('text', '')) for c in leaf_dict['components_breakdown'])
            print(f"  [SUB-SECTION]: {sub_t} (Total Length: {total_c_len})")
            # Optionally print original descriptive title if needed for debug
            if 'original_descriptive_title' in leaf_dict:
                print(f"    (Original Title: {leaf_dict['original_descriptive_title']})")
            if 'components_breakdown' in leaf_dict and len(leaf_dict['components_breakdown']) > 1:
                print("    --- Components Breakdown ---")
                for i, comp in enumerate(leaf_dict['components_breakdown']):
                    comp_len = len(comp.get('text', ''))
                    print(f"      [{i+1}] Title: {comp['title']} (Length: {comp_len})")
                print("    --------------------------")


def apply_garbled_page_filtering(text_df_processed, page_garbled_ratio_threshold=0.70):
    """
    Applies page-level filtering for garbled text.
    If more than `page_garbled_ratio_threshold` of a page is garbled, the entire page is removed.
    Otherwise, only garbled lines within that page are removed.

    Args:
        text_df_processed (pd.DataFrame): DataFrame with 'page', 'text', 'is_garbled', 'garbled_text_length' columns.
        page_garbled_ratio_threshold (float): Threshold for garbled text ratio on a page to remove the entire page.

    Returns:
        tuple: (filtered_text_df, removed_total_lines, removed_total_chars)
    """
    if text_df_processed.empty:
        return text_df_processed, 0, 0

    # Calculate total original text length per page
    page_original_lengths = text_df_processed.groupby('page')['text'].apply(lambda x: x.str.len().sum())
    # Calculate total garbled text length per page
    page_garbled_lengths = text_df_processed.groupby('page')['garbled_text_length'].sum()
    # Calculate garbled ratio per page
    page_garbled_ratio = (page_garbled_lengths / page_original_lengths.replace(0, 1)).fillna(0)

    # Initialize a mask for rows to keep
    rows_to_keep_mask = pd.Series(True, index=text_df_processed.index)

    removed_total_lines = 0
    removed_total_chars = 0

    # Iterate over each page to apply filtering logic
    for page_num in page_original_lengths.index:
        current_page_df = text_df_processed[text_df_processed['page'] == page_num]
        initial_page_rows = len(current_page_df)

        if page_garbled_ratio.get(page_num, 0) > page_garbled_ratio_threshold:
            # Remove entire page
            rows_to_keep_mask.loc[current_page_df.index] = False
            removed_total_lines += initial_page_rows
            removed_total_chars += page_original_lengths[page_num]
        else:
            # Remove only garbled lines on this page
            garbled_lines_on_page_mask = current_page_df['is_garbled']
            rows_to_keep_mask.loc[garbled_lines_on_page_mask.index[garbled_lines_on_page_mask]] = False
            removed_lines_on_page = garbled_lines_on_page_mask.sum()
            if removed_lines_on_page > 0:
                removed_total_lines += removed_lines_on_page
                removed_total_chars += page_garbled_lengths[page_num]

    # Apply the mask and remove temporary columns
    filtered_text_df = text_df_processed[rows_to_keep_mask].drop(columns=['is_garbled', 'garbled_text_length'])

    return filtered_text_df, removed_total_lines, removed_total_chars

def filter_garbled_text_lines(df, patterns=None, min_alpha_ratio_threshold=0.1):
    """
    Identifies and marks 'garbled' text lines in a DataFrame based on regex patterns
    or a low proportion of alphabetic characters. It also calculates the length of
    the *original* text for lines marked as garbled.

    Args:
        df (pd.DataFrame): The DataFrame containing 'page' and 'text' columns.
        patterns (list): A list of regular expressions to identify 'garbled' text.
                         If None, uses a predefined pattern set.
        min_alpha_ratio_threshold (float): The minimum proportion of alphabetic characters
                                         a line must have to not be considered 'garbled'.

    Returns:
        pd.DataFrame: The DataFrame with an added 'is_garbled' boolean column and 'garbled_text_length' column.
                      'garbled_text_length' will be the length of the original text if 'is_garbled' is True,
                      otherwise 0.
    """
    if df.empty:
        df_copy = df.copy()
        df_copy['is_garbled'] = False
        df_copy['garbled_text_length'] = 0
        return df_copy

    df_copy = df.copy()
    df_copy['text'] = df_copy['text'].astype(str)

    df_copy['is_garbled'] = False

    # Patterns from the earlier, more aggressive version
    if patterns is None:
        patterns = [
            r'^[#\s/%0-9@\.\,\-]+$', # Re-introducing the aggressive numeric/symbol only pattern
            r'^(?:[^\w\s]*[^\w\s]){5,}', # Matches lines with at least 5 non-alphanumeric characters (excluding spaces)
            r'^[^À-ſ\w\s]{10,}$', # Matches lines composed of 10 or more non-alphanumeric non-whitespace characters (including accented chars)
            r'^[_—–—]+$', # Matches lines with only underscores or hyphens (including unicode dashes)
            r"""^[[\\](){}<>\*#%&@^\\|/=+~`.,:;!?'"$£€`•]*$""", # Matches lines containing only common symbols, bullet points
        ]

    for pattern in patterns:
        df_copy.loc[df_copy['text'].str.match(pattern, na=False, flags=re.IGNORECASE), 'is_garbled'] = True

    # Calculate alphabetic ratio
    alpha_counts = df_copy['text'].str.count(r'[a-zA-ZÀ-ſ]')
    text_lengths_stripped = df_copy['text'].str.strip().str.len()
    alpha_ratios = alpha_counts / text_lengths_stripped.replace(0, 1)

    # Mark as garbled if alpha ratio is low and the line is not extremely short (to avoid marking valid short titles)
    df_copy.loc[(alpha_ratios < min_alpha_ratio_threshold) & (text_lengths_stripped > 10), 'is_garbled'] = True

    # Calculate the length of the original text for lines marked as garbled
    df_copy['garbled_text_length'] = df_copy['text'].str.len() # Get original length
    df_copy.loc[~df_copy['is_garbled'], 'garbled_text_length'] = 0 # Set to 0 if not garbled

    return df_copy
