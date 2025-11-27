#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "사용법: $0 <URL>"
  exit 1
fi

URL="$1"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
INTEG_DIR="$ROOT_DIR/integrate"
HANDOFF_DIR="$ROOT_DIR/handoff"
mkdir -p "$HANDOFF_DIR"

CSV="$HANDOFF_DIR/results.csv"
# CSV 헤더 생성(최초 1회)
if [ ! -f "$CSV" ]; then
  echo "timestamp,url,url_based,content_based,dynamic,final,url_time,content_time,dynamic_time,total_time" > "$CSV"
fi

# 기본값
timestamp="$(date '+%Y-%m-%d %H:%M:%S%z')"
url_based="UNKNOWN"
content_based="SKIPPED"
dynamic_res="SKIPPED"
final_res="UNKNOWN"

# 시간 측정용 변수
url_time=0
content_time=0
dynamic_time=0
total_start=$(date +%s)

# 1️⃣ URL-based 분석 (capde2)
echo "[1/3] capde2: url_based_detection.py 실행 (URL: $URL)"
url_start=$(date +%s)
(
  cd "$INTEG_DIR"
  printf "%s\n%s\n" "$URL" "exit" | conda run -n capde2 --no-capture-output python url_based_detection.py
) | tee "$HANDOFF_DIR/url_based_stdout.log"
url_end=$(date +%s)
url_time=$((url_end - url_start))

# URL-based 결과 판별
if grep -q "비정상" "$HANDOFF_DIR/url_based_stdout.log"; then
  url_based="비정상"
  final_res="비정상"
  echo "🚫 url-based 결과: 비정상 URL. 분석을 중단합니다. (소요시간: ${url_time}s)"
  printf '%s,"%s",%s,%s,%s,%s,%ds,%s,%s,%ds\n' \
    "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" \
    "$url_time" "-" "-" "$url_time" >> "$CSV"
  exit 0
elif grep -q "정상" "$HANDOFF_DIR/url_based_stdout.log"; then
  url_based="정상"
  echo "✅ url-based 결과: 정상 URL → 다음 단계(content-based) 실행 (소요시간: ${url_time}s)"
else
  url_based="UNKNOWN"
  echo "⚠️ url-based 결과를 판별할 수 없습니다. (소요시간: ${url_time}s)"
  printf '%s,"%s",%s,%s,%s,%s,%ds,%s,%s,%ds\n' \
    "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" \
    "$url_time" "-" "-" "$url_time" >> "$CSV"
  exit 1
fi

# 2️⃣ Content-based 분석 (capde)
echo "[2/3] capde: content_based_detection.py 실행 (URL: $URL)"
content_start=$(date +%s)
(
  cd "$INTEG_DIR"
  printf "%s\n%s\n" "$URL" "exit" | conda run -n capde --no-capture-output python content_based_detection.py
) | tee "$HANDOFF_DIR/content_based_stdout.log"
content_end=$(date +%s)
content_time=$((content_end - content_start))

if grep -q "비정상" "$HANDOFF_DIR/content_based_stdout.log"; then
  content_based="비정상"
  final_res="비정상"
  echo "🚫 content-based 결과: 비정상 URL. 분석 중단 (소요시간: ${content_time}s)"
  total_end=$(date +%s)
  total_time=$((total_end - total_start))
  printf '%s,"%s",%s,%s,%s,%s,%ds,%ds,%s,%ds\n' \
    "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" \
    "$url_time" "$content_time" "-" "$total_time" >> "$CSV"
  exit 0
elif grep -q "정상" "$HANDOFF_DIR/content_based_stdout.log"; then
  content_based="정상"
  echo "✅ content-based 결과: 정상 URL → 다음 단계(dynamic-analysis) 실행 (소요시간: ${content_time}s)"
else
  content_based="UNKNOWN"
  echo "⚠️ content-based 결과를 판별할 수 없습니다. (소요시간: ${content_time}s)"
  total_end=$(date +%s)
  total_time=$((total_end - total_start))
  printf '%s,"%s",%s,%s,%s,%s,%ds,%ds,%s,%ds\n' \
    "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" \
    "$url_time" "$content_time" "-" "$total_time" >> "$CSV"
  exit 1
fi

# 3️⃣ Dynamic 분석 (dynamic_analysis)
echo "[3/3] dynamic-analysis: dynamic_detection.py 실행 (URL: $URL)"
dynamic_start=$(date +%s)
(
  cd "$INTEG_DIR"
  conda run -n dynamic_analysis --no-capture-output python dynamic_detection.py "$URL"
) | tee "$HANDOFF_DIR/dynamic_analysis_stdout.log"
dynamic_end=$(date +%s)
dynamic_time=$((dynamic_end - dynamic_start))

if grep -q "비정상" "$HANDOFF_DIR/dynamic_analysis_stdout.log"; then
  dynamic_res="비정상"
  final_res="비정상"
  echo "🚫 dynamic-analysis 결과: 비정상 URL (소요시간: ${dynamic_time}s)"
elif grep -q "정상" "$HANDOFF_DIR/dynamic_analysis_stdout.log"; then
  dynamic_res="정상"
  final_res="정상"
  echo "✅ dynamic-analysis 결과: 정상 URL (소요시간: ${dynamic_time}s)"
else
  dynamic_res="UNKNOWN"
  echo "⚠️ dynamic-analysis 결과를 판별할 수 없습니다. (소요시간: ${dynamic_time}s)"
fi

# 전체 시간 계산
total_end=$(date +%s)
total_time=$((total_end - total_start))

# CSV 최종 기록
printf '%s,"%s",%s,%s,%s,%s,%ds,%ds,%ds,%ds\n' \
  "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" \
  "$url_time" "$content_time" "$dynamic_time" "$total_time" >> "$CSV"

echo "🎯 완료! 모든 분석이 완료되었습니다. (총 소요시간: ${total_time}s)"
echo "로그와 결과는 $HANDOFF_DIR/ 에 저장되었습니다."

