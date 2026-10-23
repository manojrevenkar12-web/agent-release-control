#!/usr/bin/env bash
# Smoke test against a running API: auth, a full refund conversation with verification, release
# diff, a review report, metrics. Usage: deploy/smoke.sh http://localhost:8000 <viewer-key>
set -euo pipefail
BASE=${1:-http://localhost:8000}
KEY=${2:-viewer-key}
H=(-H "X-API-Key: $KEY" -H "Content-Type: application/json")
fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

curl -fsS "$BASE/health" | grep -q '"ok":true' || fail health
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/releases")
[ "$code" = 401 ] || fail "expected 401 without a key, got $code"

r=$(curl -fsS "${H[@]}" -d '{"account": 5, "message": "please refund my last payment"}' "$BASE/conversations")
cid=$(echo "$r" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["kind"]=="verify", d; print(d["conversation"])')
otp=$(curl -fsS "${H[@]}" "$BASE/demo/inbox/$cid" | python3 -c 'import json,sys; print(json.load(sys.stdin)["verification_code"])')
curl -fsS "${H[@]}" -d "{\"message\": \"the code is $otp\"}" "$BASE/conversations/$cid/messages" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["kind"]=="result", d' || fail "refund did not complete"

curl -fsS "${H[@]}" "$BASE/releases/r2-personalised/diff" | grep -q plan_aware || fail diff
curl -fsS "${H[@]}" "$BASE/reviews/r2-personalised" | grep -q '"decision"' || fail "review report"
curl -fsS "$BASE/metrics" | grep -q 'arc_agent_replies_total' || fail metrics
echo "smoke ok"
