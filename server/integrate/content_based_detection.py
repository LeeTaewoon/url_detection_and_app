# content_based_detection.py (verbose 버전)

import joblib
import requests as re
from bs4 import BeautifulSoup
import feature_extraction as fe
import numpy as np
from time import sleep


def main():
    # 1) 사용자 입력 URL
    url = input().strip()
    if not url:
        print("❌ URL이 비어 있습니다. 종료합니다.")
        return

    # 2) URL 요청 단계
    print("\n[1/5] URL 요청 중...")
    try:
        response = re.get(
            url,
            verify=False,
            timeout=4,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    except re.exceptions.RequestException as e:
        print(f"❌ URL 요청 중 예외 발생: {e}")
        return

    sleep(0.1)
    print(f"→ HTTP 상태 코드: {response.status_code}")

    if response.status_code != 200:
        print(f"⚠️ HTTP 상태코드가 200이 아닙니다. (현재: {response.status_code}) => {url}")
        return

    # 3) HTML 파싱 + 간단한 콘텐츠 요약
    print("\n[2/5] HTML 파싱 중...")
    soup = BeautifulSoup(response.content, "html.parser")
    sleep(0.1)

    title = (soup.title.string.strip() if soup.title and soup.title.string else "(제목 없음)")
    text = soup.get_text(separator=" ", strip=True)
    text_length = len(text)
    a_tags = soup.find_all("a")
    form_tags = soup.find_all("form")
    input_tags = soup.find_all("input")

    print("--- 콘텐츠 기본 정보 ---")
    print(f"페이지 제목: {title[:80]}{'...' if len(title) > 80 else ''}")
    print(f"텍스트 길이: {text_length} 자")
    print(f"링크(a) 태그 개수: {len(a_tags)}")
    print(f"폼(form) 태그 개수: {len(form_tags)}")
    print(f"입력(input) 태그 개수: {len(input_tags)}")
    print("------------------------\n")

    # 4) feature_extraction 기반 벡터 추출
    print("[3/5] 콘텐츠 기반 피처 벡터 생성 중...")
    try:
        vec = fe.create_vector(soup)
    except Exception as e:
        print(f"❌ 피처 벡터 생성 중 오류 발생: {e}")
        return

    vector = [vec]  # 2D 형태로 변환
    sleep(0.1)

    # 5) 모델 로딩 + 예측
    print("[4/5] 콘텐츠 기반 머신러닝 모델 로딩 중...")
    try:
        model = joblib.load("content_based_model.pkl")
    except Exception as e:
        print(f"❌ 모델 로딩 실패: {e}")
        return

    sleep(0.1)

    print("[5/5] 피싱 여부 예측 중...\n")
    try:
        result = model.predict(vector)
    except Exception as e:
        print(f"❌ 예측 중 오류 발생: {e}")
        return

    # 확률(있는 경우)
    prob_phishing = None
    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(vector)[0]  # [정상, 피싱] 가정
            # 보통 1이 피싱 클래스일 확률이므로 index 1
            if len(proba) > 1:
                prob_phishing = proba[1] * 100.0
        except Exception:
            prob_phishing = None

    # 7) 결과 해석
    print("--- 콘텐츠 기반 분석 결과 ---")
    if result[0] == 0:
        print("결과: [ 정상 ] 해당 URL은 정상 사이트일 가능성이 높습니다.")
    else:
        print("결과: [ 피싱 ] 주의! 해당 URL은 피싱 사이트일 가능성이 높습니다.")

    if prob_phishing is not None:
        print(f"피싱(악성) 확률: {prob_phishing:.2f}%")
    print("-----------------------------------\n")


if __name__ == "__main__":
    main()
