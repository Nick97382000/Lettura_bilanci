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
    pattern = r'\b(pag\.?|page)\s*\d+\s*(di|of)\s*\d+\b'
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

def merge_and_split_subsections(subsections, min_len=1000, max_len=2000, median_font=11):
    if not subsections: return []
    merged = []
    for item in subsections:
        if len(" ".join(item['df_slice']['text'].astype(str))) < min_len and merged:
            prev = merged[-1]
            if not item['title'].endswith('Initial Content'):
                prev['title'] = f"{prev['title']} / {item['title']}"
            prev['df_slice'] = pd.concat([prev['df_slice'], item['df_slice']], ignore_index=True)
            prev['components'].extend(item['components'])
        else:
            if 'components' not in item:
                txt = " ".join(item['df_slice']['text'].astype(str))
                item['components'] = [{'title': item['title'], 'text': txt}]
            merged.append(item)
    final_list = []
    for item in merged:
        content_str = " ".join(item['df_slice']['text'].astype(str))
        if len(content_str) > max_len:
            internal = _cluster_text_elements_by_font(item['df_slice'], median_font, title_multiplier=1.05)
            if len(internal) > 1:
                mid = len(content_str) / 2
                acc, split_idx = 0, 1
                for i, c in enumerate(internal):
                    acc += len(" ".join(c['df_slice']['text'].astype(str)))
                    if acc > mid:
                        split_idx = max(1, i)
                        break
                p1_df = pd.concat([c['df_slice'] for c in internal[:split_idx]], ignore_index=True)
                p1_comp = []
                for c in internal[:split_idx]: p1_comp.extend(c['components'])
                final_list.append({'title': f"{item['title']} (Part 1)", 'df_slice': p1_df, 'components': p1_comp})
                p2_title = f"{item['title']} / {internal[split_idx]['title']}"
                p2_df = pd.concat([c['df_slice'] for c in internal[split_idx:]], ignore_index=True)
                p2_comp = []
                for c in internal[split_idx:]: p2_comp.extend(c['components'])
                final_list.append({'title': p2_title, 'df_slice': p2_df, 'components': p2_comp})
            else: final_list.append(item)
        else: final_list.append(item)
    return final_list

def process_to_two_levels(text_df, sections_meta, median_font, min_subsection_len=1000):
    main_sections = []
    for meta in sections_meta:
        chunk = text_df.loc[meta['start_idx']:meta['end_idx']].copy()
        clusters = _cluster_text_elements_by_font(chunk, median_font, title_multiplier=1.15)
        processed_subs = merge_and_split_subsections(clusters, min_len=1000, max_len=2000, median_font=median_font)
        main_sections.append({'title': meta['title'], 'subs': processed_subs})
    for main in main_sections: main['subs'] = _merge_short_subsections(main['subs'], min_len=min_subsection_len)
    output = {}
    for main in main_sections:
        output[main['title']] = {}
        for sub in main['subs']:
            # Rimosso il campo 'content' ridondante
            output[main['title']][sub['title']] = {
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
            if 'components_breakdown' in leaf_dict and len(leaf_dict['components_breakdown']) > 1:
                print("    --- Components Breakdown ---")
                for i, comp in enumerate(leaf_dict['components_breakdown']):
                    comp_len = len(comp.get('text', ''))
                    print(f"      [{i+1}] Title: {comp['title']} (Length: {comp_len})")
                print("    --------------------------")
