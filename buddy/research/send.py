"""Send a batch.py file to Claude through the Appolis door, on this session's shift, and collect the answers. Paid: batch.py build shows the expected bill first.
  py buddy/research/send.py send <file.jsonl>     starts the batch and writes <file>.id, so a later session can collect it
  py buddy/research/send.py status <file.jsonl>   says how far along it is
  py buddy/research/send.py collect <file.jsonl>  saves the answers as <file>.results.jsonl, for batch.py read
The shift proof is read from the file named by APPOLIS_SHIFT_FILE, as "<shift id>:<token>". It's never printed, and never belongs in this repo."""
import json, os, sys, urllib.error, urllib.request
from pathlib import Path

DOOR = "https://appolis.app/id/ai/anthropic/batches"


def call(url, body=None):
    proof = Path(os.environ["APPOLIS_SHIFT_FILE"]).read_text(encoding="utf-8").strip()
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"x-appolis-shift": proof, "content-type": "application/json", "user-agent": "ballot-buddy-claude-research"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"The door answered {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")


def main():
    action, f = sys.argv[1], Path(sys.argv[2])
    id_file = f.with_suffix(".id")
    if action == "send":
        if id_file.exists():
            raise SystemExit(f"{f.name} was already sent as {id_file.read_text().strip()}. Sending it again would pay twice.")
        requests = [json.loads(line) for line in f.read_text(encoding="utf-8").split("\n") if line.strip()]
        batch = json.loads(call(DOOR, {"requests": requests}))
        id_file.write_text(batch["batch"]["id"], encoding="utf-8")
        print("sent", len(requests), "requests as", batch["batch"]["id"], "paid by", batch.get("paid_by"))
    elif action == "status":
        batch = json.loads(call(f"{DOOR}/{id_file.read_text().strip()}"))["batch"]
        print(batch["processing_status"], batch["request_counts"])
    elif action == "collect":
        out = f.with_suffix(".results.jsonl")
        out.write_text(call(f"{DOOR}/{id_file.read_text().strip()}/results"), encoding="utf-8")
        print("saved", out)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
