#!/usr/bin/env python3
"""
medium_test.py
Medium load:
 - Duration: 300 seconds
 - Target RPS: 50
 - Concurrency: 40
Output: results_medium.csv + graphs
"""
import time, threading, csv, argparse, statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import requests
from tqdm import tqdm
import matplotlib.pyplot as plt
import pandas as pd

DEFAULT_URL = "https://d20gk38vytw5l2.cloudfront.net/"

class RateScheduler:
    def __init__(self, rps):
        self.interval = 1.0 / float(rps) if rps > 0 else 0.0
        self.lock = threading.Lock()
        self.next_time = time.perf_counter()
    def wait_for_turn(self):
        with self.lock:
            scheduled = self.next_time
            self.next_time += self.interval
        delta = scheduled - time.perf_counter()
        if delta > 0:
            time.sleep(delta)

def worker_send(session, url, idx, scheduler, timeout):
    scheduler.wait_for_turn()
    start = time.time()
    try:
        resp = session.get(url, timeout=timeout)
        latency = time.time() - start
        return {"id": idx, "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start)),
                "status": resp.status_code, "latency": latency, "error": ""}
    except Exception as e:
        return {"id": idx, "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start)),
                "status": "ERROR", "latency": None, "error": str(e)}

def generate_graphs(csv_file, mode_name="medium"):
    df = pd.read_csv(csv_file)
    df_valid = df[df["latency"].notnull()]

    plt.figure(figsize=(10,5))
    plt.plot(df_valid["id"], df_valid["latency"], marker=".", linestyle="", alpha=0.5)
    plt.xlabel("Request #"); plt.ylabel("Latency (s)")
    plt.title(f"{mode_name.capitalize()} Test - Latency over Requests")
    plt.savefig(f"{mode_name}_latency_over_time.png", dpi=150); plt.close()

    plt.figure(figsize=(8,5))
    plt.hist(df_valid["latency"], bins=30, color="skyblue", edgecolor="black")
    plt.xlabel("Latency (s)"); plt.ylabel("Frequency")
    plt.title(f"{mode_name.capitalize()} Test - Latency Distribution")
    plt.savefig(f"{mode_name}_latency_histogram.png", dpi=150); plt.close()

    status_counts = df["status"].value_counts()
    plt.figure(figsize=(6,6))
    plt.pie(status_counts, labels=status_counts.index, autopct="%1.1f%%", startangle=90)
    plt.title(f"{mode_name.capitalize()} Test - Status Codes")
    plt.savefig(f"{mode_name}_status_codes.png", dpi=150); plt.close()
    print(f"✅ Graphs saved for {mode_name} test")

def run(url, rps=50, duration_s=300, concurrency=40, out_csv="results_medium.csv"):
    theoretical = int(rps * duration_s)
    max_requests = theoretical
    print(f"Medium: {max_requests} requests to {url}")

    scheduler = RateScheduler(rps)
    results = []
    session = requests.Session()
    session.headers.update({"User-Agent": "DoS-Resilience-Tester/1.0"})

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        pbar = tqdm(total=max_requests, desc="Requests", unit="req")
        for i in range(max_requests):
            futures.append(executor.submit(worker_send, session, url, i+1, scheduler, 10))
            if len(futures) > concurrency * 4:
                done = [f for f in futures if f.done()]
                futures = [f for f in futures if not f.done()]
                for f in done: results.append(f.result()); pbar.update(1)
        for f in as_completed(futures):
            results.append(f.result()); pbar.update(1)
        pbar.close()

    with open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id","time","status","latency","error"])
        writer.writeheader()
        for r in results: writer.writerow(r)

    total = len(results)
    status_counts = Counter(r["status"] for r in results)
    latencies = [r["latency"] for r in results if r["latency"] is not None]
    print("\n=== Medium Summary ===")
    print(f"Total: {total}, Statuses: {dict(status_counts)}")
    if latencies:
        print(f"min/avg/max (s): {min(latencies):.4f}/{statistics.mean(latencies):.4f}/{max(latencies):.4f}")
    print(f"CSV -> {out_csv}")
    generate_graphs(out_csv, "medium")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", default="results_medium.csv")
    args = parser.parse_args()
    run(args.url, out_csv=args.out)
