import pandas as pd
from sklearn.metrics import classification_report

# === 데이터 불러오기 ===
results = pd.read_csv("./handoff/results.csv")
truth = pd.read_csv("test_urls_1800.csv")

# 'url' 기준으로 병합
df = results.merge(truth, on="url", how="inner")

# ===============================
# ① 'UNKNOWN' 또는 'SKIPPED' 제거
# ===============================
df = df[df["final"].isin(["정상", "비정상"])]
df = df[df["label"].isin([0, 1, "정상", "비정상"])]

# ===============================
# ② 라벨 정규화 (문자→숫자)
# ===============================
def normalize_label(x):
    if str(x) in ["정상", "0"]:
        return 0
    elif str(x) in ["비정상", "1"]:
        return 1
    else:
        return None

y_true = df["label"].apply(normalize_label)
y_pred = df["final"].apply(normalize_label)

# NaN 제거 (혹시라도 남아 있을 경우)
mask = y_true.notna() & y_pred.notna()
y_true = y_true[mask]
y_pred = y_pred[mask]

# ===============================
# ③ 성능 계산
# ===============================
if len(y_true) == 0:
    print("⚠️ 유효한 데이터가 없습니다. (모두 UNKNOWN/SKIPPED 상태)")
else:
    print("📊 모델 성능 요약")
    print(classification_report(y_true, y_pred, target_names=["정상(0)", "비정상(1)"]))

