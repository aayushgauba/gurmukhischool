import os
import re
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict
from sklearn.ensemble import IsolationForest

# =========================
# CONFIGURATION
# =========================
LOG_FILE = r"D:\Users\gauba\Downloads\gurmukhischool\stlouisgurudwara.org.access.log.txt"
MODEL_FILE = "ai_ip_bot_detector_model.pkl"

malicious_keywords = [".php", "xmlrpc", "wp-", ".env", ".git", ".bak", "conflg", "shell", "filemanager"]

def parse_log_line(line):
    """
    Parse a single line of the access log:
    Extract IP, timestamp, method, path, status, referer, user_agent, response_time if present.
    Return dict or None if parsing fails.
    """
    try:
        # Regex for IP, [timestamp], "METHOD PATH HTTP", STATUS "REFERER" "USER_AGENT"
        pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+).*\[(.*?)\].*"(GET|POST) (.*?) HTTP/.*?" (\d{3}).*?"(.*?)" "(.*?)"')
        match = pattern.search(line)
        if not match:
            return None

        ip, ts_str, method, path, status, referer, user_agent = match.groups()

        # Convert string timestamp
        ts = datetime.strptime(ts_str.split()[0], "%d/%b/%Y:%H:%M:%S")

        # Attempt to parse response-time if present
        rt_search = re.search(r'response-time=(\d+\.\d+)', line)
        response_time = float(rt_search.group(1)) if rt_search else 0.0

        return {
            "ip": ip,
            "timestamp": ts,
            "method": method,
            "path": path,
            "status": status,
            "referer": referer,
            "user_agent": user_agent,
            "response_time": response_time
        }
    except Exception as e:
        # Optional: print or log parse errors
        return None

def main():
    """
    Reads the log file, builds per-IP features, and trains an IsolationForest model.
    Saves the model to MODEL_FILE.
    """
    if not os.path.exists(LOG_FILE):
        print(f"❌ Log file not found: {LOG_FILE}")
        return

    # 1. Read the file lines
    print(f"🔍 Reading log lines from {LOG_FILE} ...")
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    print(f"📄 Total lines read: {len(lines)}")

    # 2. Parse into structured records
    records = []
    for line in lines:
        rec = parse_log_line(line)
        if rec:
            records.append(rec)

    if not records:
        print("⚠️ No valid log records parsed. Exiting.")
        return

    df = pd.DataFrame(records)
    df.sort_values(by="timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(f"✅ Parsed records: {len(df)}")

    # 3. Aggregation: group by IP and compute features
    # We'll compute:
    # total_requests, ratio_404, suspicious_path_count, avg_response_time, avg_interval
    feature_rows = []
    grouped = df.groupby("ip")

    for ip, group in grouped:
        group.sort_values("timestamp", inplace=True)
        total_requests = len(group)
        ratio_404 = (group["status"] == "404").mean()

        # suspicious hits if path has any malicious keywords
        suspicious_hits = sum(
            any(kw in str(p).lower() for kw in malicious_keywords)
            for p in group["path"]
        )

        avg_rt = group["response_time"].mean()

        # average interval between consecutive requests
        timestamps = group["timestamp"].values
        intervals = []
        for i in range(1, len(timestamps)):
            diff_sec = (timestamps[i] - timestamps[i-1]).astype('timedelta64[s]').item()
            intervals.append(diff_sec)
        avg_interval = np.mean(intervals) if intervals else 0

        feature_rows.append({
            "ip": ip,
            "total_requests": total_requests,
            "ratio_404": ratio_404,
            "suspicious_hits": suspicious_hits,
            "avg_rt": avg_rt,
            "avg_interval": avg_interval if not np.isnan(avg_interval) else 0
        })

    feature_df = pd.DataFrame(feature_rows)
    if feature_df.empty:
        print("⚠️ No features extracted. Exiting.")
        return

    print(f"🔎 Final feature set has {len(feature_df)} rows (IPs).")
    numeric_cols = ["total_requests", "ratio_404", "suspicious_hits", "avg_rt", "avg_interval"]
    X = feature_df[numeric_cols].fillna(0).values
    print(f"🔧 Training IsolationForest on shape {X.shape} ...")
    model = IsolationForest(contamination=0.01, random_state=42)
    model.fit(X)
    print("✅ Model trained.")
    joblib.dump(model, MODEL_FILE)
    print(f"✅ Model saved to '{MODEL_FILE}'.")
    feature_df.to_csv("training_features.csv", index=False)
    print("✅ 'training_features.csv' created with final features.")

if __name__ == "__main__":
    main()
