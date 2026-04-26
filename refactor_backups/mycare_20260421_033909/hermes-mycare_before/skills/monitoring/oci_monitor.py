"""MyCARE OCI監視 — リソース・ディスクを確認して異常を検知する（Cronスクリプト）"""
import shutil, subprocess, json, sys

def check_disk(threshold=80):
    total, used, free = shutil.disk_usage("/")
    pct = used / total * 100
    alerts = []
    if pct > threshold:
        alerts.append(f"DISK ALERT: {pct:.1f}% used (threshold {threshold}%)")
    return {"disk_pct": round(pct, 1), "alerts": alerts}

def check_oci_instances():
    alerts = []
    try:
        r = subprocess.run(
            ["oci", "compute", "instance", "list",
             "--compartment-id-subtree", "true",
             "--lifecycle-state", "RUNNING",
             "--query", "[].\"display-name\"", "--output", "json"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            names = json.loads(r.stdout)
            if len(names) > 2:
                alerts.append(f"OCI ALERT: {len(names)} instances running (Always Free limit: 2)")
        else:
            alerts.append(f"OCI CLI ERROR: {r.stderr.strip()[:200]}")
    except FileNotFoundError:
        pass  # oci CLI not installed
    return alerts

def check_memory(threshold=90):
    alerts = []
    try:
        with open("/proc/meminfo") as f:
            info = dict(line.split(":") for line in f if ":" in line)
        total = int(info["MemTotal"].strip().split()[0])
        available = int(info["MemAvailable"].strip().split()[0])
        pct = (total - available) / total * 100
        if pct > threshold:
            alerts.append(f"MEMORY ALERT: {pct:.1f}% used (threshold {threshold}%)")
        return {"mem_pct": round(pct, 1), "alerts": alerts}
    except Exception:
        return {"mem_pct": -1, "alerts": []}

if __name__ == "__main__":
    all_alerts = []
    disk = check_disk()
    all_alerts.extend(disk["alerts"])
    all_alerts.extend(check_oci_instances())
    mem = check_memory()
    all_alerts.extend(mem["alerts"])

    result = {
        "disk_pct": disk["disk_pct"],
        "mem_pct": mem["mem_pct"],
        "alert_count": len(all_alerts),
        "alerts": all_alerts
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1 if all_alerts else 0)
