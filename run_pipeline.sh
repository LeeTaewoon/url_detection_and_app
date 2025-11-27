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
  echo "timestamp,url,url_based,content_based,dynamic,final" > "$CSV"
fi

# 기본값
timestamp="$(date '+%Y-%m-%d %H:%M:%S%z')"
url_based="UNKNOWN"
content_based="SKIPPED"
dynamic_res="SKIPPED"
final_res="UNKNOWN"

# 공통: Python 경고 억제용 환경 변수 설정
export PYTHONWARNINGS="ignore"

# 1️⃣ URL-based 분석 (capde2)
echo "1단계 : url_based_detection.py 실행"
(
  cd "$INTEG_DIR"
  # stderr(경고)도 필터링해서 로그로만 남기고, 터미널에는 표시 안 함
  printf "%s\n%s\n" "$URL" "exit" | \
    conda run -n capde2 --no-capture-output python url_based_detection.py \
    2> "$HANDOFF_DIR/url_based_stderr.log"
) | tee "$HANDOFF_DIR/url_based_stdout.log"

# URL-based 분석 결과 판별
if grep -q "비정상" "$HANDOFF_DIR/url_based_stdout.log"; then
  url_based="비정상"
  final_res="비정상"
  echo "🚫 url-based 결과: 비정상 URL. 분석을 중단합니다."
  echo "최종 결과: 비정상"
  printf '%s,"%s",%s,%s,%s,%s\n' "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" >> "$CSV"
  exit 0
elif grep -q "정상" "$HANDOFF_DIR/url_based_stdout.log"; then
  url_based="정상"
  echo "url-based 결과: 정상 URL → 다음 단계(content-based) 실행"
else
  url_based="UNKNOWN"
  echo "⚠️ url-based 결과를 판별할 수 없습니다. (로그 확인 필요)"
  printf '%s,"%s",%s,%s,%s,%s\n' "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" >> "$CSV"
  exit 1
fi

# 2️⃣ Content-based 분석 (capde)
echo "2단계 : content_based_detection.py 실행"
(
  cd "$INTEG_DIR"
  printf "%s\n%s\n" "$URL" "exit" | \
    conda run -n capde --no-capture-output python content_based_detection.py \
    2> "$HANDOFF_DIR/content_based_stderr.log"
) | tee "$HANDOFF_DIR/content_based_stdout.log"

# Content-based 분석 결과 판별
if grep -q "비정상" "$HANDOFF_DIR/content_based_stdout.log"; then
  content_based="비정상"
  final_res="비정상"
  echo "🚫 content-based 결과: 비정상 URL. 분석을 중단합니다."
  echo "최종 결과: 비정상"
  printf '%s,"%s",%s,%s,%s,%s\n' "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" >> "$CSV"
  exit 0
elif grep -q "정상" "$HANDOFF_DIR/content_based_stdout.log"; then
  content_based="정상"
  echo "content-based 결과: 정상 URL → 다음 단계(dynamic-analysis) 실행"
else
  content_based="UNKNOWN"
  echo "⚠️ content-based 결과를 판별할 수 없습니다. (로그 확인 필요)"
  printf '%s,"%s",%s,%s,%s,%s\n' "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" >> "$CSV"
  exit 1
fi

# 3️⃣ Dynamic 분석 (dynamic_analysis)
echo "3단계 : dynamic-analysis: dynamic_detection.py 실행"
(
  cd "$INTEG_DIR"
  conda run -n dynamic_analysis --no-capture-output python dynamic_detection.py "$URL" \
    2> "$HANDOFF_DIR/dynamic_stderr.log"
) | tee "$HANDOFF_DIR/dynamic_analysis_stdout.log"

# Dynamic 분석 최종 결과 판별
if grep -Eq "비정상" "$HANDOFF_DIR/dynamic_analysis_stdout.log"; then
  dynamic_res="비정상"
  final_res="비정상"
  echo "🚫 dynamic-analysis 결과: 비정상(악성) URL"
  echo "최종 결과: 비정상"
elif grep -q "정상" "$HANDOFF_DIR/dynamic_analysis_stdout.log"; then
  dynamic_res="정상"
  final_res="정상"
  echo "최종 결과: 정상"
  echo "dynamic-analysis 결과: 정상 URL"
else
  dynamic_res="UNKNOWN"
  echo "⚠️ dynamic-analysis 결과를 판별할 수 없습니다. (로그 확인 필요)"
fi

# CSV 최종 기록
printf '%s,"%s",%s,%s,%s,%s\n' "$timestamp" "$URL" "$url_based" "$content_based" "$dynamic_res" "$final_res" >> "$CSV"

echo "모든 분석이 완료되었습니다. 로그와 결과는 $HANDOFF_DIR/ 에 저장되었습니다."


