import joblib
from urllib.parse import urlparse
import dns.resolver
import numpy as np
from time import sleep

def extract_binary_features_verbose(url):
    print("   [1/6] URL 길이 계산 중...")
    url_length = len(url)
    sleep(0.1)

    print("   [2/6] 서브도메인 개수 계산 중...")
    try:
        parsed_url = urlparse(url)
        subdomain_count = parsed_url.netloc.count('.')
    except ValueError:
        print("❌ URL 파싱 오류")
        return None
    sleep(0.1)

    print("   [3/6] 특수 문자 개수 계산 중...")
    special_chars = ['@', '-', '_', '=', '&', '?', '%']
    special_char_count = sum(url.count(char) for char in special_chars)
    sleep(0.1)

    print("   [4/6] 숫자 개수 계산 중...")
    digit_count = sum(c.isdigit() for c in url)
    sleep(0.1)

    print("   [5/6] HTTPS 여부 검사 중...")
    https_flag = 1 if parsed_url.scheme == 'https' else 0
    sleep(0.1)

    print("   [6/6] NS 레코드 개수 조회 중...")
    domain = parsed_url.netloc.lower().replace('www.', '')

    def get_ns_record(domain):
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2
            resolver.lifetime = 4
            answers = resolver.resolve(domain, 'NS')
            return len(answers)
        except:
            return 0

    ns_record_count = get_ns_record(domain)
    sleep(0.1)

    # -----------------------------------------
    # 특징 요약 출력
    # -----------------------------------------
    print("\n--- URL 기반 분석: 추출된 특징값 ---")
    print(f"url_length: {url_length}")
    print(f"subdomain_count: {subdomain_count}")
    print(f"special_char_count: {special_char_count}")
    print(f"digit_count: {digit_count}")
    print(f"https_flag: {https_flag}")
    print(f"ns_record_count: {ns_record_count}")
    print("-----------------------------------\n")

    return [
        url_length,
        subdomain_count,
        special_char_count,
        digit_count,
        https_flag,
        ns_record_count,
    ]


def main():
    model = joblib.load('url_based_model.pkl')
    sleep(0.2)

    while True:
        url = input().strip()
        if url.lower() == 'exit':
            print("프로그램을 종료합니다.")
            break

        print(f"\n[1/] '{url}'에서 특징 추출 중...\n")
        features = extract_binary_features_verbose(url)
        if features is None:
            print("❌ 유효하지 않은 URL입니다. 다시 시도하세요.\n")
            continue

        X = np.array(features).reshape(1, -1)

        print("[2/2] 머신러닝 모델 예측 중...\n")
        pred = model.predict(X)[0]

        # 확률(있는 경우)
        prob = None
        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(X)[0][1] * 100  # 악성 확률(%)

        label_map = {0: "정상 URL", 1: "비정상 URL"}

        print("--- URL 기반 분석 결과 ---")
        print(f"결과: [ {label_map.get(pred, '알 수 없음')} ]")
        if prob is not None:
            print(f"악성 확률: {prob:.2f}%")
        print("-----------------------------------\n")


if __name__ == "__main__":
    main()
