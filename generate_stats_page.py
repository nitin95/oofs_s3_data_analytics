"""
Generate GitHub Pages HTML report from XML pace data
This script processes XML files and generates an interactive multi-page dashboard.
"""

import os
import glob
import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import json
from pathlib import Path

# Configuration
SPRINT_QUALIS = {
    's3-sc1.xml': {'name': 'Portimao', 'ref_time': 103.14},
    's3-sc2.xml': {'name': 'Le Mans', 'ref_time': 235.31},
    's3-sc3.xml': {'name': 'Interlagos', 'ref_time': 93.65},
    's3-sc4.xml': {'name': 'Monza', 'ref_time': 99.01},
    's3-sc5.xml': {'name': 'Sebring', 'ref_time': 120.17},
}


SPRINT_RACES = {
    's3-sc1-r.xml': {'name': 'Portimao', 'ref_time': 103.14},
    's3-sc2-r.xml': {'name': 'Le Mans', 'ref_time': 235.31},
    's3-sc3-r.xml': {'name': 'Interlagos', 'ref_time': 93.65},
    's3-sc4-r.xml': {'name': 'Monza', 'ref_time': 99.01},
    's3-sc5-r.xml': {'name': 'Sebring', 'ref_time': 120.17},
}

MULTICLASS_QUALIS = {
    's3-mc1.xml': {'name': 'Portimao', 'ref_time_p2ur': 91.53, 'ref_time_gt3': 103.14},
    's3-mc2.xml': {'name': 'Le Mans', 'ref_time_p2ur': 206.83, 'ref_time_gt3': 235.31},
    's3-mc3.xml': {'name': 'Interlagos', 'ref_time_p2ur': 82.86, 'ref_time_gt3': 93.65},
    's3-mc4.xml': {'name': 'Monza', 'ref_time_p2ur': 87.27, 'ref_time_gt3': 99.01},
}

MULTICLASS_RACES = {
    's3-mc1-r.xml': {'name': 'Portimao', 'ref_time_p2ur': 91.53, 'ref_time_gt3': 103.14},
    's3-mc2-r.xml': {'name': 'Le Mans', 'ref_time_p2ur': 206.83, 'ref_time_gt3': 235.31},
    's3-mc3-r.xml': {'name': 'Interlagos', 'ref_time_p2ur': 82.86, 'ref_time_gt3': 93.65},
    's3-mc4-r.xml': {'name': 'Monza', 'ref_time_p2ur': 87.27, 'ref_time_gt3': 99.01},
}

DRIVER_REPLACEMENTS = {
    'Greg Kach': 'Greg Kachadurian',
    'R McLean': 'Ross McLean',
    'Ricky Swaby': 'Ricardo Swaby',
    'p thomas': 'Parker Thomas',
    'David Carter': 'Dave Carter',
    'David Carter#5529': 'Dave Carter',
    'John P': 'John Pflibsen',
    'Ayrton Senna': 'Ayrton Torres',
    'Avi Ganti': 'Avinash Ganti',
}

TRACK_NAMES = ['Portimao', 'Le Mans', 'Interlagos', 'Monza', 'Sebring', 'Paul Ricard', 'COTA', 'Spa']


def get_sidebar_html(active_page):
    """Generate sidebar navigation HTML"""
    pages = {
        'sprint-race': ('Sprint', 'Race Pace'),
        'sprint-quali': ('Sprint', 'Quali Pace'),
        'multiclass-p2ur-race': ('Multiclass P2UR', 'Race Pace'),
        'multiclass-p2ur-quali': ('Multiclass P2UR', 'Quali Pace'),
        'multiclass-gt3-race': ('Multiclass GT3', 'Race Pace'),
        'multiclass-gt3-quali': ('Multiclass GT3', 'Quali Pace'),
    }
    
    sidebar_html = '<nav class="sidebar"><div class="sidebar-content"><h3>📊 Dashboard</h3>'
    
    current_section = None
    for page_key, (section, subsection) in pages.items():
        if section != current_section:
            if current_section is not None:
                sidebar_html += '</ul></div>'
            current_section = section
            sidebar_html += f'<div class="section-group"><h4>{section}</h4><ul>'
        
        is_active = 'active' if page_key == active_page else ''
        file_name = page_key.replace('-', '_') + '.html'
        sidebar_html += f'<li><a href="{file_name}" class="{is_active}">{subsection}</a></li>'
    
    sidebar_html += '</ul></div></nav>'
    return sidebar_html


def extract_xml_drivers(xml_path):
    """Parse XML file and extract driver lap time data"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    child = root[0]
    subchild = child[-1]
    drivers_data = []
    
    for driver_elem in subchild.findall('Driver'):
        driver_info = {}
        driver_info['Driver'] = driver_elem.findtext('Name', 'Unknown')
        driver_info['Car'] = driver_elem.findtext('CarType', 'Unknown')
        driver_info['CarClass'] = driver_elem.findtext('CarClass', 'Unknown')
        driver_info['CarNumber'] = driver_elem.findtext('CarNumber', 'N/A')
        driver_info['Position'] = driver_elem.findtext('Position', 'N/A')
        driver_info['BestLapTime'] = driver_elem.findtext('BestLapTime', '')
        driver_info['Laps'] = driver_elem.findtext('Laps', '0')
        driver_info['FinishStatus'] = driver_elem.findtext('FinishStatus', '')
        
        try:
            best_lap_float = float(driver_info['BestLapTime'])
            minutes = int(best_lap_float // 60)
            seconds = best_lap_float % 60
            driver_info['Best Lap'] = f"{minutes}:{seconds:06.3f}"
            driver_info['Best Lap  Laps'] = f"{minutes}:{seconds:06.3f}"
        except (ValueError, TypeError):
            if driver_info['BestLapTime']:
                driver_info['Best Lap'] = driver_info['BestLapTime']
                driver_info['Best Lap  Laps'] = driver_info['BestLapTime']
            else:
                driver_info['Best Lap'] = 'DNF'
                driver_info['Best Lap  Laps'] = 'DNF'
        
        drivers_data.append(driver_info)
    
    if drivers_data:
        return [pd.DataFrame(drivers_data)]
    else:
        return []


def convert_laptime_to_seconds(laptime_str):
    """Convert laptime string (MM:SS.SSS or float) to seconds"""
    if pd.isna(laptime_str) or laptime_str == '' or laptime_str == 'DNF':
        return 0.0
    
    str_val = str(laptime_str).strip()
    
    if ':' in str_val:
        try:
            parts = str_val.split(':')
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0.0
    
    try:
        return float(str_val)
    except ValueError:
        return 0.0


def process_race_data(xml_path, race_name, ref_laptime):
    """Process a single race XML file"""
    tables = extract_xml_drivers(xml_path)
    if not tables:
        return None
    
    df = tables[0].copy()
    df['laptime_sec'] = df['Best Lap  Laps'].apply(convert_laptime_to_seconds)
    df['Driver_name'] = df['Driver'].apply(
        lambda x: str(x).split('LMGT3')[0].strip() if 'LMGT3' in str(x) else str(x).strip()
    )
    
    # Apply driver name replacements
    for old, new in DRIVER_REPLACEMENTS.items():
        df['Driver_name'].replace(old, new, inplace=True)
    
    # Calculate pace percentages
    min_laptime = df[df['laptime_sec'] > 0]['laptime_sec'].min()
    df['laptime_pct'] = round(min_laptime / df['laptime_sec'] * 100, 2) if min_laptime > 0 else 100
    df['laptime_pct_alien'] = round(df['laptime_sec'] / ref_laptime * 100, 2) if ref_laptime > 0 else 100
    
    return df


def process_multiclass_race_data(xml_path, race_name, car_class, ref_laptime):
    """Process a single multiclass race XML file, filtered by car class (P2UR or GT3)"""
    tables = extract_xml_drivers(xml_path)
    if not tables:
        return None
    
    df = tables[0].copy()
    
    # Filter by car class
    if car_class.upper() == 'P2UR':
        df = df[df['CarClass'].str.contains('LMP2_ELMS', case=False, na=False)]
    elif car_class.upper() == 'GT3':
        df = df[df['CarClass'].str.contains('GT3', case=False, na=False)]
    
    if df.empty:
        return None
    
    df['laptime_sec'] = df['Best Lap  Laps'].apply(convert_laptime_to_seconds)
    df['Driver_name'] = df['Driver'].apply(
        lambda x: str(x).split('LMGT3')[0].strip() if 'LMGT3' in str(x) else str(x).strip()
    )
    
    # Apply driver name replacements
    for old, new in DRIVER_REPLACEMENTS.items():
        df['Driver_name'].replace(old, new, inplace=True)
    
    # Calculate pace percentages
    min_laptime = df[df['laptime_sec'] > 0]['laptime_sec'].min()
    df['laptime_pct'] = round(min_laptime / df['laptime_sec'] * 100, 2) if min_laptime > 0 else 100
    df['laptime_pct_alien'] = round(df['laptime_sec'] / ref_laptime * 100, 2) if ref_laptime > 0 else 100
    
    return df


def extract_code_from_filename(filename, prefix):
    """Extract race code from filename (e.g., 's3-sc1-r.xml' -> 'sc1')"""
    # Remove prefix and extensions
    name = filename.replace(f'{prefix}-', '').replace('-r.xml', '').replace('.xml', '')
    return name


def load_races_dynamically(config_dict, xml_folder, is_multiclass=False):
    """
    Load available races from config and return ordered lists.
    
    Returns:
        - race_codes: List of race codes in order
        - track_names: List of track names in order
        - code_to_track: Dict mapping code to track name
    """
    loaded_races = {}
    race_codes = []
    track_names = []
    code_to_track = {}
    
    # Get prefix from first filename for code extraction
    first_filename = list(config_dict.keys())[0]
    if first_filename.startswith('s3-sc'):
        prefix = 's3-sc'
    elif first_filename.startswith('s3-mc'):
        prefix = 's3-mc'
    else:
        return race_codes, track_names, code_to_track
    
    # Sort config by filename to maintain order (s3-sc1, s3-sc2, etc.)
    sorted_items = sorted(config_dict.items(), key=lambda x: x[0])
    
    for filename, race_info in sorted_items:
        xml_path = os.path.join(xml_folder, filename)
        if os.path.exists(xml_path):
            track_name = race_info['name']
            
            # Extract code from filename
            code = extract_code_from_filename(filename, prefix)
            
            # # Get appropriate ref_time
            # if is_multiclass:
            #     # For multiclass, we'll determine class later
            #     pass  # We'll handle this separately
            # else:
            #     ref_time = race_info['ref_time']
            
            race_codes.append(code)
            track_names.append(track_name)
            code_to_track[code] = track_name
    
    return race_codes, track_names, code_to_track


def process_races_into_comparison_df(dfs_dict, race_codes, code_to_track):
    """
    Build a comparison dataframe from loaded race dataframes.
    
    Args:
        dfs_dict: Dictionary of {track_name: dataframe}
        race_codes: List of race codes in order (e.g., ['sc1', 'sc2', 'sc3'])
        code_to_track: Dict mapping code to track name
    
    Returns:
        - comparison_df: Merged dataframe with all races
        - pace_cols: List of pace column names
    """
    if not race_codes:
        return None, []
    
    # Start with first race
    first_code = race_codes[0]
    first_track = code_to_track[first_code]
    
    if first_track not in dfs_dict:
        return None, []
    
    comparison_df = dfs_dict[first_track][['Driver_name', 'laptime_sec', 'laptime_pct', 'laptime_pct_alien']].rename(
        columns={
            'laptime_sec': f'laptime_sec_{first_code}',
            'laptime_pct': f'laptime_pct_{first_code}',
            'laptime_pct_alien': f'laptime_pct_alien_{first_code}'
        }
    ).copy()
    
    pace_cols = [f'laptime_pct_alien_{first_code}']
    
    # Merge remaining races
    for code in race_codes[1:]:
        track_name = code_to_track[code]
        if track_name in dfs_dict:
            comparison_df = comparison_df.merge(
                dfs_dict[track_name][['Driver_name', 'laptime_sec', 'laptime_pct', 'laptime_pct_alien']].rename(
                    columns={
                        'laptime_sec': f'laptime_sec_{code}',
                        'laptime_pct': f'laptime_pct_{code}',
                        'laptime_pct_alien': f'laptime_pct_alien_{code}'
                    }
                ),
                on='Driver_name',
                how='outer'
            )
            pace_cols.append(f'laptime_pct_alien_{code}')
    
    # Clean up
    comparison_df = comparison_df.replace(0.00, np.nan).dropna(subset=pace_cols, how='all')
    # Replace any entries over 107% with NaN to filter out outliers
    for col in pace_cols:
        comparison_df[col] = comparison_df[col].apply(lambda x: x if pd.isna(x) or x <= 107.0 else np.nan)
    comparison_df = comparison_df.sort_values('Driver_name').reset_index(drop=True)
    
    return comparison_df, pace_cols


def build_improvement_df(comparison_df, pace_cols):
    """Build improvement dataframe from comparison df"""
    improvement_df = comparison_df[['Driver_name'] + pace_cols].copy()
    improvement_df = improvement_df.replace(0.00, np.nan).dropna(subset=pace_cols, how='all')
    
    # Calculate improvement only if we have at least 2 races
    if len(pace_cols) >= 2:
        improvement_df['best_first_two'] = improvement_df[pace_cols[:2]].min(axis=1)
        improvement_df['best_last_two'] = improvement_df[pace_cols[-2:]].min(axis=1)
        improvement_df['improvement'] = improvement_df['best_first_two'] - improvement_df['best_last_two']
        improvement_df = improvement_df.sort_values('improvement', ascending=False)
    
    return improvement_df


def create_display_df(comparison_df, pace_cols, track_names, mode='race'):
    """Create display dataframe with renamed columns"""
    display_df = comparison_df[['Driver_name'] + pace_cols].copy()
    display_df = display_df.replace(0.00, np.nan).dropna(subset=pace_cols, how='all')
    display_df['best_pct'] = display_df[pace_cols].min(axis=1)
    display_df = display_df.sort_values('best_pct')
    
    # Build rename mapping
    rename_map = {'Driver_name': 'Driver_name'}
    for i, (col, track) in enumerate(zip(pace_cols, track_names)):
        pace_type = 'Race' if mode == 'race' else 'Quali'
        rename_map[col] = f'{track} {pace_type} Pace % (vs Alien)'
    
    display_df_renamed = display_df.rename(columns=rename_map)
    return display_df_renamed, list(rename_map.values())[1:]  # Return column names minus Driver_name


def generate_html_tables(comparison_df, improvement_df, track_names):
    """Generate HTML table representations of dataframes with dynamic track names"""
    # Pace vs Alien table
    pace_cols = [col for col in comparison_df.columns if col.startswith('laptime_pct_alien_')]
    
    pace_table_df = comparison_df[['Driver_name'] + pace_cols].copy()
    
    # Convert driver names to "F. Lastname" format for space efficiency
    pace_table_df['Driver_name'] = pace_table_df['Driver_name'].apply(
        lambda x: f"{x.split()[0][0]}. {' '.join(x.split()[1:])}" if len(x.split()) > 1 else x
    )
    
    # Build rename mapping for pace table
    pace_rename = {'Driver_name': 'Driver'}
    for track, col in zip(track_names, pace_cols):
        pace_rename[col] = track
    
    pace_table_df = pace_table_df.rename(columns=pace_rename).dropna(subset=track_names, how='all')
    pace_html = pace_table_df.to_html(index=False, float_format=lambda x: f'{x:.2f}' if pd.notna(x) else '')
    
    # Improvement table
    improvement_cols = ['Driver_name', 'best_first_two', 'best_last_two', 'improvement']
    improvement_table_df = improvement_df[improvement_cols].dropna(subset=['improvement']).rename(columns={
        'Driver_name': 'Driver',
        'best_first_two': 'Best (First 2)',
        'best_last_two': 'Best (Last 2)',
        'improvement': 'Improvement'
    })
    
    improvement_html = improvement_table_df.to_html(index=False, float_format=lambda x: f'{x:.2f}' if pd.notna(x) else '')
    
    return pace_html, improvement_html


def create_plotly_json(df_display_renamed, track_names, chart_title, y_axis_title, time_lower=100.0, time_upper=107.0):
    """Create Plotly JSON data for the interactive chart with dynamic track names"""
    # Get pace columns from display df (excluding Driver_name and best_pct)
    pace_col_names = [col for col in df_display_renamed.columns if 'Pace %' in col]
    
    # Build column mapping from renamed columns back to track names
    col_mapping = {}
    for i, (track, col) in enumerate(zip(track_names, pace_col_names)):
        col_mapping[col] = track
    
    # Build plot_df
    plot_df = df_display_renamed[['Driver_name'] + pace_col_names].copy()
    plot_df.rename(columns=col_mapping, inplace=True)
    plot_df = plot_df[plot_df[plot_df.columns[-1]].between(time_lower, time_upper)].reset_index(drop=True)
    plot_df['best'] = plot_df[track_names].min(axis=1, skipna=True)
    plot_df = plot_df.sort_values('best').reset_index(drop=True)
    
    # Create traces for Plotly
    traces = []
    x_positions = list(range(len(track_names)))
    
    for idx, (_, row) in enumerate(plot_df.iterrows()):
        pts = []
        for xi, track in enumerate(track_names):
            val = row.get(track)
            if pd.notna(val):
                pts.append((xi, val))
        
        if not pts:
            continue
        
        xs, ys = list(zip(*pts))
        
        trace = {
            'x': xs,
            'y': ys,
            'mode': 'lines+markers',
            'name': row['Driver_name'],
            'hovertemplate': f"<b>{row['Driver_name']}</b><br>%{{customdata}}<br>Pace: %{{y:.2f}}%<extra></extra>",
            'customdata': [track_names[int(i)] for i in xs],
            'line': {'width': 2},
            'marker': {'size': 8}
        }
        traces.append(trace)
    
    return {
        'traces': traces,
        'layout': {
            'title': chart_title,
            'xaxis': {
                'tickmode': 'array',
                'ticktext': track_names,
                'tickvals': x_positions
            },
            'yaxis': {
                'title': y_axis_title,
                'range': [time_lower, time_upper]
            },
            'hovermode': 'closest',
            'plot_bgcolor': 'rgba(240, 240, 240, 0.5)',
            'height': 500,
            'autosize': True,
            'showlegend': False,
            'xaxis_range': [-0.6, len(track_names) - 1 + 0.6],
            'margin': {'l': 50, 'r': 20, 'b': 50, 't': 60}
        }
    }


def get_sidebar_html(active_page):
    """Generate sidebar navigation HTML"""
    nav_items = [
        ('sprint_race.html', 'Sprint', 'Race Pace'),
        ('sprint_quali.html', 'Sprint', 'Quali Pace'),
        ('multiclass_p2ur_race.html', 'Multiclass P2UR', 'Race Pace'),
        ('multiclass_p2ur_quali.html', 'Multiclass P2UR', 'Quali Pace'),
        ('multiclass_gt3_race.html', 'Multiclass GT3', 'Race Pace'),
        ('multiclass_gt3_quali.html', 'Multiclass GT3', 'Quali Pace'),
    ]
    
    sidebar_html = '<nav class="sidebar"><div class="sidebar-content"><h3>📊 Dashboard</h3>'
    
    current_section = None
    for file_name, section, subsection in nav_items:
        if section != current_section:
            if current_section is not None:
                sidebar_html += '</ul></div>'
            current_section = section
            sidebar_html += f'<div class="section-group"><h4>{section}</h4><ul>'
        
        is_active = 'active' if file_name == active_page else ''
        sidebar_html += f'<li><a href="{file_name}" class="{is_active}">{subsection}</a></li>'
    
    sidebar_html += '</ul></div></nav>'
    return sidebar_html


def get_css_styles():
    """Return shared CSS styles for all pages"""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #14161ff2;
            color: #333;
            line-height: 0.5;
            padding: 20px;
            display: flex;
        }
        
        .main-wrapper {
            display: flex;
            width: 100%;
            gap: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .sidebar {
            width: 250px;
            background: black;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 20px;
            height: fit-content;
            position: sticky;
            top: 20px;
        }
        
        .sidebar-toggle {
            display: none;
            flex-direction: column;
            cursor: pointer;
            padding: 10px;
            background: none;
            border: none;
        }
        
        .sidebar-toggle span {
            width: 25px;
            height: 3px;
            background: #667eea;
            margin: 5px 0;
            transition: 0.3s;
        }
        
        .sidebar-content h3 {
            color: #ccfc00;
            margin-bottom: 20px;
            font-size: 1.2em;
        }
        
        .section-group {
            margin-bottom: 20px;
        }
        
        .section-group h4 {
            color: #ccfc00;
            font-size: 0.95em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .section-group ul {
            list-style: none;
        }
        
        .section-group li {
            margin-bottom: 8px;
        }
        
        .section-group a {
            color: white;
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 5px;
            display: block;
            transition: all 0.3s ease;
            font-size: 0.95em;
        }
        
        .section-group a:hover {
            background: #512f89;
            color: #ccfc00;
        }
        
        .section-group a.active {
            background: #512f89;
            color: #ccfc00;
            font-weight: 600;
        }
        
        .container {
            flex: 1;
            background: transparent;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        header {
            background: transparent;
            color: #ccfc00;
            padding: 30px 20px;
            text-align: center;
        }
        
        header h1 {
            font-size: 3em;
        }
        
        header p {
            font-size: 1em;
            opacity: 0.9;
        }
        
        .header-logo {
            width: 250px;
            height: 250px;
            object-fit: contain;
            display: block;
            margin: 0 auto 20px;
        }
        
        .content {
            padding: 30px 20px;
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section h2 {
            color: #ccfc00;
            font-size: 1.6em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid gray;
        }
        
        .chart-container {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            width: 100%;
            overflow-x: auto;
        }
        
        .chart-container > div {
            width: 100% !important;
            height: 500px !important;
        }
        
        .table-container {
            overflow-x: auto;
            background: #14161ff2;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95em;
        }
        
        table thead {
            background: #14161ff2;
            color: white;
        }
        
        table th {
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        
        table td {
            color: white;
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        table tbody tr:hover {
            background: #e8eaf6;
        }
        
        table tbody tr:nth-child(even) {
            background: gray;
        }
        
        .footer {
            background: transparent;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #e0e0e0;
        }
        
        @media (max-width: 1024px) {
            .main-wrapper {
                flex-direction: column;
            }
            
            .sidebar {
                width: 100%;
                position: static;
                max-height: none;
            }
            
            header h1 {
                font-size: 2em;
            }
            
            .header-logo {
                width: 200px;
                height: 200px;
            }
            
            table {
                font-size: 0.85em;
            }
            
            table th, table td {
                padding: 8px;
            }
        }
        
        @media (max-width: 768px) {
            body {
                padding: 12px;
            }
            
            .main-wrapper {
                gap: 12px;
            }
            
            .sidebar {
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.3s ease;
            }
            
            .sidebar.active {
                max-height: 600px;
            }
            
            .sidebar-toggle {
                display: flex;
            }
            
            header {
                padding: 20px 15px;
            }
            
            header h1 {
                font-size: 1.5em;
                margin-bottom: 5px;
            }
            
            header p {
                font-size: 0.9em;
            }
            
            .header-logo {
                width: 150px;
                height: 150px;
                margin-bottom: 15px;
            }
            
            .content {
                padding: 20px 15px;
            }
            
            .section h2 {
                font-size: 1.3em;
                margin-bottom: 15px;
            }
            
            .chart-container {
                padding: 15px;
                margin-bottom: 20px;
            }
            
            .table-container {
                padding: 15px;
                margin-bottom: 20px;
            }
            
            table {
                font-size: 0.75em;
            }
            
            table th, table td {
                padding: 6px;
            }
            
            .sidebar-content h3 {
                font-size: 1em;
            }
            
            .section-group a {
                font-size: 0.85em;
                padding: 6px 10px;
            }
        }
        
        @media (max-width: 480px) {
            body {
                padding: 8px;
            }
            
            .main-wrapper {
                gap: 8px;
            }
            
            header {
                color: #ccfc00;
                padding: 15px 10px;
                border-radius: 8px 8px 0 0;
            }
            
            header h1 {
                color: #ccfc00;
                font-size: 1.1em;
                margin-bottom: 3px;
            }
            
            header p {
                font-size: 0.8em;
            }
            
            .header-logo {
                width: 100px;
                height: 100px;
                margin-bottom: 10px;
            }
            
            .container {
                border-radius: 8px;
            }
            
            .content {
                padding: 15px 10px;
            }
            
            .section {
                margin-bottom: 25px;
            }
            
            .section h2 {
                color: #ccfc00;
                font-size: 1.1em;
                margin-bottom: 12px;
                padding-bottom: 8px;
            }
            
            .chart-container {
                padding: 10px;
                margin-bottom: 15px;
            }
            
            .table-container {
                padding: 10px;
                margin-bottom: 15px;
                overflow-x: auto;
            }
            
            table {
                font-size: 0.65em;
                min-width: 100%;
            }
            
            table th, table td {
                padding: 4px;
            }
            
            .sidebar-content h3 {
                font-size: 0.9em;
                margin-bottom: 15px;
            }
            
            .section-group h4 {
                font-size: 0.75em;
                margin-bottom: 8px;
            }
            
            .section-group a {
                font-size: 0.75em;
                padding: 5px 8px;
                margin-bottom: 5px;
            }
            
            .footer {
                background: transparent;
                padding: 15px 10px;
                font-size: 0.75em;
            }
        }
    """


def generate_page(title, subtitle, sidebar_file, pace_html, improvement_html, plotly_data):
    """Generate an HTML page with sidebar"""
    sidebar = get_sidebar_html(sidebar_file)
    css = get_css_styles()
    
    # Create sidebar HTML with toggle button
    sidebar_section = f"""
    <button class="sidebar-toggle" id="sidebarToggle" aria-label="Toggle menu">
        <span></span>
        <span></span>
        <span></span>
    </button>
    {sidebar}
    """
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>{css}</style>
</head>
<body>
    <div class="main-wrapper">
        {sidebar_section}
        <div class="container">
            <header>
                <img src="logo.png" alt="Logo" class="header-logo">
                <h1>{title}</h1>
            </header>
            
            <div class="content">
                <!-- Pace Trend Chart -->
                <div class="section">
                    <h2>Pace Trend by Round</h2>
                    <div class="chart-container">
                        <div id="paceChart" style="width:100%;"></div>
                    </div>
                </div>
                
                <!-- Pace vs Alien Table -->
                <div class="section">
                    <h2>Pace vs Alien - All Rounds</h2>
                    <div class="table-container">
                        {pace_html}
                    </div>
                </div>
                
                <!-- Improvement Comparison -->
                <div class="section">
                    <h2>Driver Improvement Comparison</h2>
                    <div class="table-container">
                        {improvement_html}
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p>Generated from OOFS S3 XML Race Data</p>
                <p style="font-size: 0.9em; margin-top: 10px;">Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </div>
    
    <script>
        // Sidebar toggle functionality
        const sidebarToggle = document.getElementById('sidebarToggle');
        const sidebar = document.querySelector('.sidebar');
        
        if (sidebarToggle && sidebar) {{
            sidebarToggle.addEventListener('click', function() {{
                sidebar.classList.toggle('active');
            }});
            
            // Close sidebar when a link is clicked
            const sidebarLinks = sidebar.querySelectorAll('a');
            sidebarLinks.forEach(link => {{
                link.addEventListener('click', function() {{
                    sidebar.classList.remove('active');
                }});
            }});
        }}
        
        // Plotly chart initialization
        const plotData = {json.dumps(plotly_data['traces'])};
        const plotLayout = {json.dumps(plotly_data['layout'])};
        
        Plotly.newPlot('paceChart', plotData, plotLayout, {{responsive: true, displayModeBar: false}});
        
        // Handle responsive resizing
        window.addEventListener('resize', function() {{
            Plotly.Plots.resize('paceChart');
        }});
    </script>
</body>
</html>
"""


def main():
    """Main execution function"""
    print("Processing XML race data...\n")
    
    # Create docs folder
    os.makedirs('docs', exist_ok=True)
    
    # ===== SPRINT RACE PACE =====
    print("Processing Sprint Race Pace...")
    race_dfs = {}
    for filename, race_info in SPRINT_RACES.items():
        xml_path = os.path.join('xml/sprint', filename)
        if os.path.exists(xml_path):
            df = process_race_data(xml_path, race_info['name'], race_info['ref_time'])
            if df is not None:
                race_dfs[race_info['name']] = df
                print(f"  ✓ Loaded {race_info['name']}")
        else:
            print(f"  ✗ File not found: {xml_path}")
    
    if race_dfs:
        # Get dynamic race codes and track names
        race_codes, track_names, code_to_track = load_races_dynamically(SPRINT_RACES, 'xml/sprint')
        
        # Build comparison dataframe dynamically
        comparison_df, pace_cols = process_races_into_comparison_df(race_dfs, race_codes, code_to_track)
        
        if comparison_df is not None:
            improvement_df = build_improvement_df(comparison_df, pace_cols)
            df_display_renamed, display_col_names = create_display_df(comparison_df, pace_cols, track_names, mode='race')
            
            pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df, track_names)
            
            num_rounds = len(track_names)
            plotly_data = create_plotly_json(
                df_display_renamed, 
                track_names, 
                f'Sprint Race Pace Trend: After {num_rounds} Rounds',
                'Race Pace % (vs Alien)'
            )
            
            html_content = generate_page(
                '🏁 Sprint Race Pace Data',
                f'Performance Analysis Across {num_rounds} Championship Rounds',
                'sprint_race.html',
                pace_html,
                improvement_html,
                plotly_data
            )
            
            with open('docs/sprint_race.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content)
            with open('docs/index.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content)
            
            print("  ✓ Generated Sprint Race Pace page\n")
    
    # ===== SPRINT QUALI PACE =====
    print("Processing Sprint Quali Pace...")
    quali_dfs = {}
    for filename, quali_info in SPRINT_QUALIS.items():
        xml_path = os.path.join('xml/sprint', filename)
        if os.path.exists(xml_path):
            df = process_race_data(xml_path, quali_info['name'], quali_info['ref_time'])
            if df is not None:
                quali_dfs[quali_info['name']] = df
                print(f"  ✓ Loaded {quali_info['name']}")
        else:
            print(f"  ✗ File not found: {xml_path}")
    
    if quali_dfs:
        # Get dynamic race codes and track names
        quali_codes, quali_track_names, quali_code_to_track = load_races_dynamically(SPRINT_QUALIS, 'xml/sprint')
        
        # Build comparison dataframe dynamically
        comparison_df_quali, pace_cols_quali = process_races_into_comparison_df(quali_dfs, quali_codes, quali_code_to_track)
        
        if comparison_df_quali is not None:
            improvement_df_quali = build_improvement_df(comparison_df_quali, pace_cols_quali)
            df_quali_display_renamed, _ = create_display_df(comparison_df_quali, pace_cols_quali, quali_track_names, mode='quali')
            
            pace_html_quali, improvement_html_quali = generate_html_tables(comparison_df_quali, improvement_df_quali, quali_track_names)
            
            num_rounds_quali = len(quali_track_names)
            plotly_data_quali = create_plotly_json(
                df_quali_display_renamed,
                quali_track_names,
                f'Sprint Quali Pace Trend: After {num_rounds_quali} Rounds',
                'Quali Pace % (vs Alien)'
            )
            
            html_content_quali = generate_page(
                '🏁 Sprint Quali Pace Data',
                f'Qualification Performance Analysis Across {num_rounds_quali} Championship Rounds',
                'sprint_quali.html',
                pace_html_quali,
                improvement_html_quali,
                plotly_data_quali
            )
            
            with open('docs/sprint_quali.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content_quali)
            
            print("  ✓ Generated Sprint Quali Pace page\n")
    
    # ===== MULTICLASS P2UR RACE PACE =====
    print("Processing Multiclass P2UR Race Pace...")
    mc_p2ur_race_dfs = {}
    for filename, mc_info in MULTICLASS_RACES.items():
        xml_path = os.path.join('xml/multiclass', filename)
        if os.path.exists(xml_path):
            df = process_multiclass_race_data(xml_path, mc_info['name'], 'P2UR', mc_info['ref_time_p2ur'])
            if df is not None:
                mc_p2ur_race_dfs[mc_info['name']] = df
                print(f"  ✓ Loaded {mc_info['name']}")
        else:
            print(f"  ✗ File not found: {xml_path}")
    
    if mc_p2ur_race_dfs:
        # Get dynamic race codes and track names
        mc_codes, mc_track_names, mc_code_to_track = load_races_dynamically(MULTICLASS_RACES, 'xml/multiclass')
        
        # Build comparison dataframe dynamically
        comparison_df_mc_p2ur, pace_cols_mc_p2ur = process_races_into_comparison_df(mc_p2ur_race_dfs, mc_codes, mc_code_to_track)
        
        if comparison_df_mc_p2ur is not None:
            improvement_df_mc_p2ur = build_improvement_df(comparison_df_mc_p2ur, pace_cols_mc_p2ur)
            df_mc_p2ur_display_renamed, _ = create_display_df(comparison_df_mc_p2ur, pace_cols_mc_p2ur, mc_track_names, mode='race')
            
            pace_html_mc_p2ur, improvement_html_mc_p2ur = generate_html_tables(comparison_df_mc_p2ur, improvement_df_mc_p2ur, mc_track_names)
            
            num_rounds_mc = len(mc_track_names)
            plotly_data_mc_p2ur = create_plotly_json(
                df_mc_p2ur_display_renamed,
                mc_track_names,
                f'Multiclass P2UR Race Pace Trend: After {num_rounds_mc} Rounds',
                'Race Pace % (vs Alien)'
            )
            
            html_content_mc_p2ur = generate_page(
                '🏆 Multiclass P2UR Race Pace Data',
                f'P2UR Race Performance Analysis Across {num_rounds_mc} Championship Rounds',
                'multiclass_p2ur_race.html',
                pace_html_mc_p2ur,
                improvement_html_mc_p2ur,
                plotly_data_mc_p2ur
            )
            
            with open('docs/multiclass_p2ur_race.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content_mc_p2ur)
            
            print("  ✓ Generated Multiclass P2UR Race Pace page\n")
    
    # ===== MULTICLASS P2UR QUALI PACE =====
    print("Processing Multiclass P2UR Quali Pace...")
    mc_p2ur_quali_dfs = {}
    for filename, mc_info in MULTICLASS_QUALIS.items():
        xml_path = os.path.join('xml/multiclass', filename)
        if os.path.exists(xml_path):
            df = process_multiclass_race_data(xml_path, mc_info['name'], 'P2UR', mc_info['ref_time_p2ur'])
            if df is not None:
                mc_p2ur_quali_dfs[mc_info['name']] = df
                print(f"  ✓ Loaded {mc_info['name']}")
        else:
            print(f"  ✗ File not found: {xml_path}")
    
    if mc_p2ur_quali_dfs:
        # Get dynamic race codes and track names
        mc_quali_codes, mc_quali_track_names, mc_quali_code_to_track = load_races_dynamically(MULTICLASS_QUALIS, 'xml/multiclass')
        
        # Build comparison dataframe dynamically
        comparison_df_mc_p2ur_quali, pace_cols_mc_p2ur_quali = process_races_into_comparison_df(mc_p2ur_quali_dfs, mc_quali_codes, mc_quali_code_to_track)
        
        if comparison_df_mc_p2ur_quali is not None:
            improvement_df_mc_p2ur_quali = build_improvement_df(comparison_df_mc_p2ur_quali, pace_cols_mc_p2ur_quali)
            df_mc_p2ur_quali_display_renamed, _ = create_display_df(comparison_df_mc_p2ur_quali, pace_cols_mc_p2ur_quali, mc_quali_track_names, mode='quali')
            
            pace_html_mc_p2ur_quali, improvement_html_mc_p2ur_quali = generate_html_tables(comparison_df_mc_p2ur_quali, improvement_df_mc_p2ur_quali, mc_quali_track_names)
            
            num_rounds_mc_quali = len(mc_quali_track_names)
            plotly_data_mc_p2ur_quali = create_plotly_json(
                df_mc_p2ur_quali_display_renamed,
                mc_quali_track_names,
                f'Multiclass P2UR Quali Pace Trend: After {num_rounds_mc_quali} Rounds',
                'Quali Pace % (vs Alien)'
            )
            
            html_content_mc_p2ur_quali = generate_page(
                '🏆 Multiclass P2UR Quali Pace Data',
                f'P2UR Qualification Performance Analysis Across {num_rounds_mc_quali} Championship Rounds',
                'multiclass_p2ur_quali.html',
                pace_html_mc_p2ur_quali,
                improvement_html_mc_p2ur_quali,
                plotly_data_mc_p2ur_quali
            )
            
            with open('docs/multiclass_p2ur_quali.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content_mc_p2ur_quali)
            
            print("  ✓ Generated Multiclass P2UR Quali Pace page\n")
    
    # ===== MULTICLASS GT3 RACE PACE =====
    print("Processing Multiclass GT3 Race Pace...")
    mc_gt3_race_dfs = {}
    for filename, mc_info in MULTICLASS_RACES.items():
        xml_path = os.path.join('xml/multiclass', filename)
        if os.path.exists(xml_path):
            df = process_multiclass_race_data(xml_path, mc_info['name'], 'GT3', mc_info['ref_time_gt3'])
            if df is not None:
                mc_gt3_race_dfs[mc_info['name']] = df
                print(f"  ✓ Loaded {mc_info['name']}")
        else:
            print(f"  ✗ File not found: {xml_path}")
    
    if mc_gt3_race_dfs:
        # Get dynamic race codes and track names
        mc_gt3_codes, mc_gt3_track_names, mc_gt3_code_to_track = load_races_dynamically(MULTICLASS_RACES, 'xml/multiclass')
        
        # Build comparison dataframe dynamically
        comparison_df_mc_gt3, pace_cols_mc_gt3 = process_races_into_comparison_df(mc_gt3_race_dfs, mc_gt3_codes, mc_gt3_code_to_track)
        
        if comparison_df_mc_gt3 is not None:
            improvement_df_mc_gt3 = build_improvement_df(comparison_df_mc_gt3, pace_cols_mc_gt3)
            df_mc_gt3_display_renamed, _ = create_display_df(comparison_df_mc_gt3, pace_cols_mc_gt3, mc_gt3_track_names, mode='race')
            
            pace_html_mc_gt3, improvement_html_mc_gt3 = generate_html_tables(comparison_df_mc_gt3, improvement_df_mc_gt3, mc_gt3_track_names)
            
            num_rounds_mc_gt3 = len(mc_gt3_track_names)
            plotly_data_mc_gt3 = create_plotly_json(
                df_mc_gt3_display_renamed,
                mc_gt3_track_names,
                f'Multiclass GT3 Race Pace Trend: After {num_rounds_mc_gt3} Rounds',
                'Race Pace % (vs Alien)'
            )
            
            html_content_mc_gt3 = generate_page(
                '🏆 Multiclass GT3 Race Pace Data',
                f'GT3 Race Performance Analysis Across {num_rounds_mc_gt3} Championship Rounds',
                'multiclass_gt3_race.html',
                pace_html_mc_gt3,
                improvement_html_mc_gt3,
                plotly_data_mc_gt3
            )
            
            with open('docs/multiclass_gt3_race.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content_mc_gt3)
            
            print("  ✓ Generated Multiclass GT3 Race Pace page\n")
    
    # ===== MULTICLASS GT3 QUALI PACE =====
    print("Processing Multiclass GT3 Quali Pace...")
    mc_gt3_quali_dfs = {}
    for filename, mc_info in MULTICLASS_QUALIS.items():
        xml_path = os.path.join('xml/multiclass', filename)
        if os.path.exists(xml_path):
            df = process_multiclass_race_data(xml_path, mc_info['name'], 'GT3', mc_info['ref_time_gt3'])
            if df is not None:
                mc_gt3_quali_dfs[mc_info['name']] = df
                print(f"  ✓ Loaded {mc_info['name']}")
        else:
            print(f"  ✗ File not found: {xml_path}")
    
    if mc_gt3_quali_dfs:
        # Get dynamic race codes and track names
        mc_gt3_quali_codes, mc_gt3_quali_track_names, mc_gt3_quali_code_to_track = load_races_dynamically(MULTICLASS_QUALIS, 'xml/multiclass')
        
        # Build comparison dataframe dynamically
        comparison_df_mc_gt3_quali, pace_cols_mc_gt3_quali = process_races_into_comparison_df(mc_gt3_quali_dfs, mc_gt3_quali_codes, mc_gt3_quali_code_to_track)
        
        if comparison_df_mc_gt3_quali is not None:
            improvement_df_mc_gt3_quali = build_improvement_df(comparison_df_mc_gt3_quali, pace_cols_mc_gt3_quali)
            df_mc_gt3_quali_display_renamed, _ = create_display_df(comparison_df_mc_gt3_quali, pace_cols_mc_gt3_quali, mc_gt3_quali_track_names, mode='quali')
            
            pace_html_mc_gt3_quali, improvement_html_mc_gt3_quali = generate_html_tables(comparison_df_mc_gt3_quali, improvement_df_mc_gt3_quali, mc_gt3_quali_track_names)
            
            num_rounds_mc_gt3_quali = len(mc_gt3_quali_track_names)
            plotly_data_mc_gt3_quali = create_plotly_json(
                df_mc_gt3_quali_display_renamed,
                mc_gt3_quali_track_names,
                f'Multiclass GT3 Quali Pace Trend: After {num_rounds_mc_gt3_quali} Rounds',
                'Quali Pace % (vs Alien)'
            )
            
            html_content_mc_gt3_quali = generate_page(
                '🏆 Multiclass GT3 Quali Pace Data',
                f'GT3 Qualification Performance Analysis Across {num_rounds_mc_gt3_quali} Championship Rounds',
                'multiclass_gt3_quali.html',
                pace_html_mc_gt3_quali,
                improvement_html_mc_gt3_quali,
                plotly_data_mc_gt3_quali
            )
            
            with open('docs/multiclass_gt3_quali.html', 'w', encoding='utf-8-sig') as f:
                f.write(html_content_mc_gt3_quali)
            
            print("  ✓ Generated Multiclass GT3 Quali Pace page\n")
    
    print("\n✓ All pages generated successfully!")
    print("\nTo publish on GitHub Pages:")
    print("1. Commit and push changes to GitHub")
    print("2. Go to repository Settings > Pages")
    print("3. Select 'Deploy from a branch'")
    print("4. Choose 'main' branch and '/docs' folder")
    print("5. Your page will be published at: https://nitin95.github.io/oofs_s3_data_analytics/")


if __name__ == '__main__':
    main()
