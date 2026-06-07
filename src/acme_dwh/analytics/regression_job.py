"""Spark ML regression job.

Trains a LinearRegression on one asset's latest-per-day series (tombstones excluded)
to predict the day's `open` from (seconds, close, low, high), and writes test-set
predictions to `regression_results`. Configure via env ASSET_ID / DATA_SOURCE_ID
(default BTCUSD / BITFINEX); see README / docker-compose for the spark-submit command.
"""
import os

from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import Normalizer, VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Sources are heterogeneous, so don't hard-code OHLC. Predict the first available
# "target" indicator from whatever other same-day numeric indicators the source has.
# Bitfinex -> predicts `open`; Nasdaq's QDL/BITFINEX (no open/close) -> predicts `last`.
LABEL_PREF = ["open", "last", "close", "mid"]
FEATURE_PREF = ["open", "close", "high", "low", "mid", "last", "ask", "bid", "volume"]


def main() -> None:
    keyspace = os.environ.get("CASSANDRA_KEYSPACE", "acme_dwh")
    asset_id = os.environ.get("ASSET_ID", "BTCUSD")
    data_source_id = os.environ.get("DATA_SOURCE_ID", "BITFINEX")

    spark = SparkSession.builder.appName("acme-dwh-regression").getOrCreate()

    data = (
        spark.read.format("org.apache.spark.sql.cassandra")
        .options(table="data", keyspace=keyspace)
        .load()
        .filter((F.col("asset_id") == asset_id) & (F.col("data_source_id") == data_source_id))
    )

    latest_per_day = Window.partitionBy("business_date").orderBy(F.col("system_time").desc())
    latest = (
        data.withColumn("_rn", F.row_number().over(latest_per_day))
        .filter(F.col("_rn") == 1)
        .filter(~F.coalesce(F.col("deleted"), F.lit(False)))
    )

    candidates = sorted(set(LABEL_PREF) | set(FEATURE_PREF))
    df = latest.select(
        F.unix_timestamp(F.col("business_date").cast("timestamp")).alias("seconds"),
        F.col("business_date"),
        *[F.col("values_double")[k].alias(k) for k in candidates],
    )

    # which indicators does this source actually populate?
    counts = df.agg(*[F.count(k).alias(k) for k in candidates]).collect()[0].asDict()
    present = {k for k, v in counts.items() if v}
    label_col = next((k for k in LABEL_PREF if k in present), None)
    feature_cols = [k for k in FEATURE_PREF if k in present and k != label_col]

    if label_col is None or not feature_cols:
        print(
            f"[regression] no usable price indicators for {asset_id}/{data_source_id} "
            f"(have: {sorted(present)})."
        )
        spark.stop()
        return

    df = df.select("seconds", "business_date", label_col, *feature_cols).na.drop()
    if df.count() < 10:
        print(f"[regression] not enough data for {asset_id}/{data_source_id} (need >=10 rows).")
        spark.stop()
        return

    assembled = VectorAssembler(
        inputCols=["seconds", *feature_cols], outputCol="features"
    ).transform(df)
    normalized = Normalizer(inputCol="features", outputCol="normFeatures", p=2.0).transform(assembled)

    train, test = normalized.randomSplit([0.7, 0.3], seed=42)
    lr = LinearRegression(
        labelCol=label_col, featuresCol="normFeatures", maxIter=10, regParam=1.0, elasticNetParam=1.0
    )
    model = lr.fit(train)
    predictions = model.transform(test)

    rmse = RegressionEvaluator(
        labelCol=label_col, predictionCol="prediction", metricName="rmse"
    ).evaluate(predictions)

    results = predictions.select(
        F.lit(asset_id).alias("asset_id"),
        F.lit(data_source_id).alias("data_source_id"),
        F.col("seconds").cast("long").alias("seconds"),
        F.col("business_date"),
        F.col(label_col).alias("open"),  # actual target stored in the table's `open` column
        F.col("prediction"),
    )
    (
        results.write.format("org.apache.spark.sql.cassandra")
        .options(table="regression_results", keyspace=keyspace)
        .mode("append")
        .save()
    )

    print(
        f"[regression] {asset_id}/{data_source_id}: predicted '{label_col}' from {feature_cols}; "
        f"wrote {results.count()} predictions; RMSE={rmse:.4f}"
    )
    results.orderBy("seconds").show(20, truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
