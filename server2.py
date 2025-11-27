from flask import Flask, request, jsonify, render_template_string
import subprocess, os, re
from datetime import datetime

app = Flask(__name__)

# 최근 분석 결과들을 메모리에 저장 (시연용)
# 각 요소: {
#   "url": ...,
#   "time": ...,
#   "step1": {"status": "...", "detail": "..."},
#   "step2": {"status": "...", "detail": "..."},
#   "step3": {"status": "...", "detail": "..."},
#   "final": "...",
#   "log_tail": "..."
# }
recent_jobs = []
current_job = None

# ---------------------------------------------------------------------
# 기존 파이프라인 실행 함수 (run_pipeline.sh 그대로 호출)
# ---------------------------------------------------------------------
def run_pipeline_stream(url: str):
    script_path = os.path.join(os.path.dirname(__file__), "run_pipeline.sh")

    # conda 경로 보정
    env = os.environ.copy()
    env["PATH"] = "/home/taewoon/anaconda3/bin:" + env.get("PATH", "")

    proc = subprocess.Popen(
        ["bash", script_path, url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    tail = []
    for line in iter(proc.stdout.readline, ''):
        line = line.rstrip("\n")
        print(line, flush=True)   # 서버 콘솔에 진행 로그 실시간 출력
        tail.append(line)
        if len(tail) > 200:       # 최근 200줄만 보관
            tail.pop(0)
        update_current_job(url, "\n".join(tail))
    proc.stdout.close()
    rc = proc.wait()
    return rc, "\n".join(tail)
    


# run_pipeline.sh에서 찍는 "최종 결과: 정상/비정상" 라인 파싱
FINAL_RE = re.compile(r"최종 결과:\s*(정상|비정상)")

def parse_final_label(log_tail: str):
    m = FINAL_RE.search(log_tail)
    return m.group(1) if m else None

# ---------------------------------------------------------------------
# 단계별 상태 파싱 (run_pipeline.sh 로그 기반)
# ---------------------------------------------------------------------
def parse_step_info(log_tail: str):
    """
    run_pipeline.sh 출력 로그에서
    1단계(url-based), 2단계(content-based), 3단계(dynamic-analysis) 상태를 추출.
    - 실행 시작: [1/3] ..., [2/3] ..., [3/3] ...
    - 최종 결과: url-based 결과:, content-based 결과:, dynamic-analysis 결과:
    """
    step1 = {"status": "UNKNOWN", "detail": ""}
    step2 = {"status": "UNKNOWN", "detail": ""}
    step3 = {"status": "UNKNOWN", "detail": ""}

    for line in log_tail.splitlines():
        # 1단계 실행 시작
        if "[1/3]" in line and "url_based_detection.py" in line:
            step1["status"] = "진행중"
            step1["detail"] = line

        # 2단계 실행 시작
        elif "[2/3]" in line and "content_based_detection.py" in line:
            step2["status"] = "진행중"
            step2["detail"] = line

        # 3단계 실행 시작
        elif "[3/3]" in line and "dynamic_detection.py" in line:
            step3["status"] = "진행중"
            step3["detail"] = line

        # 1단계 최종 결과
        elif "url-based 결과:" in line:
            if "비정상" in line:
                step1["status"] = "비정상"
            elif "정상" in line:
                step1["status"] = "정상"
            else:
                step1["status"] = "UNKNOWN"
            step1["detail"] = line

        # 2단계 최종 결과
        elif "content-based 결과:" in line:
            if "비정상" in line:
                step2["status"] = "비정상"
            elif "정상" in line:
                step2["status"] = "정상"
            else:
                step2["status"] = "UNKNOWN"
            step2["detail"] = line

        # 3단계 최종 결과
        elif "dynamic-analysis 결과:" in line:
            if "비정상" in line:
                step3["status"] = "비정상"
            elif "정상" in line:
                step3["status"] = "정상"
            else:
                step3["status"] = "UNKNOWN"
            step3["detail"] = line

    # 파이프라인 특성상 비정상 나오면 뒤 단계는 SKIPPED 취급
    if step1["status"] == "비정상":
        if step2["status"] == "UNKNOWN":
            step2["status"] = "SKIPPED"
        if step3["status"] == "UNKNOWN":
            step3["status"] = "SKIPPED"
    elif step1["status"] == "정상" and step2["status"] == "비정상":
        if step3["status"] == "UNKNOWN":
            step3["status"] = "SKIPPED"

    return step1, step2, step3

def update_current_job(url: str, tail_text: str):
    """
    run_pipeline_stream에서 로그가 한 줄씩 쌓일 때마다
    현재 tail 전체를 기반으로 current_job을 업데이트.
    """
    global current_job

    # 다른 URL이거나 current_job이 아직 없으면 건너뛰기
    if current_job is None or current_job.get("url") != url:
        return

    step1, step2, step3 = parse_step_info(tail_text)
    final_label = parse_final_label(tail_text)
    final = decide_final_from_steps(final_label, step1, step2, step3)

    # final이 아직 UNKNOWN이면 '분석 중'이라는 텍스트로 보이게
    if final in (None, "UNKNOWN"):
        final_for_view = "분석 중"
    else:
        final_for_view = final

    current_job["step1"] = step1
    current_job["step2"] = step2
    current_job["step3"] = step3
    current_job["final"] = final_for_view
    current_job["log_tail"] = tail_text

def decide_final_from_steps(final_label, step1, step2, step3):
    """
    run_pipeline.sh 로그에서 뽑은 final_label("정상"/"비정상")을 우선 사용하고,
    없으면 단계 상태를 보고 최종 판정 추론.
    """
    if final_label in ("정상", "비정상"):
        return final_label

    statuses = {step1["status"], step2["status"], step3["status"]}
    if "비정상" in statuses:
        return "비정상"
    if "정상" in statuses and "비정상" not in statuses:
        return "정상"
    return "UNKNOWN"

# ---------------------------------------------------------------------
# 안드로이드에서 URL 보내는 기존 엔드포인트 (/receive)
# ---------------------------------------------------------------------
@app.route('/receive', methods=['POST'])
def receive():
    global recent_jobs, current_job

    data = request.get_json(force=True)
    device = data.get("device")
    links = data.get("links", [])

    print(f"[+] From device: {device}")
    print(f"[+] Received links: {links}")

    results = []
    for link in links:
        print(f"[*] Running pipeline for: {link}", flush=True)

        # 🔹 파이프라인 시작 시점에 current_job 초기값 세팅
        current_job = {
            "url": link,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "step1": {"status": "진행중", "detail": "URL 기반 분석 실행 중..."},
            "step2": {"status": "대기", "detail": ""},
            "step3": {"status": "대기", "detail": ""},
            "final": "분석 중",
            "log_tail": "",
            "returncode": None,
        }

        try:
            rc, tail = run_pipeline_stream(link)
            final_label = parse_final_label(tail)

            # 최종 결과 재계산
            step1, step2, step3 = parse_step_info(tail)
            final_result = decide_final_from_steps(final_label, step1, step2, step3)

            job = {
                "url": link,
                "time": current_job["time"],
                "step1": step1,
                "step2": step2,
                "step3": step3,
                "final": final_result,
                "log_tail": tail,
                "returncode": rc,
            }

            # 최근 결과 저장
            recent_jobs.insert(0, job)
            if len(recent_jobs) > 50:
                recent_jobs = recent_jobs[:50]

            # current_job도 완료 상태로 덮어쓰기
            current_job = job

            results.append({
                "url": link,
                "returncode": rc,
                "final_label": final_label,
                "final": final_result,
                "step1": step1,
                "step2": step2,
                "step3": step3,
                "log_tail": tail,
            })
        except subprocess.TimeoutExpired:
            results.append({"url": link, "error": "timeout"})
        except Exception as e:
            results.append({"url": link, "error": str(e)})

    return jsonify({"ok": True, "results": results})

# ---------------------------------------------------------------------
# Health check (기존)
# ---------------------------------------------------------------------
@app.route('/health')
def health():
    return "ok"

# ---------------------------------------------------------------------
# 대시보드용 API
# ---------------------------------------------------------------------
@app.route("/api/jobs/latest", methods=["GET"])
def api_latest_job():
    if current_job is not None:
        return jsonify({"exists": True, "job": current_job})
    if recent_jobs:
        return jsonify({"exists": True, "job": recent_jobs[0]})
    return jsonify({"exists": False})

@app.route("/api/jobs", methods=["GET"])
def api_jobs():
    return jsonify(recent_jobs)

# ---------------------------------------------------------------------
# 대시보드 HTML (단일 파일 템플릿)
# ---------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8" />
    <title>STShield 분석 대시보드</title>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            margin-top: 0;
        }
        .card {
            background: #ffffff;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        }
        .url-text {
            font-weight: 600;
            font-size: 16px;
            word-break: break-all;
        }
        .steps {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 12px;
        }
        .step-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 10px;
            border-radius: 8px;
            background-color: #fafafa;
        }
        .step-label {
            font-weight: 600;
            min-width: 150px;
        }
        .step-detail {
            font-size: 14px;
            color: #555;
        }
        .badge {
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            color: #fff;
        }
        .badge-정상 { background-color: #4CAF50; }
        .badge-비정상 { background-color: #F44336; }
        .badge-SKIPPED { background-color: #9E9E9E; }
        .badge-UNKNOWN { background-color: #757575; }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        th, td {
            padding: 8px 6px;
            border-bottom: 1px solid #e0e0e0;
            text-align: left;
        }
        th {
            background-color: #fafafa;
        }
        .final-정상 { color: #4CAF50; font-weight: 700; }
        .final-비정상 { color: #F44336; font-weight: 700; }
        .final-UNKNOWN { color: #757575; font-weight: 700; }
        .final-SKIPPED { color: #9E9E9E; font-weight: 700; }

        .small {
            font-size: 12px;
            color: #888;
        }
        details {
            margin-top: 10px;
        }
        pre {
            background-color: #111;
            color: #f5f5f5;
            padding: 10px;
            border-radius: 8px;
            max-height: 300px;
            overflow: auto;
            font-size: 12px;
        }
        .tagline {
            margin-bottom: 10px;
            color: #555;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <h1>STShield URL 분석 대시보드</h1>

    <div id="current-card" class="card">
        <h2>분석 결과</h2>
        <div id="current-content">
            <p>아직 분석된 URL이 없습니다.</p>
        </div>
    </div>

    <div class="card">
        <h2>최근 요청 로그</h2>
        <table>
            <thead>
                <tr>
                    <th>시간</th>
                    <th>URL</th>
                    <th>1단계</th>
                    <th>2단계</th>
                    <th>3단계</th>
                    <th>최종</th>
                </tr>
            </thead>
            <tbody id="jobs-table-body">
                <!-- JS로 채움 -->
            </tbody>
        </table>
    </div>

<script>
function statusBadge(status) {
    if (!status) status = "UNKNOWN";
    const cls = "badge-" + status;
    let label = status;
    if (status === "UNKNOWN") label = "알 수 없음";
    if (status === "SKIPPED") label = "건너뜀";
    return '<span class="badge ' + cls + '">' + label + '</span>';
}

function finalClass(finalStatus) {
    if (!finalStatus) finalStatus = "UNKNOWN";
    return "final-" + finalStatus;
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

async function fetchLatestJob() {
    const container = document.getElementById("current-content");

    // 🔹 렌더 전 상태 저장
    let wasOpen = false;
    let prevScrollTop = 0;
    let wasAtBottom = false;

    if (container) {
        const prevDetails = container.querySelector("details");
        if (prevDetails && prevDetails.open) {
            wasOpen = true;
        }

        const prevPre = container.querySelector("pre");
        if (prevPre) {
            prevScrollTop = prevPre.scrollTop;
            const diff = prevPre.scrollHeight - (prevPre.scrollTop + prevPre.clientHeight);
            // 거의 맨 아래까지 내려가 있었으면 '아래에 고정' 상태로 간주
            wasAtBottom = diff < 5;
        }
    }

    const res = await fetch("/api/jobs/latest");
    const data = await res.json();

    if (!data.exists) {
        container.innerHTML = "<p>아직 분석된 URL이 없습니다.</p>";
        return;
    }

    const job = data.job;

    container.innerHTML = `
        <div class="url-text">${job.url}</div>
        <div class="small">분석 시각: ${job.time}</div>
        <div class="steps">
            <div class="step-item">
                <div class="step-label">1단계 URL 기반</div>
                <div>${statusBadge(job.step1.status)}</div>
                <div class="step-detail">${job.step1.detail || ""}</div>
            </div>
            <div class="step-item">
                <div class="step-label">2단계 콘텐츠 기반</div>
                <div>${statusBadge(job.step2.status)}</div>
                <div class="step-detail">${job.step2.detail || ""}</div>
            </div>
            <div class="step-item">
                <div class="step-label">3단계 동적 분석</div>
                <div>${statusBadge(job.step3.status)}</div>
                <div class="step-detail">${job.step3.detail || ""}</div>
            </div>
        </div>
        <h3>최종 결과: <span class="${finalClass(job.final)}">${job.final}</span></h3>
        <details>
            <summary>전체 로그 보기</summary>
            <pre>${escapeHtml(job.log_tail)}</pre>
        </details>
    `;

    // 🔹 렌더 후 상태 복원
    const newDetails = container.querySelector("details");
    const newPre = container.querySelector("pre");

    // details가 예전에 열려 있었다면 다시 열기
    if (wasOpen && newDetails) {
        newDetails.open = true;
    }

    // 스크롤 위치 복원
    if (newPre) {
        if (wasAtBottom) {
            // 맨 아래 보고 있던 상태면 계속 맨 아래로
            newPre.scrollTop = newPre.scrollHeight;
        } else {
            // 중간 보고 있던 상태면 기존 scrollTop 근처로
            newPre.scrollTop = prevScrollTop;
        }
    }
}



async function fetchRecentJobs() {
    const res = await fetch("/api/jobs");
    const jobs = await res.json();
    const tbody = document.getElementById("jobs-table-body");

    tbody.innerHTML = "";

    jobs.forEach(job => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${job.time}</td>
            <td>${job.url}</td>
            <td>${statusBadge(job.step1.status)}</td>
            <td>${statusBadge(job.step2.status)}</td>
            <td>${statusBadge(job.step3.status)}</td>
            <td class="${finalClass(job.final)}">${job.final}</td>
        `;
        tbody.appendChild(row);
    });
}

// 2초마다 최신 상태 갱신
setInterval(() => {
    fetchLatestJob();
    fetchRecentJobs();
}, 2000);

// 첫 로딩 시 한 번 실행
fetchLatestJob();
fetchRecentJobs();
</script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template_string(DASHBOARD_HTML)

if __name__ == "__main__":
    # 기존과 동일하게 포트 5050 사용 (필요하면 변경)
    app.run(host="0.0.0.0", port=5050)

