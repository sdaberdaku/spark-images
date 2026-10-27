# spark-images: stock Apache Spark images with a chosen Python version

- Status: approved 2026-10-27
- Repo: `sdaberdaku/spark-images` (public). Image: `ghcr.io/sdaberdaku/spark`.

## Intent

The official `spark:<version>-python3` images carry the Python of their Ubuntu base (3.10 on jammy). PySpark
requires the same Python minor on the driver and on every executor, so anyone running a driver on a newer Python
(an Airflow worker on 3.12, a notebook on 3.14, a Spark Connect client) needs executor images with that exact
Python. This project publishes them: the stock Spark image plus one uv-managed CPython, nothing else.

## Goals

1. `ghcr.io/sdaberdaku/spark:<spark>-python<python>` for Spark {4.1.2, 4.2.0} x Python {3.11, 3.12, 3.13, 3.14},
   amd64 and arm64. Each build also pushes a dated tag `<spark>-python<python>-<YYYYMMDD>` for pinning.
2. Contents: `FROM spark:<spark>-scala2.13-java21-ubuntu` (the Python-less stock image), CPython from uv's
   python-build-standalone in `/opt/python`, a venv in `/opt/venv` with `pandas` and `pyarrow` (Arrow and pandas
   UDFs work out of the box), `PYSPARK_PYTHON` and `PYSPARK_DRIVER_PYTHON` set to the venv, `uv` removed from the
   final image, `USER spark`. Works as a Spark on Kubernetes executor, driver and Spark Connect server image.
3. A smoke test that runs a PySpark job in the built image (DataFrame aggregate, Arrow `toPandas`, an RDD `map`
   through a Python worker) on every pull request, for every row, on amd64.
4. Published on merge to `main`, weekly (picks up Python patch releases and base image updates) and on demand.

## Non-goals

- Extra jars (Iceberg, Delta, cloud SDKs, JDBC drivers): users extend the image. The README shows how.
- Python packages beyond pandas and pyarrow.
- Spark 3.x.
- Scala 2.12 or Java 17 variants.

## Constraints

- One Dockerfile; the matrix lives in `images.json`. Build args `SPARK_VERSION`, `PYTHON_VERSION`, `UV_VERSION`.
- Image labels `org.opencontainers.image.source`, `.licenses=Apache-2.0`, `.description`.
- Workflows use `GITHUB_TOKEN` only (`packages: write`); no personal tokens.
- `main` protected: pull request, `ci-ok`, linear history. Drafts do not run CI.
- No organisation-specific registries, names or accounts anywhere.

## Left to the builder

- Exact smoke job assertions beyond the three listed; how the weekly run skips rows whose inputs did not change
  (optional, a full rebuild is acceptable).
