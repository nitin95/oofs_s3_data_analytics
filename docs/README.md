# Sprint Race Pace Statistics

This directory contains the GitHub Pages site for viewing Sprint race pace statistics.

## Overview

The `index.html` file is automatically generated from XML race data files located in the `xml/sprint/` folder. It displays:

- **Race Pace Trend**: Interactive Plotly chart showing pace progress across all 5 rounds
- **Pace vs Alien Data**: Comparison table of all drivers' lap times relative to the best fictional lap time (alien pace)
- **Driver Improvement Comparison**: Analysis showing which drivers improved the most between the first 2 rounds and last 2 rounds

## Updating the Page

To update the statistics with new race data:

1. Add or update XML files in the `xml/sprint/` folder
2. Update the race references in `generate_stats_page.py` if new races are added
3. Run the script: `python generate_stats_page.py`
4. Commit and push the updated `index.html` to the repository

The page will automatically update on your GitHub Pages site.

## Files

- `index.html` - The main GitHub Pages website (auto-generated)
- `.nojekyll` - Tells GitHub Pages to serve files as-is
- `README.md` - This file

## Technology Stack

- Python data processing (pandas, numpy)
- Plotly for interactive visualizations
- HTML/CSS for responsive design

## GitHub Pages Setup

To enable GitHub Pages for this repository:

1. Go to repository **Settings** > **Pages**
2. Select **Deploy from a branch**
3. Choose **main** branch and **/docs** folder
4. Your site will be published at: `https://<username>.github.io/<repo-name>/`

## Data Sources

Race data is parsed from XML files in the following format:
- `s3-sc1-r.xml` - Portimao (Reference time: 103.14s)
- `s3-sc2-r.xml` - Le Mans (Reference time: 235.31s)
- `s3-sc3-r.xml` - Interlagos (Reference time: 93.65s)
- `s3-sc4-r.xml` - Monza (Reference time: 99.01s)
- `s3-sc5-r.xml` - Sebring (Reference time: 120.17s)

The pace percentages are calculated relative to these reference lap times.
