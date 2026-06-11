from pathlib import Path

import numpy as np
import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

HOSPITAL_GENERAL_INFO_PATH = RAW_DIR / "Hospital_General_Information.csv"
HCAHPS_PATH = RAW_DIR / "HCAHPS_Hospital.csv"
UNPLANNED_VISITS_PATH = RAW_DIR / "Unplanned_Hospital_Visits_Hospital.csv"


def clean_rating(value):
    if pd.isna(value):
        return np.nan

    text = str(value).strip()

    if text.lower() in {
        "not available",
        "not applicable",
        "not enough information",
        "",
        "nan",
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
        "nan",
    }:
        return np.nan

    try:
        return float(text)
    except ValueError:
        return np.nan


def clean_number(value):
    if pd.isna(value):
        return np.nan

    text = str(value).strip().replace(",", "")

    if text.lower() in {
        "not available",
        "not applicable",
        "not enough information",
        "",
        "nan",
    }:
        return np.nan

    try:
        return float(text)
    except ValueError:
        return np.nan


def classify_unplanned_measure(measure_name):
    if pd.isna(measure_name):
        return "Unknown"

    text = str(measure_name).lower()

    if "readmission" in text:
        return "Readmission"

    if "return days" in text or "excess days" in text or "edac" in text:
        return "Hospital Return Days / EDAC"

    if "hospital visit" in text or "unplanned visit" in text:
        return "Unplanned Visit"

    return "Other Unplanned Visit Measure"


def classify_compared_to_national(value):
    if pd.isna(value):
        return "Not Available"

    text = str(value).strip().lower()

    if text in {"", "not available", "not applicable", "nan"}:
        return "Not Available"

    if "worse" in text or "more" in text or "higher" in text:
        return "Worse Than National"

    if "better" in text or "fewer" in text or "lower" in text or "less" in text:
        return "Better Than National"

    if "no different" in text or "same" in text or "average" in text:
        return "No Different Than National"

    return str(value).strip()


def read_raw_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing raw file: {path}\n"
            f"Expected raw files to be saved in {RAW_DIR}."
        )

    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    return df


def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Saved {path} ({len(df):,} rows, {size_mb:.2f} MB)")


def build_hospitals_processed():
    hospitals = read_raw_csv(HOSPITAL_GENERAL_INFO_PATH)

    required = [
        "Facility ID",
        "Facility Name",
        "State",
        "Hospital Type",
        "Hospital Ownership",
        "Hospital overall rating",
    ]

    missing = [col for col in required if col not in hospitals.columns]
    if missing:
        raise ValueError(
            "Hospital General Information is missing expected columns: "
            + ", ".join(missing)
        )

    keep_cols = [
        col
        for col in [
            "Facility ID",
            "Facility Name",
            "Address",
            "City/Town",
            "State",
            "ZIP Code",
            "County/Parish",
            "Telephone Number",
            "Hospital Type",
            "Hospital Ownership",
            "Emergency Services",
            "Hospital overall rating",
        ]
        if col in hospitals.columns
    ]

    hospitals = hospitals[keep_cols].copy()

    hospitals["Hospital overall rating numeric"] = hospitals[
        "Hospital overall rating"
    ].apply(clean_rating)

    for col in ["Facility ID", "Facility Name", "City/Town", "State", "Hospital Type", "Hospital Ownership"]:
        if col in hospitals.columns:
            hospitals[col] = hospitals[col].astype(str).str.strip()

    save_csv(hospitals, PROCESSED_DIR / "hospitals_processed.csv")


def build_hcahps_processed():
    hcahps = read_raw_csv(HCAHPS_PATH)

    required = [
        "Facility ID",
        "Facility Name",
        "State",
        "Patient Survey Star Rating",
    ]

    missing = [col for col in required if col not in hcahps.columns]
    if missing:
        raise ValueError("HCAHPS file is missing expected columns: " + ", ".join(missing))

    keep_cols = [
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
        if col in hcahps.columns
    ]

    hcahps = hcahps[keep_cols].copy()

    hcahps["Patient Survey Star Rating Numeric"] = hcahps[
        "Patient Survey Star Rating"
    ].apply(clean_rating)

    if "HCAHPS Answer Percent" in hcahps.columns:
        hcahps["HCAHPS Answer Percent Numeric"] = hcahps[
            "HCAHPS Answer Percent"
        ].apply(clean_percent)

    if "Number of Completed Surveys" in hcahps.columns:
        hcahps["Number of Completed Surveys Numeric"] = hcahps[
            "Number of Completed Surveys"
        ].apply(clean_number)

    if "Survey Response Rate Percent" in hcahps.columns:
        hcahps["Survey Response Rate Percent Numeric"] = hcahps[
            "Survey Response Rate Percent"
        ].apply(clean_percent)

    for col in ["Facility ID", "Facility Name", "State", "HCAHPS Measure ID", "HCAHPS Answer Description"]:
        if col in hcahps.columns:
            hcahps[col] = hcahps[col].astype(str).str.strip()

    hcahps_measures = hcahps.dropna(subset=["Patient Survey Star Rating Numeric"]).copy()

    measure_cols = [
        col
        for col in [
            "Facility ID",
            "Facility Name",
            "State",
            "HCAHPS Measure ID",
            "HCAHPS Answer Description",
            "Patient Survey Star Rating",
            "Patient Survey Star Rating Numeric",
            "HCAHPS Answer Percent",
            "HCAHPS Answer Percent Numeric",
            "Number of Completed Surveys",
            "Number of Completed Surveys Numeric",
            "Survey Response Rate Percent",
            "Survey Response Rate Percent Numeric",
            "Start Date",
            "End Date",
        ]
        if col in hcahps_measures.columns
    ]

    hcahps_measures = hcahps_measures[measure_cols].copy()

    agg_dict = {
        "avg_patient_experience": ("Patient Survey Star Rating Numeric", "mean"),
        "hcahps_measure_rows": ("Patient Survey Star Rating Numeric", "count"),
    }

    if "HCAHPS Answer Percent Numeric" in hcahps_measures.columns:
        agg_dict["avg_answer_percent"] = ("HCAHPS Answer Percent Numeric", "mean")

    if "Number of Completed Surveys Numeric" in hcahps_measures.columns:
        agg_dict["avg_completed_surveys"] = (
            "Number of Completed Surveys Numeric",
            "mean",
        )

    if "Survey Response Rate Percent Numeric" in hcahps_measures.columns:
        agg_dict["avg_response_rate"] = (
            "Survey Response Rate Percent Numeric",
            "mean",
        )

    hcahps_facility_summary = (
        hcahps_measures.groupby(["Facility ID", "Facility Name", "State"], as_index=False)
        .agg(**agg_dict)
        .sort_values("avg_patient_experience", ascending=False)
    )

    save_csv(hcahps_measures, PROCESSED_DIR / "hcahps_measures_processed.csv")
    save_csv(hcahps_facility_summary, PROCESSED_DIR / "hcahps_facility_summary.csv")


def build_unplanned_processed():
    unplanned = read_raw_csv(UNPLANNED_VISITS_PATH)

    required = [
        "Facility ID",
        "Facility Name",
        "State",
        "Measure Name",
        "Compared to National",
    ]

    missing = [col for col in required if col not in unplanned.columns]
    if missing:
        raise ValueError(
            "Unplanned Hospital Visits file is missing expected columns: "
            + ", ".join(missing)
        )

    keep_cols = [
        col
        for col in [
            "Facility ID",
            "Facility Name",
            "State",
            "Measure ID",
            "Measure Name",
            "Compared to National",
            "Score",
            "Denominator",
            "Number of Patients",
            "Lower Estimate",
            "Higher Estimate",
            "Start Date",
            "End Date",
        ]
        if col in unplanned.columns
    ]

    unplanned = unplanned[keep_cols].copy()

    for col in ["Facility ID", "Facility Name", "State", "Measure ID", "Measure Name", "Compared to National"]:
        if col in unplanned.columns:
            unplanned[col] = unplanned[col].astype(str).str.strip()

    unplanned["Measure Group"] = unplanned["Measure Name"].apply(
        classify_unplanned_measure
    )
    unplanned["Performance Category"] = unplanned["Compared to National"].apply(
        classify_compared_to_national
    )

    if "Score" in unplanned.columns:
        unplanned["Score Numeric"] = unplanned["Score"].apply(clean_number)

    for numeric_col in [
        "Denominator",
        "Number of Patients",
        "Lower Estimate",
        "Higher Estimate",
    ]:
        if numeric_col in unplanned.columns:
            unplanned[f"{numeric_col} Numeric"] = unplanned[numeric_col].apply(
                clean_number
            )

    unplanned["Worse Flag"] = unplanned["Performance Category"].eq(
        "Worse Than National"
    )
    unplanned["Better Flag"] = unplanned["Performance Category"].eq(
        "Better Than National"
    )
    unplanned["No Different Flag"] = unplanned["Performance Category"].eq(
        "No Different Than National"
    )
    unplanned["Available Comparison Flag"] = ~unplanned["Performance Category"].eq(
        "Not Available"
    )

    agg_dict = {
        "unplanned_measure_rows": ("Performance Category", "count"),
        "available_unplanned_comparisons": ("Available Comparison Flag", "sum"),
        "worse_than_national_count": ("Worse Flag", "sum"),
        "better_than_national_count": ("Better Flag", "sum"),
        "no_different_count": ("No Different Flag", "sum"),
    }

    if "Score Numeric" in unplanned.columns:
        agg_dict["avg_unplanned_score"] = ("Score Numeric", "mean")

    unplanned_facility_summary = (
        unplanned.groupby(["Facility ID", "Facility Name", "State"], as_index=False)
        .agg(**agg_dict)
        .sort_values("worse_than_national_count", ascending=False)
    )

    unplanned_facility_summary["worse_than_national_rate"] = np.where(
        unplanned_facility_summary["available_unplanned_comparisons"] > 0,
        unplanned_facility_summary["worse_than_national_count"]
        / unplanned_facility_summary["available_unplanned_comparisons"],
        np.nan,
    )

    display_cols = [
        col
        for col in [
            "Facility ID",
            "Facility Name",
            "State",
            "Measure ID",
            "Measure Name",
            "Measure Group",
            "Compared to National",
            "Performance Category",
            "Score",
            "Score Numeric",
            "Denominator",
            "Denominator Numeric",
            "Number of Patients",
            "Number of Patients Numeric",
            "Start Date",
            "End Date",
        ]
        if col in unplanned.columns
    ]

    save_csv(unplanned[display_cols], PROCESSED_DIR / "unplanned_measures_processed.csv")
    save_csv(unplanned_facility_summary, PROCESSED_DIR / "unplanned_facility_summary.csv")


def main():
    print("Building processed CMS dashboard files...")
    print(f"Raw folder: {RAW_DIR.resolve()}")
    print(f"Processed folder: {PROCESSED_DIR.resolve()}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    build_hospitals_processed()
    build_hcahps_processed()
    build_unplanned_processed()

    print("\nDone. You can now commit the files in data/processed/ to GitHub.")
    print("Keep data/raw/ ignored so the large CMS raw files are not pushed.")


if __name__ == "__main__":
    main()
