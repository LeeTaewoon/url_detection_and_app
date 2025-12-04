<p align="center">
  <img src="STShield_logo.png" width="150"/>
</p>

<h1 align="center">ST Shield: Multi-Stage Phishing URL Detection System</h1>

<p align="center">
  문자(SMS) 기반 3단계 악성 URL 탐지 시스템 (캡스톤디자인)
</p>

## 프로젝트 소개 (Overview)

**ST Shield**는 사용자 스마트폰에서 수신한 문자(SMS)에 포함된 URL의  
스미싱 여부를 자동 분석하는 **3단계 악성 URL 탐지 시스템**입니다.

1. **URL 기반 정적 분석**
2. **HTML/JavaScript 기반 콘텐츠 분석 (머신러닝)**
3. **Fakeium 브라우저 기반 동적 실행 분석**

"URL 공유 → 즉시 분석 → 정상/악성 판별" 흐름을 통해  
기존 스미싱 탐지 시스템에 비해 더 **정확한 판별과 견고한 보안성**을 제공합니다.

## 시스템 아키텍처

<p align="center">
  <img src="assets/architecture.png" width="80%">
</p>

## 주요 기능 (Features)

### 1) URL 기반 탐지 (Static)
- URL 패턴 분석
- 의심 도메인 정규식 검사
- 빠른 1차 선별 단계 (< 1초)

### 2) 콘텐츠 기반 탐지 (HTML/JS Feature Extraction)
- Selenium을 활용한 스크립트 수집
- ML 모델(RandomForest/AdaBoost 등) 기반 분석
- 페이지 내 악성 스크립트 여부 파악

### 3) 동적 분석 (Dynamic Analysis – Fakeium)
- 실제 브라우저에서 URL 실행
- 리다이렉트·팝업·스크립트 실행 여부 모니터링
- 높은 정확도의 최종 판정 단계

### Android App
- 문자 앱에서 공유 시 자동으로 URL 추출
- 서버로 전송 및 결과 수신
- 정상/악성 여부를 직관적으로 표시

## 📱 앱 UI Screenshots

<p align="center">
  <img src="assets/app_1.png" width="30%">
  <img src="assets/app_2.png" width="30%">
  <img src="assets/app_3.png" width="30%">
</p>

## 🚀 설치 및 실행 방법 (Installation & Usage)

### 🖥️ 1. 서버 설치 (Ubuntu + conda)

```bash
conda create -n stshield python=3.9
conda activate stshield

pip install -r requirements.txt
python server/server.py
