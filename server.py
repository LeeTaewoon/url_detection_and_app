from flask import Flask, request, jsonify
import subprocess, os, re

app = Flask(__name__)

def run_pipeline_stream(url: str):
    script_path = os.path.join(os.path.dirname(__file__), "run_pipeline.sh")

    # conda 경로 보정 (which conda 결과에 맞게)
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
        if len(tail) > 200:
            tail.pop(0)
    proc.stdout.close()
    rc = proc.wait()
    return rc, "\n".join(tail)

FINAL_RE = re.compile(r"최종 결과:\s*(정상|비정상)")

def parse_final_label(log_tail: str):
    m = FINAL_RE.search(log_tail)
    return m.group(1) if m else None

@app.route('/receive', methods=['POST'])
def receive():
    data = request.get_json(force=True)
    device = data.get("device")
    links = data.get("links", [])

    print(f"[+] From device: {device}")
    print(f"[+] Received links: {links}")

    results = []
    for link in links:
        print(f"[*] Running pipeline for: {link}", flush=True)
        try:
            rc, tail = run_pipeline_stream(link)
            final_label = parse_final_label(tail)  # "정상" 또는 "비정상" 또는 None

            results.append({
                "url": link,
                "returncode": rc,
                "final_label": final_label,
                "log_tail": tail,  # 원하면 클라이언트에서 숨기거나 줄이기
            })
        except subprocess.TimeoutExpired:
            results.append({"url": link, "error": "timeout"})
        except Exception as e:
            results.append({"url": link, "error": str(e)})

    # 핸드폰(클라이언트)에서 바로 쓰기 좋은 형태로 응답
    return jsonify({"ok": True, "results": results})

@app.route('/health')
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
