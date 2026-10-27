# spark-images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `ghcr.io/sdaberdaku/spark:<spark>-python<python>` images (official python-slim base + JRE + stock Spark + pandas/pyarrow) for the latest patch of every Spark minor from 3.5 up, on the Python versions each line supports, tested on every PR and rebuilt weekly.

**Architecture:** One parameterised multi-stage Dockerfile (final stage `python:<python>-slim-bookworm`, JRE copied from eclipse-temurin, `/opt/spark` copied from the stock Spark image), a JSON matrix, a bash smoke test that runs a PySpark job inside the image, and two workflows: CI (build amd64 + smoke per row, `ci-ok` gate) and Publish (buildx multi-arch push on `main`, cron and dispatch).

**Tech Stack:** Docker buildx, official python and eclipse-temurin images, GitHub Actions, bash.

**Spec:** `docs/superpowers/specs/2026-10-27-spark-images-design.md`

## Global Constraints

- Image `ghcr.io/sdaberdaku/spark`, tags `<spark>-python<python>`, `<major.minor>-python<python>` and `<spark>-python<python>-<YYYYMMDD>`; platforms `linux/amd64,linux/arm64` on publish, amd64 only in CI.
- Matrix rows (`images.json`): `3.5.9` scala `2.12` java `17` python `[3.11, 3.12]`; `4.0.4` scala `2.13` java `21` python `[3.11, 3.12, 3.13]`; `4.1.3` scala `2.13` java `21` python `[3.11, 3.12, 3.13, 3.14]`; `4.2.0` scala `2.13` java `21` python `[3.11, 3.12, 3.13, 3.14]`. 13 images. If the 3.5.9 / 3.12 smoke test fails, drop that Python from the row and say so in the README.
- Sources: `spark:${SPARK_VERSION}-scala${SCALA_VERSION}-java${JAVA_VERSION}-ubuntu` (Spark files), `eclipse-temurin:${JAVA_VERSION}-jre-jammy` (JRE), `python:${PYTHON_VERSION}-slim-bookworm` (final base); pip packages exactly `pandas pyarrow` (unpinned, `--no-compile`).
- No organisation-specific registries, names or accounts.
- Commit style `type(scope): subject`.

## Review Focus

1. The JRE copied from a jammy image must run on bookworm (glibc 2.36 is newer than jammy's 2.35, so it does; a future base change could break it). Covered by the smoke test's `java -version` and spark-submit in Task 1.
2. `PYSPARK_PYTHON` must survive a pod spec that mounts over `/home/spark` (Python lives in `/usr/local`). Covered by the Task 1 smoke test running with `HOME=/tmp/elsewhere`.
3. The Arrow path must work (pyarrow wheel for that Python and arch exists). Covered by the smoke job's `toPandas`.
4. The Python worker path (RDD map) must work: `pyspark.zip` and py4j from `$SPARK_HOME/python/lib` on `PYTHONPATH`. Covered by the smoke job.
5. The weekly publish must not push a half-built matrix: each row is its own job, a failed row fails the workflow and leaves the other rows published (acceptable, tags are per row). Documented in the README.

---

### Task 1: Dockerfile, matrix and smoke test

**Files:**
- Create: `Dockerfile`, `images.json`, `test/job.py`, `test/smoke.sh`, `README.md`, `LICENSE` (Apache 2.0, copyright 2026 Sebastian Daberdaku), `.gitignore`

**Interfaces:**
- `Dockerfile`, three stages (verified 2026-10-27 outside the repo on 4.2.0 / Python 3.14.10: smoke job green, uid 185, entrypoint runs, 1.76 GB / 641 MB gzip):
  - `ARG SPARK_VERSION=4.2.0`, `ARG SCALA_VERSION=2.13`, `ARG JAVA_VERSION=21`, `ARG PYTHON_VERSION=3.14` before the first `FROM`.
  - `FROM spark:${SPARK_VERSION}-scala${SCALA_VERSION}-java${JAVA_VERSION}-ubuntu AS spark`; `FROM eclipse-temurin:${JAVA_VERSION}-jre-jammy AS jre`.
  - `FROM python:${PYTHON_VERSION}-slim-bookworm` (final): `ARG spark_uid=185`; `RUN set -eux; groupadd --system --gid=${spark_uid} spark; useradd --system --uid=${spark_uid} --gid=spark spark; apt-get update; apt-get install -y --no-install-recommends bash tini libc6 libpam-modules libnss3 procps gosu libnss-wrapper; rm -rf /var/lib/apt/lists/*; pip install --no-cache-dir --no-compile pandas pyarrow; find /usr/local/lib/python3* -name '__pycache__' -type d -prune -exec rm -rf '{}' +; mkdir -p /opt/spark/work-dir /home/spark; chown -R spark:spark /opt/spark /home/spark; chmod g+w /opt/spark/work-dir`; `COPY --from=jre /opt/java/openjdk /opt/java/openjdk`; `COPY --from=spark --chown=spark:spark /opt/spark /opt/spark`; `COPY --from=spark /opt/entrypoint.sh /opt/decom.sh /opt/`; `ENV JAVA_HOME=/opt/java/openjdk SPARK_HOME=/opt/spark PATH="/opt/java/openjdk/bin:/opt/spark/bin:${PATH}" PYSPARK_PYTHON=/usr/local/bin/python PYSPARK_DRIVER_PYTHON=/usr/local/bin/python HOME=/home/spark`; `LABEL org.opencontainers.image.source=https://github.com/sdaberdaku/spark-images org.opencontainers.image.licenses=Apache-2.0 org.opencontainers.image.description="Apache Spark ${SPARK_VERSION} with Python ${PYTHON_VERSION}"`; `WORKDIR /opt/spark/work-dir`; `ENTRYPOINT ["/opt/entrypoint.sh"]`; `USER spark`.
  - For Spark 3.5.9 the stock image's base is `eclipse-temurin:17-jammy`, so `JAVA_VERSION=17` gives `17-jre-jammy`; check that `/opt/entrypoint.sh` and `/opt/decom.sh` exist in that stock image too (they do in 3.5.x spark-docker).
- `images.json`: `[{"spark": "3.5.9", "scala": "2.12", "java": "17", "python": ["3.11", "3.12"]}, {"spark": "4.0.4", "scala": "2.13", "java": "21", "python": ["3.11", "3.12", "3.13"]}, {"spark": "4.1.3", "scala": "2.13", "java": "21", "python": ["3.11", "3.12", "3.13", "3.14"]}, {"spark": "4.2.0", "scala": "2.13", "java": "21", "python": ["3.11", "3.12", "3.13", "3.14"]}]`.
- `test/job.py`: prints `RESULT sum 499500` from `spark.range(1000).selectExpr("sum(id)")`, `RESULT arrow 6 python <major.minor>` from `spark.createDataFrame(pd.DataFrame({"x": [1, 2, 3]})).toPandas()` with `spark.sql.execution.arrow.pyspark.enabled=true`, `RESULT udf 20` from `spark.range(5).rdd.map(lambda r: r.id * 2).sum()`.
- `test/smoke.sh IMAGE PYTHON_VERSION`: `docker run --rm -e HOME=/tmp/elsewhere -v "$PWD/test/job.py:/tmp/job.py:ro" IMAGE bash -c 'id -u && python -V && /opt/spark/bin/spark-submit --master local[2] --conf spark.ui.enabled=false --conf spark.sql.execution.arrow.pyspark.enabled=true /tmp/job.py'`; asserts uid `185`, `Python PYTHON_VERSION.` prefix, the three `RESULT` lines, that `python -c "import pandas, pyarrow"` succeeds, and that `docker run --rm IMAGE driver` (the stock entrypoint) prints `Missing application resource` (proves the entrypoint runs). Prints the image size (`docker image inspect -f '{{.Size}}'`). Exit 1 with the captured output on any miss.
- README: what the images are, the tag table, pull command, Spark on Kubernetes usage (`spark.kubernetes.container.image`), what differs from the stock image (Debian slim base from the official python image, JRE instead of JDK, Python in `/usr/local`, no krb5-user/net-tools/wget/gnupg2, measured sizes), how to extend with jars (`FROM ghcr.io/sdaberdaku/spark:4.2.0-python3.14` + `ADD` into `/opt/spark/jars/`), the weekly rebuild and dated tags, how to add a row.

- [ ] **Step 1: Write the files**

- [ ] **Step 2: Build and smoke one row locally**

Run: `docker build --build-arg SPARK_VERSION=4.2.0 --build-arg PYTHON_VERSION=3.14 -t spark-local:4.2.0-python3.14 . && bash test/smoke.sh spark-local:4.2.0-python3.14 3.14`
Expected: uid 185, `Python 3.14.x`, three `RESULT` lines, entrypoint check, size about 1.8 GB, exit 0

- [ ] **Step 3: Build and smoke the 3.5.9 rows (both Pythons)**

Run: `for py in 3.11 3.12; do docker build --build-arg SPARK_VERSION=3.5.9 --build-arg SCALA_VERSION=2.12 --build-arg JAVA_VERSION=17 --build-arg PYTHON_VERSION=$py -t spark-local:3.5.9-python$py . && bash test/smoke.sh spark-local:3.5.9-python$py $py; done`
Expected: exit 0 for 3.11; for 3.12 either exit 0 (keep the row) or a clear failure (remove `3.12` from the 3.5.9 row, note it in the README)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: Spark image with uv-managed Python, matrix and smoke test"
```

---

### Task 2: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Triggers: `pull_request` `[opened, synchronize, reopened, ready_for_review]`, `workflow_dispatch`. `permissions: contents: read`.
- Job `plan`: `if: github.event_name != 'pull_request' || !github.event.pull_request.draft`; output `matrix` = `jq -c '[.[] | . as $r | .python[] | {spark: $r.spark, scala: $r.scala, java: $r.java, python: .}]' images.json`.
- Job `build`: `needs: plan`, `strategy.fail-fast: false`, `matrix.include: ${{ fromJson(needs.plan.outputs.matrix) }}`, `runs-on: ubuntu-latest`, `timeout-minutes: 30`: checkout, `docker/setup-buildx-action@v3`, `docker/build-push-action@v6` with `load: true`, `push: false`, `tags: spark-ci:${{ matrix.spark }}-python${{ matrix.python }}`, build args, `cache-from: type=gha,scope=${{ matrix.spark }}-${{ matrix.python }}`, `cache-to: type=gha,mode=max,scope=...`; then `bash test/smoke.sh spark-ci:... ${{ matrix.python }}`.
- Job `ci-ok`: `needs: [build]`, `if: always()`, fails unless `needs.build.result == 'success'`. Header comment explains that a draft PR shows `ci-ok` red on purpose.

- [ ] **Step 1: Write the workflow; run `uvx --from actionlint-py actionlint`**

- [ ] **Step 2: Commit, push, open a PR, mark ready, confirm all 13 rows and `ci-ok` green**

```bash
git add -A && git commit -m "ci: build and smoke every matrix row on pull requests"
git push -u origin HEAD && gh pr create --fill --draft && gh pr ready
```

---

### Task 3: Publish workflow, protection, merge

**Files:**
- Create: `.github/workflows/publish.yml`
- Modify: `README.md` (badge, note on the weekly rebuild)

**Interfaces:**
- Triggers: `push: branches: [main]`, `schedule: cron "0 4 * * 1"`, `workflow_dispatch`. `permissions: contents: read, packages: write`. `concurrency: publish`.
- Job `plan` as in CI (no draft condition). Job `publish`: matrix as in CI, `timeout-minutes: 60`: checkout, `docker/setup-qemu-action@v3`, `docker/setup-buildx-action@v3`, `docker/login-action@v3` (`registry: ghcr.io`, `username: ${{ github.actor }}`, `password: ${{ secrets.GITHUB_TOKEN }}`), a step that sets `DATE=$(date -u +%Y%m%d)`, `docker/build-push-action@v6` with `push: true`, `platforms: linux/amd64,linux/arm64`, tags `ghcr.io/sdaberdaku/spark:${spark}-python${python}`, `ghcr.io/sdaberdaku/spark:${spark%.*}-python${python}` (minor-level) and `ghcr.io/sdaberdaku/spark:${spark}-python${python}-${DATE}`, same gha cache scopes as CI, `provenance: false` (keeps the manifest a plain multi-arch index).
- Branch protection via `gh api -X PUT repos/sdaberdaku/spark-images/branches/main/protection`: `required_status_checks: {strict: true, contexts: ["ci-ok"]}`, `enforce_admins: true`, `required_pull_request_reviews: null`, `restrictions: null`, `required_linear_history: true`, `allow_force_pushes: true`, `allow_deletions: false`. `gh repo edit --enable-merge-commit=false --delete-branch-on-merge`.

- [ ] **Step 1: Write the workflow, lint it, commit, push, wait for `ci-ok`**

- [ ] **Step 2: Apply protection, merge with `gh pr merge --rebase`, watch the first publish run**

Run: `gh run watch` on the `Publish` run.
Expected: 13 rows pushed; `docker manifest inspect ghcr.io/sdaberdaku/spark:4.2.0-python3.14` lists amd64 and arm64 (may need the package to be public first; report either way).

- [ ] **Step 3: Report** the run URL, the tag list, and whether the package `spark` is public or still needs the visibility switch in the package settings.
