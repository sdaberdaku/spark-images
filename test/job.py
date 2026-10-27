import sys

import pandas as pd
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("smoke").getOrCreate()

total = spark.range(1000).selectExpr("sum(id)").collect()[0][0]
print("RESULT sum", total)

pdf = spark.createDataFrame(pd.DataFrame({"x": [1, 2, 3]})).toPandas()
print("RESULT arrow", int(pdf["x"].sum()), "python", f"{sys.version_info.major}.{sys.version_info.minor}")

print("RESULT udf", int(spark.range(5).rdd.map(lambda r: r.id * 2).sum()))

spark.stop()
