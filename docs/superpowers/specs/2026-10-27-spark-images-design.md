# spark-images: stock Apache Spark images with a chosen Python version

- Status: approved 2026-10-27
- Repo: `sdaberdaku/spark-images` (public). Image: `ghcr.io/sdaberdaku/spark`.

## Intent

The official `spark:<version>-python3` images carry the Python of their Ubuntu base (3.10 on jammy). PySpark
requires the same Python minor on the driver and on every executor, so anyone running a driver on a newer Python
(an Airflow worker on 3.12, a notebook on 3.14, a Spark Connect client) needs executor images with that exact
Python. This project publishes them: the stock Spark image plus one uv-managed CPython, nothing else.

## Goals

1. `ghcr.io/sdaberdaku/spark:<spark>-python<python>` for the latest patch of every Spark minor from 3.5 up, with
   the Python versions that PySpark line supports (uv has no 3.10 reason to exist here: the stock `-python3`
   images already ship 3.10):
   - 3.5.9 (Scala 2.12, Java 17): Python 3.11, 3.12 (3.12 is not in PySpark 3.5's classifiers; the smoke test
     decides whether the row stays)
   - 4.0.4 (Scala 2.13, Java 21): Python 3.11, 3.12, 3.13
   - 4.1.3 (Scala 2.13, Java 21): Python 3.11, 3.12, 3.13, 3.14
   - 4.2.0 (Scala 2.13, Java 21): Python 3.11, 3.12, 3.13, 3.14
   amd64 and arm64. Each build also pushes a minor-level tag `<major.minor>-python<python>` and a dated tag
   `<spark>-python<python>-<YYYYMMDD>` for pinning. Patch bumps are a one-line change in `images.json`.
2. Contents, built in stages so the final image is lean: `/opt/spark`, `/opt/entrypoint.sh` and `/opt/decom.sh`
   copied from the stock `spark:<spark>-scala<scala>-java<java>-ubuntu` image; CPython from uv's
   python-build-standalone in `/opt/python` (static library, test suite, idlelib and tkinter removed, no compiled
   bytecode); a venv in `/opt/venv` with `pandas` and `pyarrow` (Arrow and pandas UDFs work out of the box); final
   stage `eclipse-temurin:<java>-jre-jammy` (a JRE, the stock image ships a full JDK) with the stock image's apt
   packages minus krb5-user, net-tools, wget and gnupg2, the same `spark` user (uid 185), `WORKDIR
   /opt/spark/work-dir`, `ENTRYPOINT /opt/entrypoint.sh`, `PYSPARK_PYTHON` and `PYSPARK_DRIVER_PYTHON` set to the
   venv. No `uv` in the final image. Works as a Spark on Kubernetes executor, driver and Spark Connect server
   image. Measured on 4.2.0 / Python 3.14: 1.9 GB on disk and 676 MB compressed, against 2.4 GB / 851 MB for the
   single-stage build on the stock image.
3. A smoke test that runs a PySpark job in the built image (DataFrame aggregate, Arrow `toPandas`, an RDD `map`
   through a Python worker) on every pull request, for every row, on amd64.
4. Published on merge to `main`, weekly (picks up Python patch releases and base image updates) and on demand.

## Non-goals

- Extra jars (Iceberg, Delta, cloud SDKs, JDBC drivers): users extend the image. The README shows how.
- Python packages beyond pandas and pyarrow.
- Spark before 3.5.
- More than one Scala or Java variant per Spark minor (the defaults above).

## Constraints

- One Dockerfile; the matrix lives in `images.json`. Build args `SPARK_VERSION`, `SCALA_VERSION`, `JAVA_VERSION`,
  `PYTHON_VERSION`, `UV_VERSION`.
- Image labels `org.opencontainers.image.source`, `.licenses=Apache-2.0`, `.description`.
- Workflows use `GITHUB_TOKEN` only (`packages: write`); no personal tokens.
- `main` protected: pull request, `ci-ok`, linear history. Drafts do not run CI.
- No organisation-specific registries, names or accounts anywhere.

## Left to the builder

- Exact smoke job assertions beyond the three listed; how the weekly run skips rows whose inputs did not change
  (optional, a full rebuild is acceptable).
