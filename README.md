# spark-images

[![publish](https://github.com/sdaberdaku/spark-images/actions/workflows/publish.yml/badge.svg)](https://github.com/sdaberdaku/spark-images/actions/workflows/publish.yml)

Apache Spark images with Python, pandas and pyarrow, published to `ghcr.io/sdaberdaku/spark`. They are meant as a drop-in replacement for the stock `spark` image wherever it runs: locally with Docker, on Kubernetes, as a Spark Connect server or in a standalone cluster. The stock entrypoint and decommission script are kept, so anything that works with the stock image works here.

The final stage is the official `python:<python>-slim-bookworm` image. A JRE is copied from `eclipse-temurin:<java>-jre-jammy`, and `/opt/spark`, `/opt/entrypoint.sh` and `/opt/decom.sh` are copied from the stock `spark:<spark>-scala<scala>-java<java>-ubuntu` image. pandas and pyarrow are installed with pip. Spark runs as user `spark` (uid 185).

## Tags

Each image has three tags: `<spark>-python<python>` (for example `4.2.0-python3.14`), `<major.minor>-python<python>` (`4.2-python3.14`, which follows the latest patch release) and the dated tag described under Rebuilds.

| Spark | Scala | Java | Python |
| ----- | ----- | ---- | ------ |
| 3.5.9 | 2.12  | 17   | 3.11 |
| 4.0.4 | 2.13  | 21   | 3.11, 3.12, 3.13 |
| 4.1.3 | 2.13  | 21   | 3.11, 3.12, 3.13, 3.14 |
| 4.2.0 | 2.13  | 21   | 3.11, 3.12, 3.13, 3.14 |

Spark 3.5.9 with Python 3.12 is not published. PySpark 3.5 imports `distutils`, which Python 3.12 removed, so `createDataFrame` from pandas fails (checked with `test/smoke.sh`).

```bash
docker pull ghcr.io/sdaberdaku/spark:4.2.0-python3.14
```

## Usage

Locally with Docker:

```bash
docker run --rm -v "$PWD/job.py:/tmp/job.py:ro" ghcr.io/sdaberdaku/spark:4.2.0-python3.14 \
  /opt/spark/bin/spark-submit --master 'local[2]' /tmp/job.py
```

Spark on Kubernetes, with the image used for both driver and executors. The job file is baked into the image, so build an image `FROM` this one that copies `job.py` to `/opt/spark/work-dir/`:

```bash
spark-submit \
  --master k8s://https://<api-server> \
  --deploy-mode cluster \
  --conf spark.kubernetes.container.image=ghcr.io/sdaberdaku/spark:4.2.0-python3.14 \
  local:///opt/spark/work-dir/job.py
```

Spark Connect server (Spark 4.x, default port 15002):

```bash
docker run --rm -p 15002:15002 -e SPARK_NO_DAEMONIZE=1 ghcr.io/sdaberdaku/spark:4.2.0-python3.14 \
  /opt/spark/sbin/start-connect-server.sh
```

Spark 4 images bundle the Connect server in the main distribution. On 3.5 add `--packages org.apache.spark:spark-connect_2.12:3.5.9`. `SPARK_NO_DAEMONIZE=1` keeps the start script in the foreground so the container stays up.

Standalone cluster:

```bash
docker run -d --name master --network host ghcr.io/sdaberdaku/spark:4.2.0-python3.14 \
  /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master
docker run -d --network host ghcr.io/sdaberdaku/spark:4.2.0-python3.14 \
  /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://localhost:7077
```

## Differences from the stock image

- The base is Debian slim from the official `python` image instead of Ubuntu.
- It contains a JRE instead of a JDK.
- Python lives in `/usr/local`, and `PYSPARK_PYTHON` points to it.
- `krb5-user`, `net-tools`, `wget` and `gnupg2` are not installed.
- Measured sizes on disk: 1.76 GB for 4.2.0 with Python 3.14, 1.47 GB for 3.5.9 with Python 3.11.

## Extending with jars

```dockerfile
FROM ghcr.io/sdaberdaku/spark:4.2.0-python3.14
ADD https://repo1.maven.org/maven2/org/example/lib/1.0/lib-1.0.jar /opt/spark/jars/
```

The `spark` user owns `/opt/spark`. If you use `ADD` with a URL, add `--chown=spark:spark` or switch to `USER root` for the step.

## Rebuilds and dated tags

The images are rebuilt weekly so that base image and OS package updates are picked up. Each rebuild also gets a dated tag of the form `<spark>-python<python>-<YYYYMMDD>`. The undated tags always point to the latest build. Every row is smoke-tested before it is pushed, so a row that fails the test keeps its previous image.

GitHub disables scheduled workflows after 60 days without repository activity. A commit or a manual run of the Publish workflow enables the schedule again.

## Adding a row

Add a Spark version, or a Python version to an existing entry, in `images.json`, then build and run the smoke test:

```bash
docker build --build-arg SPARK_VERSION=4.2.0 --build-arg SCALA_VERSION=2.13 \
  --build-arg JAVA_VERSION=21 --build-arg PYTHON_VERSION=3.14 -t spark-local:4.2.0-python3.14 .
bash test/smoke.sh spark-local:4.2.0-python3.14 3.14
```

The smoke test checks the uid, the Python version, a Spark SQL job, an Arrow conversion, an RDD job with a Python lambda, the pandas and pyarrow imports and the stock entrypoint.

## License

Apache 2.0. See `LICENSE`.
