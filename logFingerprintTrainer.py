import os
import re
import gzip
import csv
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict
from sklearn.ensemble import IsolationForest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gurmukhischool.settings")
import django
django.setup()
from main.models import BlacklistedIP

LOG_BASE = "/var/log/stlouisgurudwara.org.access.log"  # base log
MODEL_FILE = "ai_ip_bot_detector_model.pkl"
DATA_FILE = "access_samples.csv"

malicious_keywords = [".php", "xmlrpc", "wp-", ".env", ".git", ".bak", "conflg", "shell", "filemanager"]
status_codes = ["200", "403", "404", "500"]
bot_agents = ["curl", "wget", "python", "sqlmap", "masscan", "nmap", "bot", "go-http-client"]

# Known legitimate bots we do NOT want to flag
known_bots = [
    "googlebot", "applebot", "bingbot", "duckduckbot", "baiduspider",
    "yandex", "slurp", "ahrefsbot", "facebookexternalhit", "facebot",
    "twitterbot", "linkedinbot", "petalbot", "sogou", "mj12bot",
    "semrushbot", "dotbot", "seznambot", "gptbot", "archive.org_bot"
]

def read_rotated_logs(base_path, max_files=5):
    all_lines = []
    if os.path.exists(base_path):
        with open(base_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines.extend(f.readlines())
    for i in range(1, max_files+1):
        txt_path = f"{base_path}.{i}"
        gz_path = f"{base_path}.{i}.gz"

        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines.extend(f.readlines())
        elif os.path.exists(gz_path):
            # read compressed
            with gzip.open(gz_path, 'rt', encoding='utf-8', errors='ignore') as f:
                all_lines.extend(f.readlines())

    return all_lines

def parse_log_line(line):
    try:
        m = re.search(
            r'(\d+\.\d+\.\d+\.\d+).*\[(.*?)\].*"(GET|POST) (.*?) HTTP/.*?" (\d{3}).*?"(.*?)" "(.*?)"',
            line
        )
        if not m:
            return None
        ip, ts_str, method, path, status, referer, user_agent = m.groups()
        ts = datetime.strptime(ts_str.split()[0], "%d/%b/%Y:%H:%M:%S")
        rt_match = re.search(r'response-time=(\d+\.\d+)', line)
        response_time = float(rt_match.group(1)) if rt_match else 0.0

        return {
            "ip": ip,
            "timestamp": ts,
            "path": path,
            "status": status,
            "referer": referer,
            "user_agent": user_agent,
            "response_time": response_time
        }
    except Exception as e:
        return None

def is_suspicious_request(path, status, user_agent):
    ua_lower = user_agent.lower()
    if any(bot in ua_lower for bot in known_bots):
        return False
    path_lower = path.lower()
    if any(kw in path_lower for kw in malicious_keywords):
        return True
    if status == "404":
        return True
    if any(ua in ua_lower for ua in bot_agents):
        return True

    return False

def extract_features(parsed):
    from collections import defaultdict
    ip_times = defaultdict(list)
    for entry in parsed:
        ip_times[entry["ip"]].append(entry["timestamp"])

    feature_rows = []
    for entry in parsed:
        ip = entry["ip"]
        path_len = len(entry["path"])
        kw_count = sum(kw in entry["path"].lower() for kw in malicious_keywords)
        response_time = entry["response_time"]
        status_idx = status_codes.index(entry["status"]) if entry["status"] in status_codes else -1
        timestamps = ip_times[ip]
        now_ts = entry["timestamp"]
        recent = [t for t in timestamps if (now_ts - t).total_seconds() <= 10]
        burst_count = len(recent)
        row = [ip, path_len, kw_count, response_time, status_idx, burst_count, "unlabeled"]
        feature_rows.append(row)

    return feature_rows

def save_features(feature_rows):
    with open(DATA_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        for row in feature_rows:
            writer.writerow(row)

def load_features():
    if not os.path.exists(DATA_FILE):
        return [], [], None

    df = pd.read_csv(
        DATA_FILE, header=None,
        names=["ip", "path_len", "kw_hits", "resp_time", "status_idx", "burst_count", "label"]
    )

    X = df[["path_len", "kw_hits", "resp_time", "status_idx", "burst_count"]].values
    y = df["label"].values
    return X, y, df

def retrain_model(X):
    model = IsolationForest(contamination=0.01, random_state=42)
    model.fit(X)
    joblib.dump(model, MODEL_FILE)
    print("✅ Model retrained and saved to", MODEL_FILE)
    return model

def detect():
    print("🧠 Running bot detection update...")
    lines = read_rotated_logs(LOG_BASE, max_files=5)
    if not lines:
        print("⚠️ No lines read from logs.")
        return
    print(f"📄 Total lines read: {len(lines)}")
    parsed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        rec = parse_log_line(line)
        if rec and is_suspicious_request(rec["path"], rec["status"], rec["user_agent"]):
            parsed.append(rec)

    if not parsed:
        print("✅ No suspicious entries found.")
        return
    features = extract_features(parsed)
    save_features(features)
    X, y, df = load_features()
    if len(X) < 10:
        print("⚠️ Not enough data to train. We have only", len(X), "rows.")
        return

    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
    else:
        model = retrain_model(X)
    model = retrain_model(X)
    new_vecs = np.array([row[1:-1] for row in features], dtype=float)  # path_len, kw_hits, resp_time, status_idx, burst_count
    preds = model.predict(new_vecs)  # -1 => anomaly
    from main.models import BlacklistedIP
    blocked = set()
    for i, pred in enumerate(preds):
        ip = features[i][0]
        if pred == -1:
            if not BlacklistedIP.objects.filter(ip_address=ip).exists():
                BlacklistedIP.objects.create(ip_address=ip, reason="AI-detected anomaly")
                blocked.add(ip)
    print(f"🛡 Blocked {len(blocked)} new IP(s): {', '.join(blocked) if blocked else 'None'}")
if __name__ == "__main__":
    detect()
