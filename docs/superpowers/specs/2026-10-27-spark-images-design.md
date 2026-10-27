# spark-images: stock Apache Spark images with a chosen Python version

- Status: approved 2026-10-27
- Repo: `sdaberdaku/spark-images` (public). Image: `ghcr.io/sdaberdaku/spark`.

## Intent

The official `spark:<version>-python3` images carry the Python of their Ubuntu base (3.10 on jammy). PySpark
requires the same Python minor on the driver and on every executor, so anyone running a driver on a newer Python
(an Airflow worker on 3.12, a notebook on 3.14, a Spark Connect client) needs executor images with that exact
Python. This project publishes them: the official python image plus a JRE and the stock Spark distribution, nothing else.

## Goals

1. `ghcr.io/sdaberdaku/spark` images for the latest patch of every Spark minor from 3.5 up, on the Python versions
   each line supports (3.10 is left out: the stock `-python3` images already ship it). The matrix lives in
   `images.json`:
   - 3.5.9 (Scala 2.12, Java 17): Python 3.11 (3.12 is not published: PySpark 3.5 imports `distutils`, which
     Python 3.12 removed, and the smoke test fails)
   - 4.0.4 (Scala 2.13, Java 21): Python 3.11, 3.12, 3.13
   - 4.1.3 (Scala 2.13, Java 21): Python 3.11 to 3.15
   - 4.2.0 (Scala 2.13, Java 21): Python 3.11 to 3.15

   Python versions in `images.json` are full patch versions (`3.14.10`). Each row has three tags:
   `<spark>-python<minor>` (`4.2.0-python3.14`), `<spark>-python<full>` (`4.2.0-python3.14.10`) and
   `<major.minor>-python<minor>` (`4.2-python3.14`). There are no dated tags: with every input pinned, the image
   digest is the reproducible pin. Images are published for amd64 and arm64.
2. Contents, built in stages so the final image is lean: the final stage is the official `python:<python>-slim`
   image; the JRE is copied from `eclipse-temurin:<java>-jre-jammy` (the stock Spark image ships a full JDK);
   `/opt/spark`, `/opt/entrypoint.sh` and `/opt/decom.sh` are copied from the stock
   `spark:<spark>-scala<scala>-java<java>-ubuntu` image; `pandas` and `pyarrow` are installed with pip from a
   pinned `requirements.txt`, without compiled bytecode; the stock image's apt packages minus `krb5-user`,
   `net-tools`, `wget` and `gnupg2`; the same `spark` user (uid 185), `WORKDIR /opt/spark/work-dir`,
   `ENTRYPOINT /opt/entrypoint.sh`; `PYSPARK_PYTHON` and `PYSPARK_DRIVER_PYTHON` set to `/usr/local/bin/python`.
   The image works as a drop-in replacement for the stock image wherever it runs. Measured on 4.2.0 with
   Python 3.14: 643 MB compressed on amd64 and 638 MB on arm64, 1.76 GB on disk.
3. A smoke test (`test/smoke.sh`) that runs PySpark jobs in the built image (DataFrame aggregate, Arrow
   `toPandas`, an RDD `map` through a Python worker). CI runs it for every row on amd64 and arm64 (28 build jobs),
   and the publish workflow runs it on amd64 before pushing.
4. Updates without a cron. Renovate (Mend app) opens one weekly pull request with all non-major updates (Spark
   and Python patches per row, pandas, pyarrow, GitHub Actions); it merges itself once `ci-ok` is green. A daily
   Discover workflow compares Docker Hub with `images.json` and opens an auto-merging pull request for new Spark
   minor or major lines and for new Python lines (added to the rows of the newest Spark major that carry the
   previous newest Python line). It also rebases or closes a stuck discovery pull request and dispatches the
   publish workflow when the latest `images.json` commit has no publish run.
5. Published on pushes to `main` that touch `Dockerfile`, `images.json`, `requirements.txt`, `test/**` or the
   publish workflow, and on demand from `main`. Untagged versions older than 30 days are deleted after each
   publish run, so a digest pin stays pullable for at least 30 days after its tag moves; tags are never deleted.
   Accepted gap: Debian security fixes that land in `python:slim` or `eclipse-temurin` without a tag change reach
   the images only with the next rebuild.

## Non-goals

- Extra jars (Iceberg, Delta, cloud SDKs, JDBC drivers): users extend the image. The README shows how.
- Python packages beyond pandas and pyarrow.
- Spark before 3.5.
- More than one Scala or Java variant per Spark minor.
- A scheduled rebuild.

## Constraints

- One Dockerfile; the matrix lives in `images.json`. Build args `SPARK_VERSION`, `SCALA_VERSION`, `JAVA_VERSION`,
  `PYTHON_VERSION`.
- Image labels `org.opencontainers.image.source`, `.licenses=Apache-2.0`, `.description`.
- Workflows use `GITHUB_TOKEN` only (`packages: write`); no personal tokens.
- `main` protected: pull request, `ci-ok`, linear history, squash merges. Drafts do not run CI.
- No organisation-specific registries, names or accounts anywhere.

## Left to the builder

- Exact smoke job assertions beyond the three listed.
