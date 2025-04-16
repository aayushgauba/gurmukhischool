import os
import re
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import IsolationForest

LOG_FILE = "/var/log/stlouisgurudwara.org.access.log"  # Adjust path as needed
MODEL_FILE = "ai_bot_detector_model.pkl"
malicious_keywords = [".php", "xmlrpc", "wp-", ".env", ".git", ".bak", "conflg", "shell", "filemanager"]

def parse_log_line(line):
    pattern = re.compile(
        r'(\d+\.\d+\.\d+\.\d+).*'
        r'\[(.*?)\].*'
        r'"(GET|POST) (.*?) HTTP/.*?" (\d{3}).*?'
        r'"(.*?)" "(.*?)"'
    )
    match = pattern.search(line)
    if not match:
        return None
    ip, ts_str, method, path, status, referer, user_agent = match.groups()
    try:
        ts = datetime.strptime(ts_str.split()[0], "%d/%b/%Y:%H:%M:%S")
    except ValueError:
        return None
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

def main():
    if not os.path.exists(LOG_FILE):
        print(f"❌ Log file not found: {LOG_FILE}")
        return
    print(f"🔍 Reading log lines from {LOG_FILE} ...")
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    print(f"📄 Total lines read: {len(lines)}")
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
    feature_rows = []
    grouped = df.groupby("ip")

    for ip, group in grouped:
        group.sort_values("timestamp", inplace=True)
        total_requests = len(group)
        ratio_404 = (group["status"] == "404").mean()
        suspicious_hits = sum(
            any(kw in str(p).lower() for kw in malicious_keywords)
            for p in group["path"]
        )
        avg_rt = group["response_time"].mean()
        avg_rt = 0.0 if pd.isna(avg_rt) else avg_rt
        timestamps = group["timestamp"].values
        intervals = []
        for i in range(1, len(timestamps)):
            diff_sec = (timestamps[i] - timestamps[i - 1]).astype('timedelta64[ms]').astype(float) / 1000.0
            intervals.append(diff_sec)

        if intervals:
            interval_mean = np.mean(intervals)
            if not isinstance(interval_mean, float):
                interval_mean = float(interval_mean)
            if np.isnan(interval_mean):
                interval_mean = 0.0
            avg_interval = interval_mean
        else:
            avg_interval = 0.0

        feature_rows.append({
            "ip": ip,
            "total_requests": total_requests,
            "ratio_404": ratio_404,
            "suspicious_hits": suspicious_hits,
            "avg_rt": avg_rt,
            "avg_interval": avg_interval
        })

    feature_df = pd.DataFrame(feature_rows)
    if feature_df.empty:
        print("⚠️ No features extracted. Exiting.")
        return

    print(f"🔎 Final feature set has {len(feature_df)} rows.")
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
