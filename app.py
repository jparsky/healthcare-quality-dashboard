from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="CMS Hospital Quality Dashboard",
    page_icon="🏥",
    layout="wide",
)

PROCESSED_DIR = Path("data/processed")

HOSPITALS_PROCESSED_PATH = PROCESSED_DIR / "hospitals_processed.csv"
HCAHPS_FACILITY_SUMMARY_PATH = PROCESSED_DIR / "hcahps_facility_summary.csv"
HCAHPS_MEASURES_PATH = PROCESSED_DIR / "hcahps_measures_processed.csv"
UNPLANNED_FACILITY_SUMMARY_PATH = PROCESSED_DIR / "unplanned_facility_summary.csv"
UNPLANNED_MEASURES_PATH = PROCESSED_DIR / "unplanned_measures_processed.csv"


# -----------------------------
# Data loading
# -----------------------------

@st.cache_data(show_spinner=True)
def load_processed_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)


def coerce_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def require_processed_files():
    required_files = [
        HOSPITALS_PROCESSED_PATH,
        HCAHPS_FACILITY_SUMMARY_PATH,
        HCAHPS_MEASURES_PATH,
        UNPLANNED_FACILITY_SUMMARY_PATH,
        UNPLANNED_MEASURES_PATH,
    ]

    missing = [path for path in required_files if not path.exists()]

    if missing:
        st.error(
            "Processed data files are missing. Run the preprocessing script locally "
            "before launching or deploying the dashboard."
        )
        st.code("py scripts/build_processed_data.py", language="bash")
        st.write("Missing files:")
        for path in missing:
            st.write(f"- `{path}`")
        st.stop()


def load_data():
    require_processed_files()

    hospitals = load_processed_csv(HOSPITALS_PROCESSED_PATH)
    hcahps_facility_summary = load_processed_csv(HCAHPS_FACILITY_SUMMARY_PATH)
    hcahps_measures = load_processed_csv(HCAHPS_MEASURES_PATH)
    unplanned_facility_summary = load_processed_csv(UNPLANNED_FACILITY_SUMMARY_PATH)
    unplanned_measures = load_processed_csv(UNPLANNED_MEASURES_PATH)

    hospitals = coerce_numeric_columns(
        hospitals,
        ["Hospital overall rating numeric"],
    )

    hcahps_facility_summary = coerce_numeric_columns(
        hcahps_facility_summary,
        [
            "avg_patient_experience",
            "hcahps_measure_rows",
            "avg_answer_percent",
            "avg_completed_surveys",
            "avg_response_rate",
        ],
    )

    hcahps_measures = coerce_numeric_columns(
        hcahps_measures,
        [
            "Patient Survey Star Rating Numeric",
            "HCAHPS Answer Percent Numeric",
            "Number of Completed Surveys Numeric",
            "Survey Response Rate Percent Numeric",
        ],
    )

    unplanned_facility_summary = coerce_numeric_columns(
        unplanned_facility_summary,
        [
            "unplanned_measure_rows",
            "available_unplanned_comparisons",
            "worse_than_national_count",
            "better_than_national_count",
            "no_different_count",
            "avg_unplanned_score",
            "worse_than_national_rate",
        ],
    )

    unplanned_measures = coerce_numeric_columns(
        unplanned_measures,
        [
            "Score Numeric",
            "Denominator Numeric",
            "Number of Patients Numeric",
        ],
    )

    return (
        hospitals,
        hcahps_facility_summary,
        hcahps_measures,
        unplanned_facility_summary,
        unplanned_measures,
    )


# -----------------------------
# Quality improvement flags
# -----------------------------

def add_quality_flags(
    hospital_df: pd.DataFrame,
    hcahps_facility_summary: pd.DataFrame,
    unplanned_facility_summary: pd.DataFrame,
) -> pd.DataFrame:
    base_cols = [
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
            "Hospital overall rating numeric",
        ]
        if col in hospital_df.columns
    ]

    flags_df = hospital_df[base_cols].copy()

    if not hcahps_facility_summary.empty:
        flags_df = flags_df.merge(
            hcahps_facility_summary[
                [
                    col
                    for col in [
                        "Facility ID",
                        "avg_patient_experience",
                        "hcahps_measure_rows",
                        "avg_answer_percent",
                        "avg_completed_surveys",
                        "avg_response_rate",
                    ]
                    if col in hcahps_facility_summary.columns
                ]
            ],
            on="Facility ID",
            how="left",
        )
    else:
        flags_df["avg_patient_experience"] = np.nan

    if not unplanned_facility_summary.empty:
        flags_df = flags_df.merge(
            unplanned_facility_summary[
                [
                    col
                    for col in [
                        "Facility ID",
                        "unplanned_measure_rows",
                        "available_unplanned_comparisons",
                        "worse_than_national_count",
                        "better_than_national_count",
                        "no_different_count",
                        "worse_than_national_rate",
                        "avg_unplanned_score",
                    ]
                    if col in unplanned_facility_summary.columns
                ]
            ],
            on="Facility ID",
            how="left",
        )
    else:
        flags_df["worse_than_national_count"] = np.nan
        flags_df["worse_than_national_rate"] = np.nan

    state_average = (
        hospital_df.dropna(subset=["Hospital overall rating numeric"])
        .groupby("State")["Hospital overall rating numeric"]
        .mean()
        .to_dict()
    )

    def get_flags(row):
        row_flags = []

        overall = row.get("Hospital overall rating numeric", np.nan)
        patient = row.get("avg_patient_experience", np.nan)
        worse_count = row.get("worse_than_national_count", np.nan)
        worse_rate = row.get("worse_than_national_rate", np.nan)
        state = row.get("State", None)
        state_avg = state_average.get(state, np.nan)

        if pd.isna(overall):
            row_flags.append("Missing overall rating")

        if not pd.isna(overall) and overall <= 2:
            row_flags.append("Low overall rating")

        if not pd.isna(patient) and patient <= 2.5:
            row_flags.append("Low patient experience")

        if not pd.isna(worse_count) and worse_count >= 1:
            row_flags.append("Worse-than-national unplanned visit/readmission measure")

        if not pd.isna(worse_rate) and not pd.isna(worse_count):
            if worse_rate >= 0.5 and worse_count >= 2:
                row_flags.append("Multiple worse-than-national outcome measures")

        if not pd.isna(overall) and not pd.isna(patient):
            if overall >= 4 and patient <= 2.5:
                row_flags.append("High quality rating / low patient experience gap")
            if overall <= 2 and patient >= 4:
                row_flags.append("Low quality rating / high patient experience gap")

        if not pd.isna(overall) and not pd.isna(state_avg):
            if overall <= state_avg - 0.75:
                row_flags.append("Below selected-state average")

        return row_flags

    def suggested_review_area(flags):
        if not flags:
            return ""

        if "Multiple worse-than-national outcome measures" in flags:
            return "Readmission, care transition, and utilization review"

        if "Worse-than-national unplanned visit/readmission measure" in flags:
            return "Unplanned visit/readmission measure review"

        if "Missing overall rating" in flags:
            return "Data completeness and reporting review"

        if "Low patient experience" in flags:
            return "Patient experience, communication, and service review"

        if "High quality rating / low patient experience gap" in flags:
            return "Patient experience review despite stronger overall rating"

        if "Low quality rating / high patient experience gap" in flags:
            return "Clinical outcome, safety, or process review"

        if "Low overall rating" in flags:
            return "Quality outcomes and process improvement review"

        if "Below selected-state average" in flags:
            return "Peer comparison and targeted performance review"

        return "Quality improvement follow-up"

    flags_df["Opportunity Flags List"] = flags_df.apply(get_flags, axis=1)
    flags_df["Opportunity Flags"] = flags_df["Opportunity Flags List"].apply(
        lambda values: "; ".join(values)
    )
    flags_df["Suggested Review Area"] = flags_df["Opportunity Flags List"].apply(
        suggested_review_area
    )
    flags_df["Flag Count"] = flags_df["Opportunity Flags List"].apply(len)

    flagged = flags_df[flags_df["Flag Count"] > 0].copy()
    flagged = flagged.sort_values(
        ["Flag Count", "State", "Facility Name"],
        ascending=[False, True, True],
    )

    return flagged


# -----------------------------
# Stakeholder summary
# -----------------------------

def build_stakeholder_summary(
    filtered_hospitals: pd.DataFrame,
    rated_hospitals: pd.DataFrame,
    hcahps_filtered_facilities: pd.DataFrame,
    unplanned_filtered_facilities: pd.DataFrame,
    flagged_hospitals: pd.DataFrame,
) -> list[str]:
    insights = []

    hospital_count = len(filtered_hospitals)
    rated_count = len(rated_hospitals)

    insights.append(
        f"The current filter selection includes **{hospital_count:,} hospitals**, "
        f"with **{rated_count:,} hospitals** reporting an overall star rating."
    )

    if not rated_hospitals.empty:
        avg_rating = rated_hospitals["Hospital overall rating numeric"].mean()
        low_rating_count = rated_hospitals[
            rated_hospitals["Hospital overall rating numeric"] <= 2
        ].shape[0]
        low_rating_pct = low_rating_count / rated_count * 100 if rated_count else 0

        insights.append(
            f"The average overall hospital rating for the selected group is "
            f"**{avg_rating:.2f} stars**. "
            f"**{low_rating_count:,} hospitals ({low_rating_pct:.1f}%)** have "
            f"an overall rating of 2 stars or lower."
        )

        state_summary = (
            rated_hospitals.groupby("State", as_index=False)
            .agg(
                avg_rating=("Hospital overall rating numeric", "mean"),
                hospital_count=("Facility ID", "count"),
            )
            .query("hospital_count >= 3")
            .sort_values("avg_rating", ascending=False)
        )

        if len(state_summary) >= 2:
            top_state = state_summary.iloc[0]
            bottom_state = state_summary.iloc[-1]

            insights.append(
                f"Among selected states with at least 3 rated hospitals, "
                f"**{top_state['State']}** has the highest average rating "
                f"(**{top_state['avg_rating']:.2f}**), while "
                f"**{bottom_state['State']}** has the lowest average rating "
                f"(**{bottom_state['avg_rating']:.2f}**)."
            )

    missing_rating_count = filtered_hospitals[
        filtered_hospitals["Hospital overall rating numeric"].isna()
    ].shape[0]

    if missing_rating_count > 0:
        insights.append(
            f"**{missing_rating_count:,} hospitals** in the filtered selection "
            f"are missing an overall rating. These records may require data "
            f"completeness review before making formal comparisons."
        )

    if not hcahps_filtered_facilities.empty:
        avg_patient = hcahps_filtered_facilities["avg_patient_experience"].mean()
        low_patient_count = hcahps_filtered_facilities[
            hcahps_filtered_facilities["avg_patient_experience"] <= 2.5
        ].shape[0]

        insights.append(
            f"HCAHPS data is available for **{len(hcahps_filtered_facilities):,} "
            f"hospitals** in the current selection. The average patient experience "
            f"rating is **{avg_patient:.2f} stars**, with **{low_patient_count:,} "
            f"hospitals** at or below 2.5 stars."
        )

    if not unplanned_filtered_facilities.empty:
        facilities_with_worse = unplanned_filtered_facilities[
            unplanned_filtered_facilities["worse_than_national_count"] >= 1
        ].shape[0]

        total_worse_measures = int(
            unplanned_filtered_facilities["worse_than_national_count"].sum()
        )

        insights.append(
            f"Unplanned visit/readmission data is available for "
            f"**{len(unplanned_filtered_facilities):,} hospitals** in the current "
            f"selection. **{facilities_with_worse:,} hospitals** have at least one "
            f"measure categorized as worse than national performance, representing "
            f"**{total_worse_measures:,} worse-than-national measure rows**."
        )

    if not flagged_hospitals.empty:
        insights.append(
            f"The opportunity flag logic identified **{len(flagged_hospitals):,} "
            f"hospitals** for potential quality improvement, data completeness, "
            f"patient experience, or unplanned visit/readmission follow-up."
        )

    if not insights:
        insights.append(
            "No stakeholder insights are available for the current filter selection."
        )

    return insights


# -----------------------------
# Main app
# -----------------------------

(
    hospitals,
    hcahps_facility_summary,
    hcahps_measures,
    unplanned_facility_summary,
    unplanned_measures,
) = load_data()

st.title("CMS Hospital Quality Dashboard")
st.caption(
    "A stakeholder-facing dashboard using public CMS hospital quality data to explore "
    "overall ratings, patient experience, unplanned visit/readmission measures, and "
    "potential quality-improvement opportunities."
)

with st.expander("Methodology and Data Quality Notes", expanded=False):
    st.write(
        """
        **Data sources.** This dashboard uses processed public CMS hospital quality files
        generated from locally downloaded CMS raw datasets. The repository includes smaller
        processed files for deployment, while the larger raw CSV files are excluded from GitHub.

        **Missing values.** CMS values such as "Not Available" and blank fields are converted
        to missing values for numeric analysis.

        **Overall ratings.** Average overall hospital ratings are calculated only from hospitals
        with available numeric star ratings.

        **Patient experience ratings.** HCAHPS files include multiple rows per facility for
        different patient experience measures. This dashboard creates a facility-level average
        patient experience rating from available HCAHPS star-rating rows. That summary is useful
        for exploratory comparison, but should not replace measure-specific review.

        **Unplanned visit/readmission measures.** CMS unplanned hospital visit data contains
        multiple provider-level measures, including readmissions, hospital return days / EDAC,
        and unplanned visits after outpatient procedures. Scores are not averaged across
        measure types for final quality conclusions because different measures may use different
        definitions and units. Instead, this dashboard uses the CMS "Compared to National" field
        to summarize whether measures are better, worse, or no different than national performance.

        **Quality improvement flags.** Opportunity flags are exploratory screening indicators.
        They are intended to identify hospitals or groups that may warrant follow-up review, not
        to make final quality determinations.

        **Use case.** The dashboard is designed to support data exploration, stakeholder
        communication, and quality-improvement prioritization.
        """
    )

st.sidebar.header("Filters")

states = sorted(hospitals["State"].dropna().unique())
default_states = ["DC"] if "DC" in states else states[:5]

selected_states = st.sidebar.multiselect(
    "State",
    options=states,
    default=default_states,
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

include_missing_ratings = st.sidebar.checkbox(
    "Include hospitals with missing overall ratings",
    value=True,
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

if include_missing_ratings:
    filtered_hospitals = filtered_hospitals[
        filtered_hospitals["Hospital overall rating numeric"].isna()
        | (filtered_hospitals["Hospital overall rating numeric"] >= min_rating)
    ]
else:
    filtered_hospitals = filtered_hospitals[
        filtered_hospitals["Hospital overall rating numeric"] >= min_rating
    ]

rated_hospitals = filtered_hospitals.dropna(
    subset=["Hospital overall rating numeric"]
)

filtered_facility_ids = set(filtered_hospitals["Facility ID"])

hcahps_filtered_facilities = hcahps_facility_summary[
    hcahps_facility_summary["Facility ID"].isin(filtered_facility_ids)
].copy()

hcahps_measure_view = hcahps_measures[
    hcahps_measures["Facility ID"].isin(filtered_facility_ids)
].copy()

unplanned_filtered_facilities = unplanned_facility_summary[
    unplanned_facility_summary["Facility ID"].isin(filtered_facility_ids)
].copy()

unplanned_view = unplanned_measures[
    unplanned_measures["Facility ID"].isin(filtered_facility_ids)
].copy()

flagged_hospitals = add_quality_flags(
    filtered_hospitals,
    hcahps_filtered_facilities,
    unplanned_filtered_facilities,
)

# -----------------------------
# Stakeholder summary
# -----------------------------

st.subheader("Stakeholder Summary")

summary_insights = build_stakeholder_summary(
    filtered_hospitals,
    rated_hospitals,
    hcahps_filtered_facilities,
    unplanned_filtered_facilities,
    flagged_hospitals,
)

for insight in summary_insights:
    st.markdown(f"- {insight}")

st.divider()

# -----------------------------
# KPI cards
# -----------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Hospitals shown", f"{len(filtered_hospitals):,}")
col2.metric("Hospitals with ratings", f"{len(rated_hospitals):,}")

avg_rating = rated_hospitals["Hospital overall rating numeric"].mean()
col3.metric(
    "Avg. overall rating",
    "N/A" if np.isnan(avg_rating) else f"{avg_rating:.2f}",
)

facilities_with_worse = unplanned_filtered_facilities[
    unplanned_filtered_facilities["worse_than_national_count"] >= 1
].shape[0]
col4.metric("Hospitals with worse outcome measure", f"{facilities_with_worse:,}")

st.divider()

# -----------------------------
# Overall quality charts
# -----------------------------

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
        fig.update_layout(
            xaxis=dict(dtick=1),
            xaxis_title="Overall star rating",
            yaxis_title="Hospital count",
        )
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
        fig.update_layout(
            yaxis_title="Average rating",
            xaxis_title="State",
        )
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

# -----------------------------
# Patient experience section
# -----------------------------

st.subheader("Patient Experience Snapshot")

if hcahps_filtered_facilities.empty:
    st.info("No HCAHPS patient experience data match the selected filters.")
else:
    patient_col1, patient_col2, patient_col3 = st.columns(3)

    avg_patient_rating = hcahps_filtered_facilities[
        "avg_patient_experience"
    ].mean()

    low_patient_count = hcahps_filtered_facilities[
        "avg_patient_experience"
    ].le(2.5).sum()

    patient_col1.metric(
        "Avg. patient experience",
        f"{avg_patient_rating:.2f}",
    )
    patient_col2.metric(
        "Hospitals with HCAHPS data",
        f"{len(hcahps_filtered_facilities):,}",
    )
    patient_col3.metric(
        "Hospitals ≤ 2.5 patient rating",
        f"{low_patient_count:,}",
    )

    patient_exp_by_state = (
        hcahps_filtered_facilities.groupby("State", as_index=False)
        .agg(
            avg_patient_experience=("avg_patient_experience", "mean"),
            hospital_count=("Facility ID", "nunique"),
        )
        .sort_values("avg_patient_experience", ascending=False)
    )

    fig = px.bar(
        patient_exp_by_state,
        x="State",
        y="avg_patient_experience",
        hover_data=["hospital_count"],
        title="Average Patient Experience Rating by State",
    )
    fig.update_layout(
        yaxis_title="Average patient experience rating",
        xaxis_title="State",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write("### Overall Rating vs. Patient Experience")

    patient_quality_join = hcahps_filtered_facilities.merge(
        hospitals[
            [
                col
                for col in [
                    "Facility ID",
                    "Hospital overall rating numeric",
                    "Hospital Type",
                    "Hospital Ownership",
                ]
                if col in hospitals.columns
            ]
        ],
        on="Facility ID",
        how="left",
    ).dropna(subset=["Hospital overall rating numeric", "avg_patient_experience"])

    if patient_quality_join.empty:
        st.info(
            "Not enough matched overall rating and patient experience data for a scatter plot."
        )
    else:
        fig = px.scatter(
            patient_quality_join,
            x="Hospital overall rating numeric",
            y="avg_patient_experience",
            color="State",
            hover_name="Facility Name",
            hover_data=[
                col
                for col in [
                    "Hospital Type",
                    "Hospital Ownership",
                    "hcahps_measure_rows",
                ]
                if col in patient_quality_join.columns
            ],
            title="Overall Hospital Rating vs. Patient Experience Rating",
        )
        fig.update_layout(
            xaxis_title="Overall hospital star rating",
            yaxis_title="Average patient experience rating",
        )
        st.plotly_chart(fig, use_container_width=True)

    if not hcahps_measure_view.empty:
        measure_summary = (
            hcahps_measure_view.groupby("HCAHPS Answer Description", as_index=False)
            .agg(
                avg_star_rating=("Patient Survey Star Rating Numeric", "mean"),
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

st.divider()

# -----------------------------
# Unplanned visits / readmissions section
# -----------------------------

st.subheader("Unplanned Visits / Readmissions Snapshot")

if unplanned_filtered_facilities.empty:
    st.info("No unplanned visit/readmission data match the selected filters.")
else:
    outcome_col1, outcome_col2, outcome_col3 = st.columns(3)

    facilities_with_worse = unplanned_filtered_facilities[
        unplanned_filtered_facilities["worse_than_national_count"] >= 1
    ].shape[0]

    total_worse_measures = int(
        unplanned_filtered_facilities["worse_than_national_count"].sum()
    )

    outcome_col1.metric(
        "Hospitals with outcome data",
        f"{len(unplanned_filtered_facilities):,}",
    )
    outcome_col2.metric(
        "Hospitals with worse measure",
        f"{facilities_with_worse:,}",
    )
    outcome_col3.metric(
        "Worse-than-national rows",
        f"{total_worse_measures:,}",
    )

    if not unplanned_view.empty:
        st.write("### Compared to National Summary")

        comparison_summary = (
            unplanned_view.groupby("Performance Category", as_index=False)
            .agg(measure_rows=("Facility ID", "count"))
            .sort_values("measure_rows", ascending=False)
        )

        fig = px.bar(
            comparison_summary,
            x="Performance Category",
            y="measure_rows",
            text="measure_rows",
            title="Unplanned Visit / Readmission Measures Compared to National",
        )
        fig.update_layout(
            xaxis_title="Performance category",
            yaxis_title="Measure rows",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.write("### Worse-Than-National Measures by Measure Group")

        worse_view = unplanned_view[
            unplanned_view["Performance Category"].eq("Worse Than National")
        ]

        if worse_view.empty:
            st.success(
                "No worse-than-national unplanned visit/readmission measure rows "
                "were identified for the current filters."
            )
        else:
            worse_by_group = (
                worse_view.groupby("Measure Group", as_index=False)
                .agg(worse_measure_rows=("Facility ID", "count"))
                .sort_values("worse_measure_rows", ascending=False)
            )

            fig = px.bar(
                worse_by_group,
                x="Measure Group",
                y="worse_measure_rows",
                text="worse_measure_rows",
                title="Worse-Than-National Rows by Measure Group",
            )
            fig.update_layout(
                xaxis_title="Measure group",
                yaxis_title="Worse-than-national rows",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.write("### State-Level Worse-Than-National Rate")

        state_outcomes = (
            unplanned_view[
                ~unplanned_view["Performance Category"].eq("Not Available")
            ]
            .groupby("State", as_index=False)
            .agg(
                available_measure_rows=("Facility ID", "count"),
                worse_measure_rows=(
                    "Performance Category",
                    lambda values: values.eq("Worse Than National").sum(),
                ),
            )
        )

        if state_outcomes.empty:
            st.info("No available comparison rows for state-level outcome analysis.")
        else:
            state_outcomes["worse_rate"] = (
                state_outcomes["worse_measure_rows"]
                / state_outcomes["available_measure_rows"]
            )

            fig = px.bar(
                state_outcomes.sort_values("worse_rate", ascending=False),
                x="State",
                y="worse_rate",
                hover_data=["available_measure_rows", "worse_measure_rows"],
                title="Share of Available Outcome Measures Worse Than National by State",
            )
            fig.update_layout(
                xaxis_title="State",
                yaxis_title="Worse-than-national share",
                yaxis_tickformat=".0%",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.write("### Unplanned Visit / Readmission Detail Table")

        outcome_display_cols = [
            col
            for col in [
                "Facility ID",
                "Facility Name",
                "State",
                "Measure Name",
                "Measure Group",
                "Compared to National",
                "Performance Category",
                "Score",
                "Denominator",
                "Number of Patients",
                "Start Date",
                "End Date",
            ]
            if col in unplanned_view.columns
        ]

        st.dataframe(
            unplanned_view[outcome_display_cols].head(1000),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

# -----------------------------
# Quality improvement flags
# -----------------------------

st.subheader("Quality Improvement Opportunity Flags")

st.write(
    """
    The table below identifies hospitals that may warrant follow-up review based on
    missing ratings, low overall ratings, lower patient experience ratings, rating gaps,
    worse-than-national unplanned visit/readmission measures, or below-peer performance
    within the selected filter group.
    """
)

if flagged_hospitals.empty:
    st.success("No quality improvement opportunity flags were identified for the current filters.")
else:
    flag_col1, flag_col2, flag_col3, flag_col4 = st.columns(4)

    flag_col1.metric("Flagged hospitals", f"{len(flagged_hospitals):,}")
    flag_col2.metric(
        "Low overall rating flags",
        f"{flagged_hospitals['Opportunity Flags'].str.contains('Low overall rating', na=False).sum():,}",
    )
    flag_col3.metric(
        "Data completeness flags",
        f"{flagged_hospitals['Opportunity Flags'].str.contains('Missing overall rating', na=False).sum():,}",
    )
    flag_col4.metric(
        "Outcome measure flags",
        f"{flagged_hospitals['Opportunity Flags'].str.contains('unplanned visit/readmission', na=False).sum():,}",
    )

    flag_display_cols = [
        col
        for col in [
            "Facility ID",
            "Facility Name",
            "City/Town",
            "State",
            "Hospital Type",
            "Hospital Ownership",
            "Hospital overall rating",
            "avg_patient_experience",
            "worse_than_national_count",
            "worse_than_national_rate",
            "Opportunity Flags",
            "Suggested Review Area",
        ]
        if col in flagged_hospitals.columns
    ]

    st.dataframe(
        flagged_hospitals[flag_display_cols],
        use_container_width=True,
        hide_index=True,
    )

    flag_csv = flagged_hospitals[flag_display_cols].to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download quality opportunity flags as CSV",
        data=flag_csv,
        file_name="quality_improvement_opportunity_flags.csv",
        mime="text/csv",
    )

st.divider()

# -----------------------------
# Hospital detail table
# -----------------------------

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

st.subheader("Future Enhancements")

st.info(
    "Potential next steps include adding national benchmark tables, separating specific "
    "readmission conditions into focused analyses, adding HEDIS or CMS quality measure "
    "context where available, and refining facility-level scoring methods."
)
