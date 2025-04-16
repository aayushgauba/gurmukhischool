def evaluate_ip(ip, timestamps):
    if len(timestamps) < 10:
        return False
    diffs = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
    avg_interval = sum(diffs) / len(diffs)
    if avg_interval < 0.5:
        return True
    return False
