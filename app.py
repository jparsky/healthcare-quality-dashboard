import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Healthcare Quality Dashboard",
    page_icon="🏥",
    layout="wide",
)

HOSPITAL_GENERAL_INFO_PATH = "data/raw/Hospital_General_Information.csv"

HCAHPS_PATH = "data/raw/HCAHPS_Hospital.csv"

UNPLANNED_VISITS_URL = (
    "https://data.cms.gov/provider-data/sites/default/files/resources/"
    "hospital/Unplanned_Hospital_Visits-Hospital.csv"
)


@st.cache_data(show_spinner=True)
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)

def clean_rating(value):
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    if text.lower() in {
        "not available",
        "not applicable",
        "not enough information",
        "",
    }:
        return np.nan

    try:
        return float(text)
    except ValueError:
        return np.nan
    
    
def clean_percent(value):
    if pd.isna(value):
        return np.nan

    text = str(value).strip().replace("%", "")

    if text.lower() in {
        "not available",
        "not applicable",
        "not enough information",
        "",
    }:
        return np.nan

    try:
        return float(text)
    except ValueError:
        return np.nan

def load_and_clean_data():
    hospitals = load_csv(HOSPITAL_GENERAL_INFO_PATH)
    hcahps = load_csv(HCAHPS_PATH)

    hospitals.columns = hospitals.columns.str.strip()
    hcahps.columns = hcahps.columns.str.strip()

    hospitals["Hospital overall rating numeric"] = hospitals[
        "Hospital overall rating"
    ].apply(clean_rating)

    hospitals["State"] = hospitals["State"].str.strip()
    hospitals["Hospital Type"] = hospitals["Hospital Type"].str.strip()
    hospitals["Hospital Ownership"] = hospitals["Hospital Ownership"].str.strip()

    if "Patient Survey Star Rating" in hcahps.columns:
        hcahps["Patient Survey Star Rating Numeric"] = hcahps[
            "Patient Survey Star Rating"
        ].apply(clean_rating)

    if "HCAHPS Answer Percent" in hcahps.columns:
        hcahps["HCAHPS Answer Percent Numeric"] = hcahps[
            "HCAHPS Answer Percent"
        ].apply(clean_percent)

    if "State" in hcahps.columns:
        hcahps["State"] = hcahps["State"].str.strip()

    return hospitals, hcahps


def find_hcahps_summary(hcahps: pd.DataFrame) -> pd.DataFrame:
    """
    Pulls out HCAHPS rows that look like summary/star-rating rows.
    CMS data files can change slightly over time, so this uses flexible matching.
    """
    measure_col = "HCAHPS Measure ID"
    score_col = "Patient Survey Star Rating"

    if measure_col not in hcahps.columns or score_col not in hcahps.columns:
        return pd.DataFrame()

    summary = hcahps[
        hcahps[measure_col].str.contains("H_STAR_RATING", na=False)
    ].copy()

    summary["Patient survey star rating numeric"] = summary[score_col].apply(
        clean_rating
    )

    return summary


def find_readmission_rows(unplanned: pd.DataFrame) -> pd.DataFrame:
    """
    Pulls unplanned visit/readmission measures from the CMS unplanned visits file.
    """
    measure_name_col = "Measure Name"

    if measure_name_col not in unplanned.columns:
        return pd.DataFrame()

    readmissions = unplanned[
        unplanned[measure_name_col].str.contains(
            "readmission|unplanned", case=False, na=False
        )
    ].copy()

    if "Score" in readmissions.columns:
        readmissions["Score numeric"] = readmissions["Score"].apply(clean_rating)

    return readmissions


hospitals, hcahps = load_and_clean_data()
#hcahps_summary = find_hcahps_summary(hcahps)
#readmissions = find_readmission_rows(unplanned)

st.title("Healthcare Quality Dashboard")
st.caption(
    "CMS hospital quality analysis focused on overall ratings, patient experience, "
    "and unplanned visit/readmission-related measures."
)

with st.expander("About this dashboard", expanded=False):
    st.write(
        """
        This dashboard uses public CMS Provider Data Catalog hospital datasets to explore
        hospital quality patterns. It is designed as a stakeholder-facing analysis tool:
        users can filter hospitals, compare quality ratings, and identify areas that may
        warrant further quality-improvement review.
        """
    )

st.sidebar.header("Filters")

states = sorted(hospitals["State"].dropna().unique())
selected_states = st.sidebar.multiselect(
    "State",
    options=states,
    default=["DC"] if "DC" in states else states[:5],
)

hospital_types = sorted(hospitals["Hospital Type"].dropna().unique())
selected_types = st.sidebar.multiselect(
    "Hospital type",
    options=hospital_types,
    default=hospital_types,
)

ownership_types = sorted(hospitals["Hospital Ownership"].dropna().unique())
selected_ownership = st.sidebar.multiselect(
    "Hospital ownership",
    options=ownership_types,
    default=ownership_types,
)

min_rating = st.sidebar.slider(
    "Minimum overall star rating",
    min_value=1,
    max_value=5,
    value=1,
)

filtered_hospitals = hospitals.copy()

if selected_states:
    filtered_hospitals = filtered_hospitals[
        filtered_hospitals["State"].isin(selected_states)
    ]

if selected_types:
    filtered_hospitals = filtered_hospitals[
        filtered_hospitals["Hospital Type"].isin(selected_types)
    ]

if selected_ownership:
    filtered_hospitals = filtered_hospitals[
        filtered_hospitals["Hospital Ownership"].isin(selected_ownership)
    ]

filtered_hospitals = filtered_hospitals[
    filtered_hospitals["Hospital overall rating numeric"].isna()
    | (filtered_hospitals["Hospital overall rating numeric"] >= min_rating)
]

rated_hospitals = filtered_hospitals.dropna(
    subset=["Hospital overall rating numeric"]
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Hospitals shown", f"{len(filtered_hospitals):,}")
col2.metric("Hospitals with ratings", f"{len(rated_hospitals):,}")

avg_rating = rated_hospitals["Hospital overall rating numeric"].mean()
col3.metric(
    "Avg. overall rating",
    "N/A" if np.isnan(avg_rating) else f"{avg_rating:.2f}",
)

five_star_count = (
    rated_hospitals["Hospital overall rating numeric"].eq(5).sum()
)
col4.metric("5-star hospitals", f"{five_star_count:,}")

st.divider()

left, right = st.columns((1.1, 0.9))

with left:
    st.subheader("Distribution of Overall Hospital Ratings")

    if rated_hospitals.empty:
        st.info("No rated hospitals match the selected filters.")
    else:
        rating_counts = (
            rated_hospitals["Hospital overall rating numeric"]
            .value_counts()
            .sort_index()
            .reset_index()
        )
        rating_counts.columns = ["Overall rating", "Hospital count"]

        fig = px.bar(
            rating_counts,
            x="Overall rating",
            y="Hospital count",
            text="Hospital count",
            title="Hospital Count by Overall Star Rating",
        )
        fig.update_layout(xaxis=dict(dtick=1))
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Average Rating by State")

    if rated_hospitals.empty:
        st.info("No rated hospitals match the selected filters.")
    else:
        state_summary = (
            rated_hospitals.groupby("State", as_index=False)
            .agg(
                avg_rating=("Hospital overall rating numeric", "mean"),
                hospital_count=("Facility ID", "count"),
            )
            .sort_values("avg_rating", ascending=False)
        )

        fig = px.bar(
            state_summary,
            x="State",
            y="avg_rating",
            hover_data=["hospital_count"],
            title="Average Overall Rating by State",
        )
        fig.update_layout(yaxis_title="Average rating")
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Hospital Type Comparison")

if rated_hospitals.empty:
    st.info("No rated hospitals match the selected filters.")
else:
    type_summary = (
        rated_hospitals.groupby("Hospital Type", as_index=False)
        .agg(
            avg_rating=("Hospital overall rating numeric", "mean"),
            hospital_count=("Facility ID", "count"),
        )
        .sort_values("avg_rating", ascending=False)
    )

    fig = px.scatter(
        type_summary,
        x="hospital_count",
        y="avg_rating",
        size="hospital_count",
        hover_name="Hospital Type",
        title="Average Rating by Hospital Type and Number of Hospitals",
    )
    fig.update_layout(
        xaxis_title="Hospital count",
        yaxis_title="Average overall rating",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Patient Experience Snapshot")

required_hcahps_cols = {
    "Facility ID",
    "Facility Name",
    "State",
    "HCAHPS Measure ID",
    "HCAHPS Answer Description",
    "Patient Survey Star Rating Numeric",
}

missing_hcahps_cols = required_hcahps_cols - set(hcahps.columns)

if missing_hcahps_cols:
    st.warning(
        "The HCAHPS file loaded, but some expected columns were not found: "
        + ", ".join(sorted(missing_hcahps_cols))
    )

    with st.expander("Show HCAHPS columns found in this file"):
        st.write(list(hcahps.columns))

else:
    hcahps_filtered = hcahps.copy()

    if selected_states:
        hcahps_filtered = hcahps_filtered[
            hcahps_filtered["State"].isin(selected_states)
        ]

    # Keep rows that have a patient survey star rating.
    hcahps_rated = hcahps_filtered.dropna(
        subset=["Patient Survey Star Rating Numeric"]
    )

    if hcahps_rated.empty:
        st.info("No HCAHPS patient survey star rating data match the selected filters.")
    else:
        col_a, col_b, col_c = st.columns(3)

        avg_patient_rating = hcahps_rated[
            "Patient Survey Star Rating Numeric"
        ].mean()

        unique_hospitals_hcahps = hcahps_rated["Facility ID"].nunique()

        five_star_patient_count = (
            hcahps_rated["Patient Survey Star Rating Numeric"].eq(5).sum()
        )

        col_a.metric(
            "Avg. patient survey rating",
            f"{avg_patient_rating:.2f}",
        )
        col_b.metric(
            "Hospitals with HCAHPS ratings",
            f"{unique_hospitals_hcahps:,}",
        )
        col_c.metric(
            "5-star HCAHPS rows",
            f"{five_star_patient_count:,}",
        )

        patient_exp_by_state = (
            hcahps_rated.groupby("State", as_index=False)
            .agg(
                avg_patient_experience=(
                    "Patient Survey Star Rating Numeric",
                    "mean",
                ),
                hospital_count=("Facility ID", "nunique"),
            )
            .sort_values("avg_patient_experience", ascending=False)
        )

        fig = px.bar(
            patient_exp_by_state,
            x="State",
            y="avg_patient_experience",
            hover_data=["hospital_count"],
            title="Average HCAHPS Patient Survey Star Rating by State",
        )
        fig.update_layout(
            yaxis_title="Average patient survey star rating",
            xaxis_title="State",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.write("### Patient Experience Measures")

        measure_summary = (
            hcahps_rated.groupby("HCAHPS Answer Description", as_index=False)
            .agg(
                avg_star_rating=(
                    "Patient Survey Star Rating Numeric",
                    "mean",
                ),
                hospital_count=("Facility ID", "nunique"),
            )
            .sort_values("avg_star_rating", ascending=False)
        )

        fig = px.bar(
            measure_summary.head(15),
            x="avg_star_rating",
            y="HCAHPS Answer Description",
            orientation="h",
            hover_data=["hospital_count"],
            title="Average Star Rating by HCAHPS Measure",
        )
        fig.update_layout(
            xaxis_title="Average star rating",
            yaxis_title="HCAHPS measure",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.write("### HCAHPS Detail Table")

        hcahps_display_cols = [
            col
            for col in [
                "Facility ID",
                "Facility Name",
                "State",
                "HCAHPS Measure ID",
                "HCAHPS Answer Description",
                "Patient Survey Star Rating",
                "HCAHPS Answer Percent",
                "Number of Completed Surveys",
                "Survey Response Rate Percent",
                "Start Date",
                "End Date",
            ]
            if col in hcahps_rated.columns
        ]

        st.dataframe(
            hcahps_rated[hcahps_display_cols].head(1000),
            use_container_width=True,
            hide_index=True,
        )
st.divider()

st.subheader("Unplanned Visits / Readmissions Data Preview")

st.info(
    "Readmission and unplanned visit analysis will be added after loading the "
    "CMS Unplanned Hospital Visits dataset. This first version currently focuses "
    "on hospital profile and overall rating analysis."
)

st.divider()

st.subheader("Hospital Detail Table")

detail_cols = [
    col
    for col in [
        "Facility ID",
        "Facility Name",
        "City/Town",
        "State",
        "Hospital Type",
        "Hospital Ownership",
        "Emergency Services",
        "Hospital overall rating",
    ]
    if col in filtered_hospitals.columns
]

st.dataframe(
    filtered_hospitals[detail_cols].sort_values(
        ["State", "Facility Name"], na_position="last"
    ),
    use_container_width=True,
    hide_index=True,
)

csv = filtered_hospitals[detail_cols].to_csv(index=False).encode("utf-8")

st.download_button(
    "Download filtered hospital table as CSV",
    data=csv,
    file_name="filtered_hospital_quality_data.csv",
    mime="text/csv",
)

st.divider()

st.subheader("Preliminary Stakeholder Insights")

st.write(
    """
    This first version is designed to support exploratory review. A project team could use
    the dashboard to identify hospitals or regions with lower ratings, compare performance
    by hospital type, and review unplanned visit or readmission-related measures for potential
    quality-improvement follow-up.
    """
)