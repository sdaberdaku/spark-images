ARG SPARK_VERSION=4.2.0
ARG SCALA_VERSION=2.13
ARG JAVA_VERSION=21
ARG PYTHON_VERSION=3.14.10

FROM spark:${SPARK_VERSION}-scala${SCALA_VERSION}-java${JAVA_VERSION}-ubuntu AS spark
FROM eclipse-temurin:${JAVA_VERSION}-jre-jammy AS jre

FROM python:${PYTHON_VERSION}-slim
ARG SPARK_VERSION
ARG PYTHON_VERSION
ARG spark_uid=185

COPY requirements.txt /tmp/requirements.txt

RUN set -eux; \
    groupadd --system --gid=${spark_uid} spark; \
    useradd --system --uid=${spark_uid} --gid=spark spark; \
    apt-get update; \
    apt-get install -y --no-install-recommends bash tini libc6 libpam-modules libnss3 procps gosu libnss-wrapper; \
    rm -rf /var/lib/apt/lists/*; \
    pip install --no-cache-dir --no-compile -r /tmp/requirements.txt; \
    rm /tmp/requirements.txt; \
    find /usr/local/lib/python3* -name '__pycache__' -type d -prune -exec rm -rf '{}' +; \
    mkdir -p /opt/spark/work-dir /home/spark; \
    chown -R spark:spark /opt/spark /home/spark; \
    chmod g+w /opt/spark/work-dir

COPY --from=jre /opt/java/openjdk /opt/java/openjdk
COPY --from=spark --chown=spark:spark /opt/spark /opt/spark
COPY --from=spark /opt/entrypoint.sh /opt/decom.sh /opt/

ENV JAVA_HOME=/opt/java/openjdk \
    SPARK_HOME=/opt/spark \
    PATH="/opt/java/openjdk/bin:/opt/spark/bin:${PATH}" \
    PYSPARK_PYTHON=/usr/local/bin/python \
    PYSPARK_DRIVER_PYTHON=/usr/local/bin/python \
    HOME=/home/spark

LABEL org.opencontainers.image.source=https://github.com/sdaberdaku/spark-images \
      org.opencontainers.image.licenses=Apache-2.0 \
      org.opencontainers.image.description="Apache Spark ${SPARK_VERSION} with Python ${PYTHON_VERSION}"

WORKDIR /opt/spark/work-dir
ENTRYPOINT ["/opt/entrypoint.sh"]
USER spark
