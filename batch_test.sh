#!/usr/bin/env bash
set -euo pipefail

URL_FILE="test_urls_1800.csv"
ANALYZE_SCRIPT="./run_detection.sh"
HANDOFF_DIR="./handoff"

mkdir -p "$HANDOFF_DIR"

CPU_CORES=$(nproc)
MAX_JOBS=$((CPU_CORES - 1))
if (( MAX_JOBS < 1 )); then MAX_JOBS=1; fi

echo "⚙️ 병렬 실행 시작 (최대 동시 작업: ${MAX_JOBS})"

# CSV 유효성 검사
if [ ! -f "$URL_FILE" ]; then
  echo "❌ 오류: $URL_FILE 파일이 없습니다."
  exit 1
fi

# 헤더 확인
header=$(head -n 1 "$URL_FILE")
if [[ "$header" != *"url"* || "$header" != *"label"* ]]; then
  echo "❌ CSV 헤더에 url,label 컬럼이 필요합니다."
  exit 1
fi

# URL 목록 추출 후 병렬 실행 (로그 최소화)
tail -n +2 "$URL_FILE" | awk -F',' '{print $1}' | \
xargs -I {} -P "$MAX_JOBS" bash -c '
  URL="{}"
  echo "▶ 분석 중: $URL"
  bash "'"$ANALYZE_SCRIPT"'" "$URL" >/dev/null 2>&1 || echo "⚠️ 오류 발생: $URL"
'

echo "✅ 모든 URL 병렬 분석 완료!"
echo "📄 결과 파일: $HANDOFF_DIR/results.csv"



