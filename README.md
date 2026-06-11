# Healthcare Quality Dashboard

An interactive Python and Streamlit dashboard using public CMS hospital quality data to analyze hospital ratings, state-level trends, hospital type comparisons, and potential quality-improvement opportunities.

This project was built as a healthcare analytics portfolio project to demonstrate data cleaning, exploratory analysis, dashboard development, visualization, and stakeholder-facing communication.

## Project Overview

The dashboard currently analyzes CMS Hospital General Information data and allows users to explore hospital quality patterns by state, hospital type, ownership, and overall star rating.

The goal is to support clear, actionable review of healthcare quality data for project teams, analysts, and stakeholders interested in care delivery and quality improvement.

## Current Features

- Loads and cleans CMS Hospital General Information data
- Filters hospitals by state, hospital type, ownership, and minimum star rating
- Displays summary KPI cards for the filtered hospital population
- Visualizes the distribution of overall hospital ratings
- Compares average hospital ratings by state
- Compares hospital type performance
- Provides a searchable hospital detail table
- Allows users to download the filtered hospital table as a CSV

## Tech Stack

- Python
- pandas
- NumPy
- Streamlit
- Plotly

## Data Source

This project uses public hospital quality data from the CMS Provider Data Catalog.

Current dataset:

- Hospital General Information

The raw CMS CSV file is not included in this repository because public datasets may be large and are periodically updated by CMS.

To run the project locally, download the Hospital General Information CSV from the CMS Provider Data Catalog and save it here:

```text
data/raw/Hospital_General_Information.csv
```

## Project Structure

```text
healthcare-quality-dashboard/
  app.py
  requirements.txt
  README.md
  data/
    raw/
```

## Running Locally

Create and activate a virtual environment:

```bash
py -m venv .venv
source .venv/Scripts/activate
```

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

Run the dashboard:

```bash
streamlit run app.py
```

## Future Improvements

Planned next steps include:

- Add CMS HCAHPS patient experience data
- Add CMS unplanned hospital visits/readmission-related measures
- Create quality-improvement opportunity flags
- Add dashboard-style stakeholder insight summaries
- Add data dictionary and methodology documentation
- Add screenshots to the README
- Deploy the dashboard publicly using Streamlit Community Cloud

## Portfolio Relevance

This project demonstrates healthcare data analysis, data cleaning, dashboard development, visualization, stakeholder communication, and interpretation of public healthcare quality data.
