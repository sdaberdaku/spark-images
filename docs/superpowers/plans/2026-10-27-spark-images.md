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
- README: what the images are, the tag table, pull command, usage as a drop-in for the stock image (local `docker run` with `spark-submit`, Spark on Kubernetes via `spark.kubernetes.container.image`, Spark Connect server, standalone cluster), what differs from the stock image (Debian slim base from the official python image, JRE instead of JDK, Python in `/usr/local`, no krb5-user/net-tools/wget/gnupg2, measured sizes), how to extend with jars (`FROM ghcr.io/sdaberdaku/spark:4.2.0-python3.14` + `ADD` into `/opt/spark/jars/`), the weekly rebuild and dated tags, how to add a row.

- [ ] **Step 1: Write the files**

- [ ] **Step 2: Build and smoke one row locally**

Run: `docker build --build-arg SPARK_VERSION=4.2.0 --build-arg PYTHON_VERSION=3.14 -t spark-local:4.2.0-python3.14 . && bash test/smoke.sh spark-local:4.2.0-python3.14 3.14`
Expected: uid 185, `Python 3.14.x`, three `RESULT` lines, entrypoint check, size about 1.8 GB, exit 0

- [ ] **Step 3: Build and smoke the 3.5.9 rows (both Pythons)**

Run: `for py in 3.11 3.12; do docker build --build-arg SPARK_VERSION=3.5.9 --build-arg SCALA_VERSION=2.12 --build-arg JAVA_VERSION=17 --build-arg PYTHON_VERSION=$py -t spark-local:3.5.9-python$py . && bash test/smoke.sh spark-local:3.5.9-python$py $py; done`
Expected: exit 0 for 3.11; for 3.12 either exit 0 (keep the row) or a clear failure (remove `3.12` from the 3.5.9 row, note it in the README)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: Spark image on the official python base, matrix and smoke test"
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
- Modify: `README.md` (badge; note that the weekly rebuild smoke-tests every row before pushing, that GitHub disables cron workflows after 60 days without repository activity so a commit or a manual run re-enables it, and the tag list including `<major.minor>-python<python>` next to the other two; also the deferred Task 1 minors: rephrase "Debian slim, not Ubuntu" / "a JRE, not a JDK" as "instead of", say in the Kubernetes example that the job file is baked into the image)

**Interfaces:**
- Triggers: `push: branches: [main]`, `schedule: cron "0 4 * * 1"`, `workflow_dispatch`. `permissions: contents: read, packages: write`. `concurrency: publish`.
- Job `plan` as in CI (no draft condition). Job `publish`: matrix as in CI, `fail-fast: false`, `timeout-minutes: 60`: checkout, `docker/setup-qemu-action@v3`, `docker/setup-buildx-action@v3`, `docker/login-action@v3` (`registry: ghcr.io`, `username: ${{ github.actor }}`, `password: ${{ secrets.GITHUB_TOKEN }}`), a step that sets `DATE=$(date -u +%Y%m%d)`; then, per row, the smoke gate before any push: `docker/build-push-action@v6` with `load: true`, `push: false`, `platforms: linux/amd64`, tag `spark-smoke:${spark}-python${python}`, gha cache scopes as in CI; `bash test/smoke.sh spark-smoke:${spark}-python${python} ${python}`; only then `docker/build-push-action@v6` with `push: true`, `platforms: linux/amd64,linux/arm64` (amd64 layers come from the cache just filled), tags `ghcr.io/sdaberdaku/spark:${spark}-python${python}`, `ghcr.io/sdaberdaku/spark:${spark%.*}-python${python}` (minor-level) and `ghcr.io/sdaberdaku/spark:${spark}-python${python}-${DATE}`, same cache scopes, `provenance: false` (keeps the manifest a plain multi-arch index). A row whose smoke test fails pushes nothing; other rows are unaffected.
- Branch protection via `gh api -X PUT repos/sdaberdaku/spark-images/branches/main/protection`: `required_status_checks: {strict: true, contexts: ["ci-ok"]}`, `enforce_admins: true`, `required_pull_request_reviews: null`, `restrictions: null`, `required_linear_history: true`, `allow_force_pushes: true`, `allow_deletions: false`. Repo merge settings are already set (squash only, delete branch on merge); merge with `gh pr merge --squash`.

- [ ] **Step 1: Write the workflow, lint it, commit, push, wait for `ci-ok`**

- [ ] **Step 2: Apply protection, merge with `gh pr merge --squash`, watch the first publish run**

Run: `gh run watch` on the `Publish` run.
Expected: 13 rows pushed; `docker manifest inspect ghcr.io/sdaberdaku/spark:4.2.0-python3.14` lists amd64 and arm64 (may need the package to be public first; report either way).

- [ ] **Step 3: Report** the run URL, the tag list, and whether the package `spark` is public or still needs the visibility switch in the package settings.

---

### Task 4: Cleanup of old image versions

**Files:**
- Modify: `.github/workflows/publish.yml`, `README.md` (retention policy sentence)

**Interfaces:**
- Job `cleanup` in `publish.yml`: `needs: publish`, `if: always()` (runs even when a row failed), `permissions: packages: write`, single step `dataaxiom/ghcr-cleanup-action@v1` with `token: ${{ secrets.GITHUB_TOKEN }}`, `owner: sdaberdaku`, `package: spark`, `older-than: 90 days`, `delete-tags: "*-20[0-9][0-9][0-1][0-9][0-3][0-9]"` (dated tags only), `exclude-tags` left empty (the pattern already excludes floating tags), `delete-untagged: true` (the action keeps untagged child manifests that a tagged multi-arch index still references), `dry-run: false`. Check the action's README for the exact input names before writing them; if an input differs, use the documented one and say so in the report.
- Policy stated in the README under a "Retention" heading: floating tags `<spark>-python<python>` and `<major.minor>-python<python>` are never deleted; dated tags are kept for 90 days; untagged versions are removed when nothing references them.

- [ ] **Step 1: Add the job and the README sentence; lint the workflow**

Run: `uvx --from actionlint-py actionlint .github/workflows/publish.yml`
Expected: no findings

- [ ] **Step 2: Commit, push, wait for `ci-ok`, merge with `gh pr merge --squash`, watch the publish run including `cleanup`**

Expected: `cleanup` completes without deleting anything on the first run (nothing older than 90 days); its log lists the versions it considered.

- [ ] **Step 3: Report** the run URL and what the cleanup log shows.

---

### Task 5: Renovate, pinned inputs, no cron

**Files:**
- Create: `renovate.json`, `requirements.txt`
- Modify: `images.json`, `Dockerfile`, `.github/workflows/publish.yml`, `.github/workflows/ci.yml` (if it reads python from images.json, nothing changes; verify), `README.md`

**Interfaces:**
- `images.json`: Python entries become full versions, the current patch of each line as published on Docker Hub for `python:<ver>-slim-bookworm` (look them up with `curl -s "https://hub.docker.com/v2/repositories/library/python/tags?page_size=100&name=-slim-bookworm"`): e.g. `"python": ["3.11.x", "3.12.x", "3.13.x", "3.14.x"]`.
- `Dockerfile`: `FROM python:${PYTHON_VERSION}-slim-bookworm` unchanged in shape (now a full version); pandas and pyarrow installed with `pip install --no-cache-dir --no-compile -r /tmp/requirements.txt` from `COPY requirements.txt /tmp/requirements.txt`; `requirements.txt` pins `pandas==<current>` and `pyarrow==<current>` (current PyPI versions).
- `plan` jobs (ci.yml and publish.yml): the jq expansion adds `python_minor` (`.python | split(".")[:2] | join(".")`) next to `python`; the smoke test receives `python_minor`... no: `test/smoke.sh IMAGE PYTHON_VERSION` asserts the `Python X.Y.` prefix, so pass the full version and change the assertion to the exact `Python <full>` string (update smoke.sh accordingly).
- publish.yml tags per row: `ghcr.io/sdaberdaku/spark:${spark}-python${python_minor}`, `ghcr.io/sdaberdaku/spark:${spark}-python${python}` (full), `ghcr.io/sdaberdaku/spark:${minor}-python${python_minor}`, `ghcr.io/sdaberdaku/spark:${spark}-python${python_minor}-${DATE}`. Remove the `schedule:` trigger; keep `push: branches: [main]` and `workflow_dispatch`. The cleanup job's dated-tag pattern must still match the dated tag form.
- `renovate.json` (schema `https://docs.renovatebot.com/renovate-schema.json`): `extends: ["config:recommended", ":dependencyDashboard"]`; `enabledManagers: ["dockerfile", "github-actions", "pip_requirements", "custom.regex"]`; one custom regex manager on `images.json` matching `"spark": "(?<currentValue>\d+\.\d+\.\d+)"` with `datasourceTemplate: "docker"`, `depNameTemplate: "spark"`, `versioningTemplate: "docker"`; another matching each full Python version inside the `"python": [...]` arrays with `datasourceTemplate: "docker"`, `depNameTemplate: "python"` (both regexes anchored so they cannot match each other's values); `packageRules`: `{matchDepNames: ["spark", "python"], matchUpdateTypes: ["minor", "major"], enabled: false}` (patch-only per row), `{matchUpdateTypes: ["patch", "pin", "digest"], automerge: true}`, `{matchManagers: ["github-actions"], automerge: true}`, `{matchManagers: ["pip_requirements"], matchUpdateTypes: ["minor", "patch"], automerge: true}`; `platformAutomerge: true`; `schedule: ["before 6am on monday"]`; `prConcurrentLimit: 4`; `labels: ["dependencies"]`. The `dockerfile` manager also sees `ARG` defaults; leave `eclipse-temurin:${JAVA_VERSION}-jre-jammy` and the stock Spark `FROM` alone (they follow ARGs, Renovate reports them as unversioned or tracks the ARG defaults; disable with a packageRule on `matchDepNames: ["eclipse-temurin", "spark"]` for the dockerfile manager only, since Spark is handled by images.json).
- README: replace the weekly-rebuild wording with: images are rebuilt when a Renovate pull request bumps Spark, Python, pandas or pyarrow (patch-only per row; a new Spark or Python minor is a manual row); tag table gains the full-Python tag; the retention paragraph stays; remove the 60-day cron note; add the accepted gap (OS-level fixes without tag changes arrive with the next rebuild).

- [ ] **Step 1: Make the changes on a branch `feat/renovate-pinned-inputs`; lint workflows; validate `renovate.json` with `npx --yes renovate-config-validator renovate.json` (node is available; if not, `docker run --rm -v "$PWD":/w -w /w renovate/renovate renovate-config-validator`)**

- [ ] **Step 2: Build and smoke one row locally with the full Python version** (`docker build --build-arg SPARK_VERSION=4.2.0 --build-arg PYTHON_VERSION=<full 3.14> -t spark-local:x . && bash test/smoke.sh spark-local:x <full 3.14>`)

- [ ] **Step 3: Commit, push, PR, `ci-ok`, squash-merge, watch the publish run (all rows, cleanup), verify `docker manifest inspect ghcr.io/sdaberdaku/spark:4.2.0-python3.14.<x>` and `...:4.2.0-python3.14`**

- [ ] **Step 4: Report** the run URL, the new tag list for one row, and the Renovate config summary. The Mend Renovate app installation on the account is the owner's step; say so in the report and in the README's development section.

---

### Task 6: Discovery of new Spark minor and major lines

**Files:**
- Create: `.github/workflows/discover.yml`, `scripts/discover.py`
- Modify: `README.md` (one paragraph under the rebuild section), `renovate.json` (nothing unless the new file needs an exclusion)

**Interfaces:**
- `scripts/discover.py` (stdlib only, Python 3.12 on the runner): reads `images.json`; queries Docker Hub `https://hub.docker.com/v2/repositories/library/spark/tags?page_size=100&name=-ubuntu` (follow `next` pages) for tags matching `^(\d+)\.(\d+)\.(\d+)-scala(\d+\.\d+)-java(\d+)-ubuntu$`; groups by `major.minor`; ignores lines below 3.5 and lines already in `images.json`; for each new line picks the highest patch, Scala `2.13` when available (else the highest), Java `21` when available (else the highest), and the `python` list of the newest existing row; appends the rows in version order; writes `images.json` back (2-space indent, trailing newline); prints the added `major.minor` lines one per line; exit 0 in every case. A `--dry-run` flag prints without writing. Unit-tested in-process with a fake tag list (a small `tests/test_discover.py` using `unittest`, run with `python -m unittest`).
- `discover.yml`: `on: schedule: cron "0 5 * * *"` (one API call a day, no builds) and `workflow_dispatch`; `permissions: contents: write, pull-requests: write, actions: write`; steps: checkout, `actions/setup-python@v7` 3.12, run `python scripts/discover.py`, capture the output; if empty, stop; else `git switch -c spark/<lines joined by ->` (e.g. `spark/4.3`), commit `feat(images): add Spark 4.3` as the github-actions bot (`github-actions[bot]` name and `41898282+github-actions[bot]@users.noreply.github.com` email), push, `gh pr create` with a plain-prose body listing the new rows and that rows failing the smoke test must be trimmed by hand, `gh workflow run ci.yml --ref <branch>` (a PR opened with `GITHUB_TOKEN` does not trigger `pull_request` workflows; the dispatched run reports `ci-ok` on the branch head commit, which is what the protection checks), then `gh pr merge --auto --squash`. Idempotent: if a branch or open PR for that line already exists, do nothing.
- Repo setting `allow auto-merge` is already enabled.
- README paragraph: new Spark minor and major lines are discovered daily and arrive as a pull request that auto-merges when every row passes the smoke test; a line whose Python versions are not all supported needs a hand edit of the row before merge.

- [ ] **Step 1: Write `scripts/discover.py` with its unittest first (fake tags: existing 4.2.0 row, Docker Hub offering 4.2.1, 4.3.0, 5.0.0 with java21/25 and scala2.13; expect rows 4.3.0 and 5.0.0 added with java 21 and python copied, 4.2.1 ignored because the 4.2 line exists); run `python -m unittest tests/test_discover.py`**

- [ ] **Step 2: Run `python scripts/discover.py --dry-run` against the live Docker Hub; expected: no new lines today (4.2 is the newest)**

- [ ] **Step 3: Write `discover.yml`, lint it, commit on the Task 5 branch (same PR) or a follow-up branch if Task 5 already merged; after merge, `gh workflow run discover.yml` once and confirm it exits cleanly with nothing to add**

- [ ] **Step 4: Report** the run URL and the dry-run output.
