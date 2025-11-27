#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSV_FILE="$ROOT_DIR/handoff/results.csv"

if [ ! -f "$CSV_FILE" ]; then
  echo "❌ 파일을 찾을 수 없습니다: $CSV_FILE"
  exit 1
fi

python3 - <<'PYCODE'
import pandas as pd
import re

path = "handoff/results.csv"
df = pd.read_csv(path)

# === 숫자 추출 함수 ===
def extract_numeric(x):
    if pd.isna(x):
        return None
    if isinstance(x, (int, float)):
        return x
    match = re.search(r"(\d+(\.\d+)?)", str(x))
    return float(match.group(1)) if match else None

# 변환 대상 컬럼들
for col in ["url_time", "content_time", "dynamic_time", "total_time"]:
    df[col] = df[col].apply(extract_numeric)

# 유효 데이터만
df = df[df["final"].isin(["정상", "비정상"])]

# === 전체 평균 ===
overall_avg = df[["url_time", "content_time", "dynamic_time", "total_time"]].mean()
print("📊 전체 평균 시간 (초 단위)")
print(overall_avg.round(2))
print("\n")

# === 정상/비정상 별 평균 ===
group_avg = (
    df.groupby("final")[["url_time", "content_time", "dynamic_time", "total_time"]]
    .mean()
    .round(2)
)
print("⚖️ 정상/비정상 별 평균 시간 (초 단위)")
print(group_avg)
print("\n")

# === 비중 계산 ===
if not overall_avg.isna().all():
    time_ratios = (overall_avg / overall_avg["total_time"] * 100).round(1)
    print("⏱️ 단계별 평균 비중 (%)")
    print(time_ratios)
else:
    print("⚠️ 시간 데이터가 유효하지 않습니다 (모두 NaN).")
PYCODE

