#!/usr/bin/env bash
# Usage: test/smoke.sh IMAGE PYTHON_VERSION
set -euo pipefail

image=$1
python_version=$2
here=$(cd "$(dirname "$0")" && pwd)

fail() {
  echo "FAIL: $1" >&2
  echo "--- output ---" >&2
  echo "$out" >&2
  echo "--- stderr ---" >&2
  cat "$err" >&2
  exit 1
}

err=$(mktemp)
trap 'rm -f "$err"' EXIT
# stderr (Spark logs) goes to a file: interleaved with stdout it can glue onto a RESULT line
out=$(docker run --rm -e HOME=/tmp/elsewhere -v "$here/job.py:/tmp/job.py:ro" "$image" bash -c \
  'id -u && python -V && /opt/spark/bin/spark-submit --master local[2] --conf spark.ui.enabled=false --conf spark.sql.execution.arrow.pyspark.enabled=true /tmp/job.py' 2>"$err") \
  || fail "job run exited non-zero"

grep -qx '185' <<<"$out" || fail "uid is not 185"
grep -q "^Python ${python_version//./\\.}\\." <<<"$out" || fail "python is not ${python_version}"
grep -qx 'RESULT sum 499500' <<<"$out" || fail "missing RESULT sum 499500"
grep -qx "RESULT arrow 6 python ${python_version}" <<<"$out" || fail "missing RESULT arrow 6 python ${python_version}"
grep -qx 'RESULT udf 20' <<<"$out" || fail "missing RESULT udf 20"

out=$(docker run --rm "$image" python -c "import pandas, pyarrow" 2>&1) || fail "pandas/pyarrow import failed"

out=$(docker run --rm "$image" driver 2>&1 || true)
grep -q 'Missing application resource' <<<"$out" || fail "entrypoint did not print 'Missing application resource'"

echo "OK $image size=$(docker image inspect -f '{{.Size}}' "$image") bytes"
