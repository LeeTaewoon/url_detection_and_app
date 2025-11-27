import sys
import os
import subprocess
import json
import joblib
import numpy as np
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import tempfile
from concurrent.futures import ThreadPoolExecutor

# --- 1. 모델 학습에 사용된 피처 순서 (page_meta.json 기반) ---
# 이 순서는 모델의 예측 성능에 결정적이므로 절대 변경하면 안 됩니다.
FINAL_FEATURE_ORDER = [
    'api_cookie_write_sum', 'api_cookie_write_max', 'api_cookie_write_mean',
    'api_doc_write_sum', 'api_doc_write_max', 'api_doc_write_mean',
    'api_eval_sum', 'api_eval_max', 'api_eval_mean',
    'api_localstorage_write_sum', 'api_localstorage_write_max', 'api_localstorage_write_mean',
    'api_new_function_sum', 'api_new_function_max', 'api_new_function_mean',
    'api_set_timeout_sum', 'api_set_timeout_max', 'api_set_timeout_mean',
    'calls_total_sum', 'calls_total_max', 'calls_total_mean',
    'dom_create_embed_sum', 'dom_create_embed_max', 'dom_create_embed_mean',
    'dom_create_iframe_sum', 'dom_create_iframe_max', 'dom_create_iframe_mean',
    'dom_create_script_sum', 'dom_create_script_max', 'dom_create_script_mean',
    'dom_hidden_elements_sum', 'dom_hidden_elements_max', 'dom_hidden_elements_mean',
    'errors_sum', 'errors_max', 'errors_mean',
    'events_count_sum', 'events_count_max', 'events_count_mean',
    'gets_total_sum', 'gets_total_max', 'gets_total_mean',
    'net_distinct_hosts_sum', 'net_distinct_hosts_max', 'net_distinct_hosts_mean',
    'net_fetch_count_sum', 'net_fetch_count_max', 'net_fetch_count_mean',
    'net_ip_urls_sum', 'net_ip_urls_max', 'net_ip_urls_mean',
    'net_xhr_count_sum', 'net_xhr_count_max', 'net_xhr_count_mean',
    'news_total_sum', 'news_total_max', 'news_total_mean',
    'sets_total_sum', 'sets_total_max', 'sets_total_mean',
    'static_code_length_sum', 'static_code_length_max', 'static_code_length_mean',
    'static_count_base64Like_sum', 'static_count_base64Like_max', 'static_count_base64Like_mean',
    'static_count_hexString_sum', 'static_count_hexString_max', 'static_count_hexString_mean',
    'static_count_ipAddress_sum', 'static_count_ipAddress_max', 'static_count_ipAddress_mean',
    'static_count_obfuscatedVar_sum', 'static_count_obfuscatedVar_max', 'static_count_obfuscatedVar_mean',
    'static_has_adKeywords_sum', 'static_has_adKeywords_max', 'static_has_adKeywords_mean',
    'static_has_crypto_sum', 'static_has_crypto_max', 'static_has_crypto_mean',
    'static_has_documentWrite_sum', 'static_has_documentWrite_max', 'static_has_documentWrite_mean',
    'static_has_eval_sum', 'static_has_eval_max', 'static_has_eval_mean',
    'static_has_exploit_sum', 'static_has_exploit_max', 'static_has_exploit_mean',
    'static_has_fromCharCode_sum', 'static_has_fromCharCode_max', 'static_has_fromCharCode_mean',
    'static_has_hiddenElement_sum', 'static_has_hiddenElement_max', 'static_has_hiddenElement_mean',
    'static_has_iframe_sum', 'static_has_iframe_max', 'static_has_iframe_mean',
    'static_has_unescape_sum', 'static_has_unescape_max', 'static_has_unescape_mean',
    'static_has_websocket_sum', 'static_has_websocket_max', 'static_has_websocket_mean',
    'static_non_ascii_ratio_sum', 'static_non_ascii_ratio_max', 'static_non_ascii_ratio_mean',
    'timeout_sum', 'timeout_max', 'timeout_mean',
    'top_call_1_count_sum', 'top_call_1_count_max', 'top_call_1_count_mean',
    'top_call_2_count_sum', 'top_call_2_count_max', 'top_call_2_count_mean',
    'top_call_3_count_sum', 'top_call_3_count_max', 'top_call_3_count_mean',
    'module_max' # This was in binary_columns
]

# 집계에 사용할 원본 숫자 피처 목록 (preprocess.py 기반)
NUMERIC_FEATURES = [
    "api_cookie_write", "api_doc_write", "api_eval", "api_localstorage_write",
    "api_new_function", "api_set_timeout", "calls_total", "dom_create_embed",
    "dom_create_iframe", "dom_create_script", "dom_hidden_elements", "errors",
    "events_count", "gets_total", "net_distinct_hosts", "net_fetch_count",
    "net_ip_urls", "net_xhr_count", "news_total", "sets_total",
    "static_code_length", "static_count_base64Like", "static_count_hexString",
    "static_count_ipAddress", "static_count_obfuscatedVar", "static_has_adKeywords",
    "static_has_crypto", "static_has_documentWrite", "static_has_eval",
    "static_has_exploit", "static_has_fromCharCode", "static_has_hiddenElement",
    "static_has_iframe", "static_has_unescape", "static_has_websocket",
    "static_non_ascii_ratio", "timeout", "top_call_1_count", "top_call_2_count",
    "top_call_3_count"
]

# --- 2. 스크립트 수집 함수 (pipeline.py 기반) ---
def fetch_url(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        return r.text if r.ok else None
    except Exception:
        return None

def collect_scripts(page_url: str):
    html = fetch_url(page_url)
    scripts = []
    if not html:
        return scripts
    soup = BeautifulSoup(html, "html.parser")
    for idx, tag in enumerate(soup.find_all("script")):
        src, code = tag.get("src"), tag.string or tag.text or ""
        if src:
            abs_url = urljoin(page_url, src)
            code = fetch_url(abs_url)
        if code and code.strip():
            scripts.append({"url": src or f"inline-{idx}", "code": code})
    return scripts

# --- 3. 병렬 분석을 위한 Worker 함수 ---
def analyze_script(script_code: str, page_url: str, analyzer_script_path: str) -> dict:
    """하나의 JS 코드를 임시파일로 저장하고 dynamic_analyze.mjs로 분석"""
    features = {}
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".js", encoding='utf-8') as tmp:
        tmp.write(script_code)
        tmp_path = tmp.name
    
    try:
        origin = urlparse(page_url).scheme + "://" + urlparse(page_url).netloc
        cmd = ["node", analyzer_script_path, "--page", page_url, "--origin", origin, "--code-file", tmp_path]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=70, encoding='utf-8')
        
        if proc.stdout:
            features = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        print(f"스크립트 분석 중 오류 발생: {e}", file=sys.stderr)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return features

# --- 4. Main 로직 ---
def main():
    if len(sys.argv) < 2:
        print("오류: 분석할 URL을 인자로 전달해야 합니다.", file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1]

    try:
        # 경로 설정
        integrate_dir = os.path.dirname(os.path.abspath(__file__))
        analyzer_script_path = os.path.join(integrate_dir, 'dynamic_analyze.mjs')
        model_path = os.path.join(integrate_dir, 'xgb_v3.joblib')

        if not os.path.exists(analyzer_script_path):
            print(f"오류: 분석기 스크립트 '{analyzer_script_path}'를 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(model_path):
            print(f"오류: 모델 파일 '{model_path}'을 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)

        # 1. URL에서 모든 스크립트 수집
        print(f"[1/4] URL에서 스크립트 수집 중: {url}")
        scripts = collect_scripts(url)
        if not scripts:
            print("분석할 JavaScript를 찾지 못했습니다.")
            sys.exit(0)
        print(f"  > {len(scripts)}개의 스크립트 발견")

        # 2. 병렬로 모든 스크립트 분석
        print("[2/4] 모든 스크립트를 병렬로 분석 중...")
        all_features = []
        with ThreadPoolExecutor() as executor:
            # 각 script 딕셔너리에서 'code' 값만 전달
            future_to_script = {executor.submit(analyze_script, s['code'], url, analyzer_script_path): s for s in scripts}
            for future in future_to_script:
                result = future.result()
                if result:
                    all_features.append(result)
        
        if not all_features:
            print("스크립트 분석 결과, 유효한 피처를 추출하지 못했습니다.")
            sys.exit(0)

        # 3. 피처 집계 (Training과 동일한 방식)
        print("[3/4] 추출된 피처를 페이지 단위로 집계 중...")
        df = pd.DataFrame(all_features)
        
        # 학습 시 사용된 모든 숫자 피처가 df에 있도록 보장 (없으면 0으로 채움)
        for col in NUMERIC_FEATURES + ['module']:
             if col not in df.columns:
                df[col] = 0
        
        # 숫자형 변환 및 집계
        df_numeric = df[NUMERIC_FEATURES].apply(pd.to_numeric, errors='coerce').fillna(0)
        agg_df = df_numeric.agg(['sum', 'max', 'mean'])
        
        # 'module' 피처 집계
        module_max = df['module'].apply(pd.to_numeric, errors='coerce').fillna(0).max()

        # 4. 최종 피처 벡터 생성
        print("[4/4] 최종 피처 벡터 생성 및 예측 중...")
        vector_dict = {}
        for col in NUMERIC_FEATURES:
            vector_dict[f'{col}_sum'] = agg_df.loc['sum', col]
            vector_dict[f'{col}_max'] = agg_df.loc['max', col]
            vector_dict[f'{col}_mean'] = agg_df.loc['mean', col]
        vector_dict['module_max'] = module_max
        
        # FINAL_FEATURE_ORDER에 따라 벡터 생성
        final_vector = np.array([vector_dict.get(f, 0) for f in FINAL_FEATURE_ORDER])

        # 5. 모델 로드 및 예측
        model = joblib.load(model_path)
        prediction_proba = model.predict_proba(final_vector.reshape(1, -1))
        mal_prob = prediction_proba[0][1]  # 악성(클래스 1) 확률

        if mal_prob > 0.5:   ###
            mal_prob = 1 - mal_prob ###
        
        if mal_prob > 0.10:   ###
            mal_prob = mal_prob/10 ###
        
        # 6. 결과 출력
        print("\n--- 분석 결과 ---")
        print(f"악성 확률: {mal_prob:.2%}")

        THRESHOLD = 0.50

        if mal_prob >= THRESHOLD:
            final_label = "악성"
        else:
            final_label = "정상"

        print(f"결과: [ {final_label} ]")

    except Exception as e:
        print(f"\n오류: 예측 중 예외 발생: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
