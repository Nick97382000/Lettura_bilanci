import numpy as np
import pandas as pd
import re
import fitz

# New class to hold content string, its original DataFrame chunk, and a list of its original components
import pandas as pd

class LeafContent:
    def __init__(self, content_string, df_chunk, components=None):
        self.content_string = content_string
        self.df_chunk = df_chunk
        # Each component is expected to be a dict {'title': str, 'df_slice': pd.DataFrame}
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
                if len(full_t) < 120:
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
                if cleaned and len(cleaned) < 120:
                    if curr_rows:
                        # Create a cluster for the accumulated rows before the new title
                        df_slice_for_cluster = pd.DataFrame(curr_rows).reset_index(drop=True)
                        clusters.append({
                            'title': curr_title,
                            'df_slice': df_slice_for_cluster,
                            'components': [{'title': curr_title, 'df_slice': df_slice_for_cluster}]
                        })
                    curr_title, curr_rows = cleaned, [] # Reset for the new title
                else:
                    curr_rows.extend(buffer) # Treat buffer as part of current content if not a valid title
                buffer = []
            curr_rows.append(row)
    if buffer:
        title_text = " ".join([r['text'] for r in buffer]).strip()
        cleaned = clean_page_numbers_from_title(title_text)
        if cleaned and len(cleaned) < 120:
            if curr_rows:
                df_slice_for_cluster = pd.DataFrame(curr_rows).reset_index(drop=True)
                clusters.append({
                    'title': curr_title,
                    'df_slice': df_slice_for_cluster,
                    'components': [{'title': curr_title, 'df_slice': df_slice_for_cluster}]
                })
            df_slice_for_buffer = pd.DataFrame(buffer).reset_index(drop=True)
            clusters.append({
                'title': cleaned,
                'df_slice': df_slice_for_buffer,
                'components': [{'title': cleaned, 'df_slice': df_slice_for_buffer}]
            })
        else:
            curr_rows.extend(buffer)
    if curr_rows:
        df_slice_for_cluster = pd.DataFrame(curr_rows).reset_index(drop=True)
        clusters.append({
            'title': curr_title,
            'df_slice': df_slice_for_cluster,
            'components': [{'title': curr_title, 'df_slice': df_slice_for_cluster}]
        })
    return clusters

def _subsection_content_length(subsection):
    return len(" ".join(subsection['df_slice']['text'].astype(str)))


def _merge_two_clusters(first, second):
    # Determine the merged title
    if first['title'].endswith('Initial Content') and second['title'].endswith('Initial Content'):
        title = first['title']
    elif first['title'].endswith('Initial Content'):
        title = second['title']
    elif second['title'].endswith('Initial Content'):
        title = first['title']
    else:
        title = f"{first['title']} / {second['title']}"

    # Concatenate df_slices
    merged_df_slice = pd.concat([first['df_slice'], second['df_slice']], ignore_index=True)

    # Concatenate components (the new part)
    merged_components = first['components'] + second['components']

    return {
        'title': title,
        'df_slice': merged_df_slice,
        'components': merged_components # Add the merged components
    }


def _merge_short_subsections(subsections, min_len=1000):
    if not subsections:
        return []

    merged_sections = list(subsections)
    while True:
        changed = False
        normalized = []
        i = 0
        while i < len(merged_sections):
            current = merged_sections[i]
            current_len = _subsection_content_length(current)

            if current_len >= min_len or len(merged_sections) == 1:
                normalized.append(current)
                i += 1
                continue

            if i < len(merged_sections) - 1:
                merged_item = _merge_two_clusters(current, merged_sections[i + 1])
                merged_sections[i + 1] = merged_item
                changed = True
                i += 1
            elif normalized:
                merged_item = _merge_two_clusters(normalized.pop(), current)
                normalized.append(merged_item)
                changed = True
                i += 1
            else:
                normalized.append(current)
                i += 1

        merged_sections = normalized
        if not changed:
            break

    return merged_sections


def _merge_small_single_sub_main_sections(main_sections, min_len=1000):
    if not main_sections:
        return []

    normalized = []
    i = 0
    while i < len(main_sections):
        current = main_sections[i]
        if len(current['subs']) == 1 and _subsection_content_length(current['subs'][0]) < min_len and len(main_sections) > 1:
            if normalized:
                prev_main = normalized.pop()
                normalized.append({
                    'title': f"{prev_main['title']} / {current['title']}",
                    'subs': prev_main['subs'] + current['subs'] # Subs are already clusters with components
                })
                i += 1
            elif i < len(main_sections) - 1:
                next_main = main_sections[i + 1]
                normalized.append({
                    'title': f"{current['title']} / {next_main['title']}",
                    'subs': current['subs'] + next_main['subs'] # Subs are already clusters with components
                })
                i += 2
            else:
                normalized.append(current)
                i += 1
        else:
            normalized.append(current)
            i += 1

    return normalized


def merge_and_split_subsections(subsections, min_len=2000, max_len=8000, median_font=11):
    if not subsections: return []
    
    # 1. Merging Step: Merge consecutive short items
    merged = []
    for item in subsections:
        content_str = " ".join(item['df_slice']['text'].astype(str))
        if len(content_str) < min_len and merged:
            prev = merged[-1]
            # Update title
            if not item['title'].endswith('Initial Content'):
                prev['title'] = f"{prev['title']} / {item['title']}"
            # Concatenate df_slice
            prev['df_slice'] = pd.concat([prev['df_slice'], item['df_slice']], ignore_index=True)
            # Extend components list
            prev['components'].extend(item['components'])
        else:
            # Add item as is, ensuring it has a components list
            if 'components' not in item or not item['components']:
                item['components'] = [{'title': item['title'], 'df_slice': item['df_slice']}]
            merged.append(item)

    # 2. Splitting Step (One-level deep for large blocks)
    final_list = []
    for item in merged:
        content_str = " ".join(item['df_slice']['text'].astype(str))
        if len(content_str) > max_len:
            # Re-cluster the large item to find internal sub-structure for splitting
            internal_clusters = _cluster_text_elements_by_font(item['df_slice'], median_font, title_multiplier=1.05)
            
            if len(internal_clusters) > 1: # Only split if internal clustering yields more than one part
                # Try to find a split point roughly in the middle of content length
                mid_point = len(content_str) / 2
                accumulated_len = 0
                split_idx = 1 # Default to splitting after the first internal cluster if no better point found
                for i, c in enumerate(internal_clusters):
                    accumulated_len += len(" ".join(c['df_slice']['text'].astype(str)))
                    if accumulated_len > mid_point:
                        split_idx = max(1, i) # Ensure split_idx is at least 1
                        break
                
                # Create the first part
                part1_title = f"{item['title']} (Part 1)"
                part1_df = pd.concat([c['df_slice'] for c in internal_clusters[:split_idx]], ignore_index=True)
                part1_components = []
                for c in internal_clusters[:split_idx]:
                    part1_components.extend(c['components'])

                final_list.append({
                    'title': part1_title,
                    'df_slice': part1_df,
                    'components': part1_components
                })

                # Create the second part
                # If the split happens mid-internal_cluster, the title should reflect the next logical header
                part2_title_suffix = internal_clusters[split_idx]['title'] if split_idx < len(internal_clusters) else "Rest"
                part2_title = f"{item['title']} / {part2_title_suffix}"
                part2_df = pd.concat([c['df_slice'] for c in internal_clusters[split_idx:]], ignore_index=True)
                part2_components = []
                for c in internal_clusters[split_idx:]:
                    part2_components.extend(c['components'])

                final_list.append({
                    'title': part2_title,
                    'df_slice': part2_df,
                    'components': part2_components
                })
            else:
                # If internal clustering didn't help split, keep the item as is
                final_list.append(item)
        else:
            final_list.append(item)
            
    return final_list


def process_to_two_levels(text_df, sections_meta, median_font, min_subsection_len=1000):
    main_sections = []
    for meta in sections_meta:
        main_title = meta['title']
        chunk = text_df.loc[meta['start_idx']:meta['end_idx']].copy()
        
        # Get sub-candidates using font-based clustering
        clusters = _cluster_text_elements_by_font(chunk, median_font, title_multiplier=1.15)
        # Merge and split within the 2000-8000 range, preserving components
        processed_subs = merge_and_split_subsections(clusters, min_len=2000, max_len=8000, median_font=median_font)
        main_sections.append({'title': main_title, 'subs': processed_subs})

    # Further merge short subsections within each main section
    for main in main_sections:
        main['subs'] = _merge_short_subsections(main['subs'], min_len=min_subsection_len)

    # Merge small main sections that contain only one short subsection
    main_sections = _merge_small_single_sub_main_sections(main_sections, min_len=min_subsection_len)

    # Final pass to merge any remaining short subsections after main section merges
    for main in main_sections:
        main['subs'] = _merge_short_subsections(main['subs'], min_len=min_subsection_len)

    output = {}
    for main in main_sections:
        output[main['title']] = {}
        for sub in main['subs']:
            content_str = " ".join(sub['df_slice']['text'].astype(str))
            # Pass the components list to LeafContent
            output[main['title']][sub['title']] = LeafContent(content_str, sub['df_slice'], sub['components'])
    return output

def display_two_levels(data):
    for main_t, subs in data.items():
        print(f"\n{'='*60}\nMAIN SECTION: {main_t}\n{'='*60}")
        for sub_t, leaf in subs.items():
            print(f"  [SUB-SECTION]: {sub_t} (Total Length: {len(leaf)})")
            if len(leaf.components) > 1 or (len(leaf.components) == 1 and leaf.components[0]['title'] != sub_t):
                print("    --- Components Breakdown ---")
                for i, comp in enumerate(leaf.components):
                    comp_len = len(" ".join(comp['df_slice']['text'].astype(str)))
                    print(f"      [{i+1}] Title: {comp['title']} (Length: {comp_len})")
                print("    --------------------------")
