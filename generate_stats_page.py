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
SPRINT_RACES = {
    's3-sc1-r.xml': {'name': 'Portimao', 'ref_time': 103.14},
    's3-sc2-r.xml': {'name': 'Le Mans', 'ref_time': 235.31},
    's3-sc3-r.xml': {'name': 'Interlagos', 'ref_time': 93.65},
    's3-sc4-r.xml': {'name': 'Monza', 'ref_time': 99.01},
    's3-sc5-r.xml': {'name': 'Sebring', 'ref_time': 120.17},
}

MULTICLASS_RACES = {
    's3-mc1.xml': {'name': 'Round 1', 'ref_time_p2ur': 242.50, 'ref_time_gt3': 281.30},
    's3-mc2.xml': {'name': 'Round 2', 'ref_time_p2ur': 245.80, 'ref_time_gt3': 284.60},
    's3-mc3.xml': {'name': 'Round 3', 'ref_time_p2ur': 241.90, 'ref_time_gt3': 279.40},
    's3-mc4.xml': {'name': 'Round 4', 'ref_time_p2ur': 246.20, 'ref_time_gt3': 285.10},
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


def generate_html_tables(comparison_df, improvement_df_2):
    """Generate HTML table representations of dataframes"""
    # Pace vs Alien table
    pace_cols = ['Driver_name', 'laptime_pct_alien_sc1', 'laptime_pct_alien_sc2', 
                 'laptime_pct_alien_sc3', 'laptime_pct_alien_sc4', 'laptime_pct_alien_sc5', 'time_diff_pct']
    pace_table_df = comparison_df[pace_cols].rename(columns={
        'Driver_name': 'Driver',
        'laptime_pct_alien_sc1': 'Portimao',
        'laptime_pct_alien_sc2': 'Le Mans',
        'laptime_pct_alien_sc3': 'Interlagos',
        'laptime_pct_alien_sc4': 'Monza',
        'laptime_pct_alien_sc5': 'Sebring',
        'time_diff_pct': 'Diff'
    }).dropna(subset=['Portimao', 'Le Mans', 'Interlagos', 'Monza', 'Sebring'], how='all')
    
    pace_html = pace_table_df.to_html(index=False, float_format=lambda x: f'{x:.2f}' if pd.notna(x) else '')
    
    # Improvement table
    improvement_cols = ['Driver_name', 'best_first_two', 'best_last_two', 'improvement']
    improvement_table_df = improvement_df_2[improvement_cols].dropna(subset=['improvement']).rename(columns={
        'Driver_name': 'Driver',
        'best_first_two': 'Best (First 2)',
        'best_last_two': 'Best (Last 2)',
        'improvement': 'Improvement'
    })
    
    improvement_html = improvement_table_df.to_html(index=False, float_format=lambda x: f'{x:.2f}' if pd.notna(x) else '')
    
    return pace_html, improvement_html


def create_plotly_json(df2, time_lower=100.0, time_upper=107.0):
    """Create Plotly JSON data for the interactive chart"""
    track_cols = ['Portimao', 'Le Mans', 'Interlagos', 'Monza', 'Sebring']
    col_mapping = {
        'Portimao Race Pace % (vs Alien)': 'Portimao',
        'Le Mans Race Pace % (vs Alien)': 'Le Mans',
        'Interlagos Race Pace % (vs Alien)': 'Interlagos',
        'Monza Race Pace % (vs Alien)': 'Monza',
        'Sebring Race Pace % (vs Alien)': 'Sebring'
    }
    
    # Build plot_df
    plot_df = df2[['Driver_name'] + list(col_mapping.keys())].copy()
    plot_df.rename(columns=col_mapping, inplace=True)
    plot_df = plot_df[plot_df[plot_df.columns[-1]].between(time_lower, time_upper)].reset_index(drop=True)
    plot_df['best'] = plot_df[track_cols].min(axis=1, skipna=True)
    plot_df = plot_df.sort_values('best').reset_index(drop=True)
    
    # Create traces for Plotly
    traces = []
    x_positions = list(range(len(track_cols)))
    
    for idx, (_, row) in enumerate(plot_df.iterrows()):
        pts = []
        for xi, col in enumerate(track_cols):
            val = row.get(col)
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
            'customdata': [track_cols[int(i)] for i in xs],
            'line': {'width': 2},
            'marker': {'size': 8}
        }
        traces.append(trace)
    
    return {
        'traces': traces,
        'layout': {
            'title': 'Sprint Race Pace Trend: After 5 Rounds',
            'xaxis': {
                'tickmode': 'linear',
                'tick0': 0,
                'dtick': 1,
                'ticktext': track_cols,
                'tickvals': x_positions
            },
            'yaxis': {
                'title': 'Race Pace % (vs Alien)',
                'range': [time_lower, time_upper]
            },
            'hovermode': 'closest',
            'plot_bgcolor': 'rgba(240, 240, 240, 0.5)',
            'height': 700,
            'width': 1000,
            'showlegend': False,
            'xaxis_range': [-0.6, len(track_cols) - 1 + 0.6]
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
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
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 20px;
            height: fit-content;
            position: sticky;
            top: 20px;
        }
        
        .sidebar-content h3 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.2em;
        }
        
        .section-group {
            margin-bottom: 20px;
        }
        
        .section-group h4 {
            color: #764ba2;
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
            color: #555;
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 5px;
            display: block;
            transition: all 0.3s ease;
            font-size: 0.95em;
        }
        
        .section-group a:hover {
            background: #f0f0f0;
            color: #667eea;
        }
        
        .section-group a.active {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        
        .container {
            flex: 1;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }
        
        header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        header p {
            font-size: 1em;
            opacity: 0.9;
        }
        
        .content {
            padding: 30px 20px;
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section h2 {
            color: #667eea;
            font-size: 1.6em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        
        .chart-container {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        .table-container {
            overflow-x: auto;
            background: #f8f9fa;
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
            background: #667eea;
            color: white;
        }
        
        table th {
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        
        table td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        table tbody tr:hover {
            background: #e8eaf6;
        }
        
        table tbody tr:nth-child(even) {
            background: #f5f5f5;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #e0e0e0;
        }
        
        @media (max-width: 968px) {
            .main-wrapper {
                flex-direction: column;
            }
            
            .sidebar {
                width: 100%;
                position: static;
            }
            
            header h1 {
                font-size: 1.6em;
            }
            
            table {
                font-size: 0.85em;
            }
            
            table th, table td {
                padding: 8px;
            }
        }
    """


def generate_page(title, subtitle, sidebar_file, pace_html, improvement_html, plotly_data):
    """Generate an HTML page with sidebar"""
    sidebar = get_sidebar_html(sidebar_file)
    css = get_css_styles()
    
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
        {sidebar}
        <div class="container">
            <header>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </header>
            
            <div class="content">
                <!-- Pace Trend Chart -->
                <div class="section">
                    <h2>Pace Trend by Round</h2>
                    <div class="chart-container">
                        <div id="paceChart" style="width:100%;height:700px;"></div>
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
                    <p>Performance comparison across rounds</p>
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
        const plotData = {json.dumps(plotly_data['traces'])};
        const plotLayout = {json.dumps(plotly_data['layout'])};
        
        Plotly.newPlot('paceChart', plotData, plotLayout, {{responsive: true}});
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
        # Create comparison dataframe
        comparison_df = race_dfs['Portimao'][['Driver_name', 'laptime_sec', 'laptime_pct', 'laptime_pct_alien']].rename(
            columns={
                'laptime_sec': 'laptime_sec_sc1',
                'laptime_pct': 'laptime_pct_sc1',
                'laptime_pct_alien': 'laptime_pct_alien_sc1'
            }
        ).copy()
        
        race_order = ['Le Mans', 'Interlagos', 'Monza', 'Sebring']
        race_codes = ['sc2', 'sc3', 'sc4', 'sc5']
        
        for race_name, race_code in zip(race_order, race_codes):
            if race_name in race_dfs:
                comparison_df = comparison_df.merge(
                    race_dfs[race_name][['Driver_name', 'laptime_sec', 'laptime_pct', 'laptime_pct_alien']].rename(
                        columns={
                            'laptime_sec': f'laptime_sec_{race_code}',
                            'laptime_pct': f'laptime_pct_{race_code}',
                            'laptime_pct_alien': f'laptime_pct_alien_{race_code}'
                        }
                    ),
                    on='Driver_name',
                    how='outer'
                )
        
        comparison_df['time_diff_pct'] = comparison_df['laptime_pct_alien_sc1'] - comparison_df['laptime_pct_alien_sc5']
        comparison_df = comparison_df.sort_values('Driver_name').reset_index(drop=True)
        
        # Improvement dataframe
        improvement_df_2 = comparison_df[['Driver_name', 'laptime_pct_alien_sc1', 'laptime_pct_alien_sc2', 
                                           'laptime_pct_alien_sc3', 'laptime_pct_alien_sc4', 'laptime_pct_alien_sc5']].copy()
        improvement_df_2 = improvement_df_2.replace(0.00, np.nan).dropna(subset=['laptime_pct_alien_sc1', 'laptime_pct_alien_sc2', 
                                                                                   'laptime_pct_alien_sc3', 'laptime_pct_alien_sc4', 
                                                                                   'laptime_pct_alien_sc5'], how='all')
        improvement_df_2['best_first_two'] = improvement_df_2[['laptime_pct_alien_sc1', 'laptime_pct_alien_sc2']].min(axis=1)
        improvement_df_2['best_last_two'] = improvement_df_2[['laptime_pct_alien_sc4', 'laptime_pct_alien_sc5']].min(axis=1)
        improvement_df_2['improvement'] = improvement_df_2['best_first_two'] - improvement_df_2['best_last_two']
        improvement_df_2 = improvement_df_2.sort_values('improvement', ascending=False)
        
        # Display dataframe
        df2_display = comparison_df[['Driver_name', 'laptime_pct_alien_sc1', 'laptime_pct_alien_sc2', 
                                     'laptime_pct_alien_sc3', 'laptime_pct_alien_sc4', 'laptime_pct_alien_sc5', 'time_diff_pct']].copy()
        df2_display = df2_display.replace(0.00, np.nan).dropna(subset=['laptime_pct_alien_sc1', 'laptime_pct_alien_sc2', 
                                                                        'laptime_pct_alien_sc3', 'laptime_pct_alien_sc4', 
                                                                        'laptime_pct_alien_sc5'], how='all')
        df2_display['best_pct'] = df2_display[['laptime_pct_alien_sc1', 'laptime_pct_alien_sc2', 
                                                'laptime_pct_alien_sc3', 'laptime_pct_alien_sc4', 
                                                'laptime_pct_alien_sc5']].min(axis=1)
        df2_display = df2_display.sort_values('best_pct')
        
        # Create renamed columns for display
        df2_display_renamed = df2_display.rename(columns={
            'laptime_pct_alien_sc1': 'Portimao Race Pace % (vs Alien)',
            'laptime_pct_alien_sc2': 'Le Mans Race Pace % (vs Alien)',
            'laptime_pct_alien_sc3': 'Interlagos Race Pace % (vs Alien)',
            'laptime_pct_alien_sc4': 'Monza Race Pace % (vs Alien)',
            'laptime_pct_alien_sc5': 'Sebring Race Pace % (vs Alien)',
        })
        
        pace_html, improvement_html = generate_html_tables(comparison_df, improvement_df_2)
        plotly_data = create_plotly_json(df2_display_renamed)
        
        html_content = generate_page(
            '🏁 Sprint Race Pace',
            'Performance Analysis Across 5 Championship Rounds',
            'sprint_race.html',
            pace_html,
            improvement_html,
            plotly_data
        )
        
        with open('docs/sprint_race.html', 'w') as f:
            f.write(html_content)
        with open('docs/index.html', 'w') as f:
            f.write(html_content)
        
        print("  ✓ Generated Sprint Race Pace page\n")
    
    # Generate stub pages for future data
    print("Generating stub pages for upcoming features...\n")
    
    stub_pages = [
        ('sprint_quali.html', '🏁 Sprint Quali Pace', 'Qualification Performance Across 5 Rounds'),
        ('multiclass_p2ur_race.html', '🏆 Multiclass P2UR Race Pace', 'P2UR Race Performance Analysis'),
        ('multiclass_p2ur_quali.html', '🏆 Multiclass P2UR Quali Pace', 'P2UR Qualification Performance'),
        ('multiclass_gt3_race.html', '🏆 Multiclass GT3 Race Pace', 'GT3 Race Performance Analysis'),
        ('multiclass_gt3_quali.html', '🏆 Multiclass GT3 Quali Pace', 'GT3 Qualification Performance'),
    ]
    
    for page_file, page_title, page_subtitle in stub_pages:
        stub_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>{get_css_styles()}</style>
</head>
<body>
    <div class="main-wrapper">
        {get_sidebar_html(page_file)}
        <div class="container">
            <header>
                <h1>{page_title}</h1>
                <p>{page_subtitle}</p>
            </header>
            
            <div class="content">
                <div class="section">
                    <h2>Coming Soon</h2>
                    <p style="font-size: 1.1em; color: #667eea; text-align: center; padding: 40px 20px;">
                        Data for this section is being prepared. Check back soon!
                    </p>
                </div>
            </div>
            
            <div class="footer">
                <p>Generated from OOFS S3 XML Race Data</p>
                <p style="font-size: 0.9em; margin-top: 10px;">Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        with open(f'docs/{page_file}', 'w') as f:
            f.write(stub_html)
        print(f"  ✓ Generated {page_title}")
    
    print("\n✓ All pages generated successfully!")
    print("\nTo publish on GitHub Pages:")
    print("1. Commit and push changes to GitHub")
    print("2. Go to repository Settings > Pages")
    print("3. Select 'Deploy from a branch'")
    print("4. Choose 'main' branch and '/docs' folder")
    print("5. Your page will be published at: https://nitin95.github.io/oofs_s3_data_analytics/")


if __name__ == '__main__':
    main()
