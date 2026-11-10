"""In-process bounded observability; per-worker only, not distributed metrics."""
from collections import defaultdict
from threading import Lock
from time import perf_counter
from uuid import uuid4
from fastapi import Request

lock=Lock()
counts=defaultdict(int)
totals=defaultdict(float)
latency_buckets=(0.1,0.5,1,5,30,120)
buckets=defaultdict(lambda: [0]*7)

def observe(route, method, status, duration):
    # Route must be the path template, never dynamic IDs or query strings.
    key=(method, route, str(status))
    with lock:
        counts[key]+=1
        totals[key]+=duration
        for i, upper in enumerate(latency_buckets):
            if duration <= upper:
                buckets[key][i]+=1
                break
        else:
            buckets[key][-1]+=1

def snapshot():
    with lock:
        return [{'method':k[0],'route':k[1],'status':k[2], 'count':v,
                 'total_seconds':round(totals[k],4), 'latency_buckets':list(buckets[k])}
                for k,v in sorted(counts.items())]
