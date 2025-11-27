#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
HANDOFF_DIR="$ROOT_DIR/handoff"
PIPELINE_SCRIPT="$ROOT_DIR/run_pipeline.sh"
UNKNOWN_LIST="$HANDOFF_DIR/unknown_urls.csv"

# 1️⃣ UNKNOWN URL 목록 추출
echo "🔍 UNKNOWN URL 목록 생성 중..."
awk -F, 'NR>1 && $6 ~ /UNKNOWN/ {gsub(/"/,"",$2); print $2}' "$HANDOFF_DIR/results.csv" > "$UNKNOWN_LIST" || true

if [ ! -s "$UNKNOWN_LIST" ]; then
  echo "✅ UNKNOWN URL이 없습니다. (results.csv가 모두 처리됨)"
  exit 0
fi

COUNT=$(wc -l < "$UNKNOWN_LIST")
echo "📄 총 $COUNT개의 UNKNOWN URL을 재분석합니다."

# 2️⃣ URL별 개별 재분석
i=0
while IFS= read -r url; do
  if [[ -z "$url" ]]; then
    continue
  fi
  ((i++))
  echo "----------------------------------------"
  echo "[$i/$COUNT] 🔁 재분석 중: $url"
  
  # run_pipeline.sh 실행
  bash "$PIPELINE_SCRIPT" "$url" || echo "⚠️ $url 분석 실패 (다음으로 진행)"
  
  echo
done < "$UNKNOWN_LIST"

echo "🎯 UNKNOWN URL 재분석 완료!"
echo "📊 결과 파일: $HANDOFF_DIR/results.csv"
