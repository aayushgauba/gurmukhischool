# ============= Django Bootstrap ============================================
import os, re, glob, gzip, csv, joblib
import numpy as np, pandas as pd
from datetime import datetime
from collections import defaultdict
from sklearn.ensemble import IsolationForest

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gurmukhischool.settings")
import django
django.setup()
from main.models import BlacklistedIP

# ===================== Config =====================
LOG_BASE    = r"D:\Users\gauba\Downloads\gurmukhischool\stlouisgurudwara.org.access.log.txt"
MODEL_FILE  = "ai_ip_bot_detector_model.pkl"
DATA_FILE   = "access_samples.csv"
CSV_HEADER  = ["ip", "path_len", "kw_hits", "resp_time", "status_idx", "burst_count", "total_404", "label"]

malicious_keywords = [".php", "xmlrpc", "wp-", ".env", ".git", ".bak", "conflg", "shell", "filemanager"]
status_codes       = ["200", "403", "404", "500"]
bot_agents         = ["curl", "wget", "python", "sqlmap", "masscan", "nmap", "bot", "go-http-client"]
known_bots         = [
    "googlebot", "applebot", "bingbot", "duckduckbot", "baiduspider", "yandex", "slurp",
    "ahrefsbot", "facebookexternalhit", "facebot", "twitterbot", "linkedinbot", "petalbot",
    "sogou", "mj12bot", "semrushbot", "dotbot", "seznambot", "gptbot", "archive.org_bot"
]

# ===================== Helpers =====================
def read_rotated_logs(base_path):
    lines = []
    if os.path.exists(base_path):
        with open(base_path, encoding="utf-8", errors="ignore") as f:
            lines.extend(f.readlines())
    for path in sorted(glob.glob(base_path + ".*")):
        opener = gzip.open if path.endswith(".gz") else open
        try:
            with opener(path, "rt", encoding="utf-8", errors="ignore") as f:
                lines.extend(f.readlines())
        except OSError:
            continue
    return lines

_LOG_RX = re.compile(r'(\d+\.\d+\.\d+\.\d+).*\[(.*?)\].*"(GET|POST) (.*?) HTTP/.*?" (\d{3}).*?"(.*?)" "(.*?)"')

def parse_log_line(line):
    m = _LOG_RX.search(line)
    if not m:
        return None
    ip, ts_str, _, path, status, ref, ua = m.groups()
    try:
        ts = datetime.strptime(ts_str.split()[0], "%d/%b/%Y:%H:%M:%S")
    except ValueError:
        return None
    rt = re.search(r'response-time=(\d+\.\d+)', line)
    return dict(
        ip = ip,
        timestamp = ts,
        path = path,
        status = status,
        referer = ref,
        user_agent = ua,
        response_time = float(rt.group(1)) if rt else 0.0
    )

def is_suspicious(path, status, ua):
    ua = ua.lower()
    if any(b in ua for b in known_bots):
        return False
    path = path.lower()
    if any(k in path for k in malicious_keywords):
        return True
    if status == "404":
        return True
    if any(b in ua for b in bot_agents):
        return True
    return False

def build_rows(parsed, ip_404):
    ip_times = defaultdict(list)
    for rec in parsed:
        ip_times[rec["ip"]].append(rec["timestamp"])

    rows = []
    for rec in parsed:
        ip = rec["ip"]
        recent = [t for t in ip_times[ip] if (rec["timestamp"] - t).total_seconds() <= 10]
        kw_hits = sum(k in rec["path"].lower() for k in malicious_keywords)
        rows.append([
            ip,
            len(rec["path"]),
            kw_hits,
            rec["response_time"],
            status_codes.index(rec["status"]) if rec["status"] in status_codes else -1,
            len(recent),
            ip_404[ip],
            "unlabeled"
        ])
    return rows

def append_csv(rows):
    new_file = not os.path.exists(DATA_FILE)
    with open(DATA_FILE, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(CSV_HEADER)
        writer.writerows(rows)

def load_feature_matrix():
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return None, None
    CSV_HEADER = ["ip", "path_len", "kw_hits", "resp_time", "status_idx", "burst_count", "total_404", "label"]
    df = pd.read_csv(DATA_FILE, names=CSV_HEADER, skiprows=1, engine="python", on_bad_lines="skip")
    df = df.reindex(columns=CSV_HEADER).fillna(0)
    X = df.drop(columns=["ip", "label"]).values
    return X, df


def train_iforest(X):
    clf = IsolationForest(contamination=0.01, random_state=42)
    clf.fit(X)
    joblib.dump(clf, MODEL_FILE)
    print("🔧 Model trained and saved.")
    return clf

# ===================== Main Detection =====================
def detect():
    print("🧠  Active‑Learning Defender starting …")
    lines = read_rotated_logs(LOG_BASE)
    print(f"📑  {len(lines)} total lines.")

    parsed = []
    ip_404 = defaultdict(int)

    for ln in lines:
        rec = parse_log_line(ln.strip())
        if not rec:
            continue
        if rec["status"] == "404":
            ip_404[rec["ip"]] += 1
        if is_suspicious(rec["path"], rec["status"], rec["user_agent"]):
            parsed.append(rec)

    # Instantly block IPs with ≥6 404s
    auto_blocked = {ip for ip, c in ip_404.items() if c >= 6}
    for ip in auto_blocked:
        BlacklistedIP.objects.get_or_create(
            ip_address = ip,
            defaults   = {"reason": "Excessive 404s (≥6)"}
        )
    if auto_blocked:
        print(f"🚫  Instantly blocked {len(auto_blocked)} IPs for ≥6 404s")

    if not parsed:
        print("✅  No suspicious requests; exiting.")
        return

    rows = build_rows(parsed, ip_404)
    append_csv(rows)

    X, _ = load_feature_matrix()
    if X is None or len(X) < 20:
        print("⚠️  Not enough total samples to train.")
        return

    model = train_iforest(X)
    new_X = np.array([r[1:-1] for r in rows], dtype=float)
    preds = model.predict(new_X)

    ml_blocked = set()
    for row, pred in zip(rows, preds):
        ip = row[0]
        print(ip, pred)
        if pred == -1 and ip not in auto_blocked:
            if not BlacklistedIP.objects.filter(ip_address=ip).exists():
                BlacklistedIP.objects.create(
                    ip_address=ip,
                    defaults={"reason": "AI-detected anomaly"}
                )
                ml_blocked.add(ip)

    print(f"🛡  AI blocked {len(ml_blocked)} additional IPs.")
    if ml_blocked:
        print("    " + ", ".join(sorted(ml_blocked)))

# ===================== Run =====================
if __name__ == "__main__":
    detect()
