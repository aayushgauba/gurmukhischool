import os
import re
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

LOG_FILE = r"D:\Users\gauba\Downloads\gurmukhischool\stlouisgurudwara.org.access.log.txt"
MODEL_FILE = "ai_ip_bot_detector_model.pkl"
DATA_FILE = "access_samples.csv"
malicious_keywords = [".php", "xmlrpc", "wp-", ".env", ".git", ".bak", "conflg", "shell", "filemanager"]
status_codes = ["200", "403", "404", "500"]
bot_agents = ["curl", "wget", "python", "sqlmap", "masscan", "nmap", "bot", "go-http-client"]

def parse_log_line(line):
    try:
        m = re.search(r'(\d+\.\d+\.\d+\.\d+).*\[(.*?)\].*"(GET|POST) (.*?) HTTP/.*?" (\d{3}).*?"(.*?)" "(.*?)"', line)
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
        print(f"⚠️ Parse error: {e}")
        return None
# List of known search engine and legitimate crawlers
known_bots = [
    "googlebot", "applebot", "bingbot", "duckduckbot", "baiduspider",
    "yandex", "slurp", "ahrefsbot", "facebookexternalhit", "facebot",
    "twitterbot", "linkedinbot", "petalbot", "sogou", "mj12bot",
    "semrushbot", "dotbot", "seznambot", "gptbot", "archive.org_bot"
]

def is_suspicious_request(path, status, user_agent):
    user_agent = user_agent.lower()
    
    # Allow known good bots
    if any(bot in user_agent for bot in known_bots):
        return False
    
    # Our spam/bot detection rules
    path = path.lower()
    if any(kw in path for kw in malicious_keywords): return True
    if status == "404": return True
    if any(ua in user_agent for ua in bot_agents): return True
    
    return False


def extract_features(parsed):
    ip_times = defaultdict(list)
    for entry in parsed:
        ip_times[entry["ip"]].append(entry["timestamp"])

    feature_rows = []
    for entry in parsed:
        ip = entry["ip"]
        recent = [t for t in ip_times[ip] if (entry["timestamp"] - t).total_seconds() <= 10]
        feature_rows.append([
            ip,
            len(entry["path"]),
            sum(kw in entry["path"].lower() for kw in malicious_keywords),
            entry["response_time"],
            status_codes.index(entry["status"]) if entry["status"] in status_codes else -1,
            len(recent),
            "unlabeled"  # default label
        ])
    return feature_rows

def save_features(feature_rows):
    with open(DATA_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        for row in feature_rows:
            writer.writerow(row)

def load_features():
    if not os.path.exists(DATA_FILE):
        return [], []
    df = pd.read_csv(DATA_FILE, header=None,
                     names=["ip", "path_len", "kw_hits", "resp_time", "status_idx", "burst_count", "label"])
    X = df[["path_len", "kw_hits", "resp_time", "status_idx", "burst_count"]].values
    y = df["label"].values
    return X, y, df

def retrain_model(X):
    model = IsolationForest(contamination=0.01, random_state=42)
    model.fit(X)
    joblib.dump(model, MODEL_FILE)
    print("✅ Model retrained and saved.")
    return model

def detect():
    print("🧠 Running bot detection update...")
    with open(LOG_FILE, 'r') as f:
        parsed = [parse_log_line(l) for l in f if l.strip()]
    parsed = [p for p in parsed if p and is_suspicious_request(p["path"], p["status"], p["user_agent"])]
    if not parsed:
        print("✅ No suspicious entries today.")
        return

    features = extract_features(parsed)
    save_features(features)

    X, y, df = load_features()
    if len(X) < 10:
        print("⚠️ Not enough data to train.")
        return

    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
    else:
        model = retrain_model(X)

    preds = model.predict(np.array([f[1:-1] for f in features]))  # exclude IP + label
    blocked = set()

    for i, pred in enumerate(preds):
        ip = features[i][0]
        if pred == -1 and not BlacklistedIP.objects.filter(ip_address=ip).exists():
            BlacklistedIP.objects.create(ip_address=ip, reason="AI-detected anomaly")
            blocked.add(ip)

    print(f"🛡 Blocked {len(blocked)} new IP(s): {', '.join(blocked) if blocked else 'None'}")

if __name__ == "__main__":
    detect()
