# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(layout="wide", page_title="Investment Trends Dashboard")

DATA_PATH = "Data_set 2.csv"  # change path if needed

# -----------------------------
# Helper to map likely column names
# -----------------------------
# If your CSV uses different column names, edit the values below.
COLUMN_MAP = {
    "age": None,                # e.g. "Age"
    "gender": None,             # e.g. "Gender"
    "investment_type": None,    # e.g. "Investment_Type" or "Investment"
    "duration": None,           # e.g. "Duration"
    "investment_reason": None,  # e.g. "Reason"
    "source": None,             # e.g. "Source"
    # optional:
    "monitoring_freq": None,    # e.g. "Monitoring_Frequency"
    "amount": None,             # e.g. "Amount"
}

def auto_map_columns(df):
    # try to auto-detect some column names by simple heuristics
    col_lower = {c.lower(): c for c in df.columns}
    def find(keys):
        for k in keys:
            if k in col_lower:
                return col_lower[k]
        return None

    # suggestions for each logical field
    suggestions = {
        "age": ["age", "years", "investor_age"],
        "gender": ["gender", "sex"],
        "investment_type": ["investment", "investment_type", "investment_type_name", "investment_option", "type"],
        "duration": ["duration", "investment_duration", "tenure"],
        "investment_reason": ["reason", "investment_reason", "investment_reasons", "objective"],
        "source": ["source", "source_of_information", "info_source"],
        "monitoring_freq": ["monitoring", "monitoring_frequency", "freq_monitoring"],
        "amount": ["amount", "investment_amount", "total_investment"]
    }

    mapped = {}
    for k, keys in suggestions.items():
        mapped[k] = find(keys)
    return mapped

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    return df

try:
    df = load_data(DATA_PATH)
except Exception as e:
    st.error(f"Could not load data from {DATA_PATH}. Check filename/path. Error: {e}")
    st.stop()

# auto map columns if user didn't supply explicit names
auto_map = auto_map_columns(df)
for key in COLUMN_MAP:
    if COLUMN_MAP[key] is None:
        COLUMN_MAP[key] = auto_map.get(key)

# fallback checks
if COLUMN_MAP["age"] is None:
    # try 'Age' with different capitalization
    for col in df.columns:
        if 'age' in col.lower():
            COLUMN_MAP["age"] = col
            break

if COLUMN_MAP["gender"] is None:
    for col in df.columns:
        if 'gender' in col.lower() or col.lower() in ["sex"]:
            COLUMN_MAP["gender"] = col
            break

# show resolved column names for user's awareness
st.sidebar.markdown("### Data column mapping (edit in code if wrong)")
for k, v in COLUMN_MAP.items():
    st.sidebar.write(f"- {k}: `{v}`")

# -----------------------------
# Safe access aliasing
# -----------------------------
def c(name):
    return COLUMN_MAP.get(name)

# Ensure important fields exist; if some aren't present, app will still run with limited charts
# Make sure categorical fields are strings
for col in [c("gender"), c("investment_type"), c("duration"), c("investment_reason"), c("source")]:
    if col and col in df.columns:
        df[col] = df[col].astype(str).fillna("Unknown")

# Age numeric
if c("age") and c("age") in df.columns:
    df[c("age")] = pd.to_numeric(df[c("age")], errors='coerce')

# -----------------------------
# Filters (left column)
# -----------------------------
left_col, middle_col, right_col = st.columns([1, 3, 3])

with left_col:
    st.markdown("## Filters & KPIs")
    # quick KPIs
    avg_age = None
    total_male = None
    total_female = None
    if c("age") and c("age") in df.columns:
        avg_age = df[c("age")].dropna().mean()
    if c("gender") and c("gender") in df.columns:
        genders = df[c("gender")].str.lower()
        total_male = int((genders == "male").sum())
        total_female = int((genders == "female").sum())
    # Display KPIs in boxes
    st.markdown("**Average Age**")
    st.markdown(f"### {avg_age:.2f}" if avg_age is not None else "N/A")
    st.markdown("---")
    st.markdown("**Total Male**")
    st.markdown(f"### {total_male}" if total_male is not None else "N/A")
    st.markdown("---")
    st.markdown("**Total Female**")
    st.markdown(f"### {total_female}" if total_female is not None else "N/A")
    st.markdown("---")

    # interactive filters
    st.markdown("### Interactive Filters")
    gender_filter = None
    if c("gender") and c("gender") in df.columns:
        genders_unique = sorted(df[c("gender")].unique())
        gender_filter = st.multiselect("Gender", options=genders_unique, default=genders_unique)
    else:
        gender_filter = None

    objective_filter = None
    if c("investment_reason") and c("investment_reason") in df.columns:
        objectives_unique = sorted(df[c("investment_reason")].unique())
        objective_filter = st.multiselect("Investment Objective / Reason", options=objectives_unique, default=objectives_unique)
    else:
        objective_filter = None

    # Apply filters to dataframe view below
    st.markdown("---")
    st.markdown("### Data Preview")
    st.dataframe(df.head(20))

# -----------------------------
# Preprocess filtered data
# -----------------------------
filtered = df.copy()
if gender_filter is not None:
    filtered = filtered[filtered[c("gender")].isin(gender_filter)]
if objective_filter is not None:
    filtered = filtered[filtered[c("investment_reason")].isin(objective_filter)]

# create age bins for stacked chart
if c("age") and c("age") in filtered.columns:
    bins = list(range(15, 66, 5))  # 15-19,20-24,...,60-64
    labels = [f"{b}-{b+4}" for b in bins[:-1]]
    filtered["age_group"] = pd.cut(filtered[c("age")], bins=bins, labels=labels, include_lowest=True)
else:
    filtered["age_group"] = "Unknown"

# -----------------------------
# Middle column: big charts (stacked by age groups, treemap, counts)
# -----------------------------
with middle_col:
    st.markdown("### Investment Preferences Across Age Groups (percentage stacked)")
    if c("investment_type") and c("investment_type") in filtered.columns:
        # compute percent per age_group
        group = filtered.groupby(["age_group", c("investment_type")]).size().reset_index(name="count")
        total_by_age = group.groupby("age_group")["count"].transform("sum")
        group["pct"] = group["count"] / total_by_age * 100
        # create stacked bar (percentage)
        fig1 = px.bar(group, x="age_group", y="pct", color=c("investment_type"),
                      labels={"pct":"% of investments","age_group":"age"},
                      title="")
        fig1.update_layout(barmode='stack', legend_title_text='Investment Type', xaxis_title='Age group')
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No investment type column found to build the age-group stacked chart.")

    st.markdown("### Total Investment Reasons Count (Treemap)")
    if c("investment_reason") and c("investment_reason") in filtered.columns:
        treemap_df = filtered[c("investment_reason")].value_counts().reset_index()
        treemap_df.columns = ["reason", "count"]
        fig_treemap = px.treemap(treemap_df, path=["reason"], values="count", title="")
        st.plotly_chart(fig_treemap, use_container_width=True)
    else:
        st.info("No investment reason column found to build treemap.")

    st.markdown("### Source of Investment Information (Counts)")
    if c("source") and c("source") in filtered.columns:
        src = filtered[c("source")].value_counts().reset_index()
        src.columns = ["source", "count"]
        fig_src = px.bar(src, x="count", y="source", orientation='h', labels={"count":"Total Sources","source":""}, title="")
        st.plotly_chart(fig_src, use_container_width=True)
    else:
        st.info("No source column found to build source counts chart.")

# -----------------------------
# Right column: duration chart, reason distribution pie, male/female by type
# -----------------------------
with right_col:
    st.markdown("### Total Investments Across Different Durations")
    if c("duration") and c("duration") in filtered.columns and c("investment_type") and c("investment_type") in filtered.columns:
        dur = filtered.groupby([c("duration"), c("investment_type")]).size().reset_index(name="count")
        # if duration values are short labels, keep them; else try to group similar durations
        fig_dur = px.bar(dur, x=c("duration"), y="count", color=c("investment_type"), barmode='group', labels={c("duration"):"Duration", "count":"Total"})
        st.plotly_chart(fig_dur, use_container_width=True)
    else:
        st.info("No duration or investment type column found for duration chart.")

    st.markdown("### Percentage Distribution of Investment Reasons")
    if c("investment_reason") and c("investment_reason") in filtered.columns:
        reason_counts = filtered[c("investment_reason")].value_counts().reset_index()
        reason_counts.columns = ["reason", "count"]
        fig_pie = px.pie(reason_counts, names="reason", values="count", hole=0.3)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No investment reason column found for pie chart.")

    st.markdown("### Number of Male vs Female Investors in Each Investment Type")
    if c("gender") and c("gender") in filtered.columns and c("investment_type") and c("investment_type") in filtered.columns:
        # Normalize gender values
        gcol = c("gender")
        itype = c("investment_type")
        tmp = filtered[[gcol, itype]].copy()
        tmp[gcol] = tmp[gcol].str.title()
        grouped = tmp.groupby([gcol, itype]).size().reset_index(name="count")
        fig_gender_type = px.bar(grouped, x=itype, y="count", color=gcol, barmode='group', labels={"count":"Number of Investors", itype:"Investment Type"})
        st.plotly_chart(fig_gender_type, use_container_width=True)
    else:
        st.info("No gender or investment type column found for male/female chart.")

# -----------------------------
# Bottom: Additional insights / summary
# -----------------------------
st.markdown("---")
st.markdown("## Key Takeaways (Auto-generated summary)")
takeaways = []
if avg_age is not None:
    takeaways.append(f"- Average investor age: {avg_age:.1f} years")
if total_male is not None and total_female is not None:
    takeaways.append(f"- Gender split (male : female) = {total_male} : {total_female}")
if c("investment_type") and c("investment_type") in df.columns:
    top_types = df[c("investment_type")].value_counts().nlargest(3).index.tolist()
    takeaways.append(f"- Top investment types: {', '.join(top_types)}")
if c("investment_reason") and c("investment_reason") in df.columns:
    top_reasons = df[c("investment_reason")].value_counts().nlargest(3).index.tolist()
    takeaways.append(f"- Top reasons for investing: {', '.join(top_reasons)}")

if not takeaways:
    st.write("No summary available due to missing columns.")
else:
    for t in takeaways:
        st.write(t)

# Footer with data info
st.markdown("---")
st.caption("Data visualizations generated using Pandas and Plotly. Adjust column name mappings at the top of the script if needed.")
