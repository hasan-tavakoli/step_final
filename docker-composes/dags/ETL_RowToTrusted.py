import airflow
from datetime import datetime, timedelta
from airflow.operators.python_operator import PythonOperator
import pyspark
from pyspark.sql import SparkSession
from airflow.models import DAG
import pyspark.sql.functions as f
from functools import reduce
from pyspark.sql.functions import from_unixtime, col
from datetime import datetime, timedelta
from pyspark.sql import functions as F
from pyspark.sql.functions import *
now = datetime.now()


args = {
    'owner': 'Hassan',
    "start_date": datetime(now.year, now.month, now.day),
    'provide_context': True,
    'depends_on_past': True,
    'wait_for_downstream': True,
}

dag = DAG(
    dag_id='ETL_RawToTrusted',
    default_args=args,
    schedule_interval=timedelta(1),
    max_active_runs=1,
    concurrency=1
)
# -----------------------------------------------------------------------------------------
# inner functions
def create_spark_session(spark_host):
    app = SparkSession \
        .builder \
        .appName("test") \
        .config("spark.jars.packages",
                "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1") \
        .config("spark.mongodb.input.uri", "mongodb://mongo1:27017/mydb?readPreference=primaryPreferred") \
        .config("spark.mongodb.output.uri", "mongodb://mongo1:27017/mydb?readPreference=primaryPreferred") \
        .master(spark_host) \
        .getOrCreate()
    return app

def read_from_hdfs(dataPath, spark):
    df = spark.read.format('parquet').load(dataPath)
    return df

# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------

# task functions

# -----------------------------------------------------------------------------------------
def compress_to_Trusted_Dimuser(**kwargs):
   # export PYTHONIOENCODING = utf8
    raw_dir="hdfs://namenode:9000//EDL_Data/Raw_Data_Zone/user/Curr_date={}".format(datetime.now().strftime("%Y-%m-%d"))
    # read data from Row directory
    spark = create_spark_session("spark://spark:7077")
    data = read_from_hdfs(raw_dir, spark)
    # transfer
    data.createOrReplaceTempView("user")
    datasql = spark.sql("select (_id.oid) as id,givenName,familyName,email,cast(gender as  String),cast(phoneNumber as String),cast(dateOfBirth as String) from user")

    datasql.write.mode("overwrite").option("compression", "snappy")\
        .parquet("hdfs://namenode:9000//EDL_Data/Trusted_Data_Zone/user")
# ---------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------
def compress_to_Trusted_bloodpressure(**kwargs):
    raw_dir="hdfs://namenode:9000//EDL_Data/Raw_Data_Zone/bloodpressure/Curr_date={}".format(datetime.now().strftime("%Y-%m-%d"))
    # read data from Row directory
    spark = create_spark_session("spark://spark:7077")
    data = read_from_hdfs(raw_dir, spark)
    data.createOrReplaceTempView("bloodpressure")
    datasql = spark.sql(
        "select cast(startDateTime as String) ,(userId.oid) as userId, "
        "ragThreshold.BloodPressure.diastolicValue.color as diastolicValue_color,"
        "ragThreshold.BloodPressure.diastolicValue.direction as diastolicValue_direction,"
        "cast(ragThreshold.BloodPressure.diastolicValue.isCustom as String) as diastolicValue_isCustom,"
        "ragThreshold.BloodPressure.diastolicValue.severity as diastolicValue_severity,"
        "ragThreshold.BloodPressure.systolicValue.color as systolicValue_color,"
        "ragThreshold.BloodPressure.systolicValue.direction as systolicValue_direction,"
        "cast(ragThreshold.BloodPressure.systolicValue.isCustom as string) as systolicValue_isCustom,"
        "ragThreshold.BloodPressure.systolicValue.severity as systolicValue_severity from bloodpressure")

    datasql.write.mode("overwrite").option("compression", "snappy").parquet(
        "hdfs://namenode:9000//EDL_Data/Trusted_Data_Zone/bloodpressure")
# ---------------------------------------------------------------------------------------

def compress_to_Trusted_steps(**kwargs):
    raw_dir="hdfs://namenode:9000//EDL_Data/Raw_Data_Zone/steps/Curr_date={}".format(datetime.now().strftime("%Y-%m-%d"))
    # read data from Row directory
    spark = create_spark_session("spark://spark:7077")
    data = read_from_hdfs(raw_dir, spark)

    data=data.withColumn("week_strt_day",date_sub(next_day(col("startDateTime"),"sunday"),7)).groupBy("week_strt_day","userId.oid").agg(
        count("userId.oid").cast("int").alias("stepsnum")
    ).orderBy("week_strt_day")

    data.createOrReplaceTempView("steps")
    datasql = spark.sql("select cast(week_strt_day as String) as week_strt_day,oid as userId,stepsnum from steps")
    datasql\
        .write.mode("overwrite") \
        .option("compression", "snappy") \
        .parquet("hdfs://namenode:9000//EDL_Data/Trusted_Data_Zone/steps")
# ---------------------------------------------------------------------------------------

# operators
t_compress_to_Trusted_Dimuser = PythonOperator(
    task_id='compress_to_Trusted_Dimuser',
    python_callable=compress_to_Trusted_Dimuser,
    dag=dag, )

t_compress_to_Trusted_bloodpressure = PythonOperator(
    task_id='compress_to_Trusted_bloodpressure',
    python_callable=compress_to_Trusted_bloodpressure,
    dag=dag, )

t_compress_to_Trusted_steps = PythonOperator(
    task_id='compress_to_Trusted_steps',
    python_callable=compress_to_Trusted_steps,
    dag=dag, )

t_compress_to_Trusted_Dimuser >> t_compress_to_Trusted_bloodpressure >> t_compress_to_Trusted_steps
