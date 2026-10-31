import os
import json, datetime, sys
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runlog.jsonl')
def log(phase, kind, text):
    t = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2))).isoformat(timespec='seconds')
    with open(LOG, 'a') as f:
        f.write(json.dumps({"t": t, "phase": phase, "kind": kind, "text": text[:60]}, ensure_ascii=False) + "\n")
if __name__ == '__main__':
    log(sys.argv[1], sys.argv[2], sys.argv[3])
