import logging
from airflow import DAG
from airflow.operators.python import PythonOperator, get_current_context
# from airflow.contrib.operators.bigquery_operator import BigQueryOperator
from datetime import datetime
from configparser import ConfigParser
import requests
import json

config_object = ConfigParser()
config_object.read("resources/config.ini")


# Parse config up here in case we want to add more steps involving config in other tasks

# Since this dag is simple, put all methods here for easy viewing but with longer methods,
# would put under a directory called scripts with a file called extract.py
# and would import extract.extract_airports from scripts, same with transform and load
def extract_airports(ti) -> None:
    config = config_object["extract_airports"]
    api_url = config["api_url"].format(config["country"])
    # Put this in a config in case next time we want a different country next time
    response = requests.get(api_url, headers={'X-Api-Key': config["api_key"]})

    if response.status_code == requests.codes.ok:
        extract_output_loc = "dags/airports_extract.json"
        with open(extract_output_loc, 'w') as f:
            json.dump(response.json(), f)
        ti.xcom_push(key='extract_output_loc', value=extract_output_loc)
        # Adding to xcom would be useful if this dag runs a lot and output loc has an autogenerated name
    else:
        logging.info(f"Error getting airports for {config['country']}:", response.status_code, response.text)


def transform_airports(ti) -> None:
    ctx = get_current_context()
    data_interval_start = dict(ctx)["data_interval_start"]
    # If we wanted a value that takes multiple lines to get, would make a helper in a "helpers/transform" directory.

    timestamp = datetime.now()  # More efficient to get this once but could be done line by line

    extract_output_loc = ti.xcom_pull(key='extract_output_loc', task_ids='extract')
    transform_output_loc = "dags/airports_transform.json"
    ti.xcom_push(key='transform_output_loc', value=transform_output_loc)

    with open(extract_output_loc) as f:
        to_transform = json.load(f)

    for line in to_transform:
        line["transformation_timestamp"] = timestamp.strftime("%m/%d/%Y, %H:%M:%S")
        line["data_interval_start"] = str(data_interval_start)

    with open(transform_output_loc, 'w') as f:
        json.dump(to_transform, f)


def load_airports(ti) -> None:
    transform_output_loc = ti.xcom_pull(key='transform_output_loc', task_ids='transform')
    logging.info(f"Placeholder to load data for {transform_output_loc}")


with DAG(
        dag_id="airport_etl",
        description="Airport ETL DAG",
        start_date=datetime(2024, 1, 1),
        schedule_interval="@hourly",
        catchup=False
) as dag:
    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_airports)

    transform = PythonOperator(
        task_id="transform",
        python_callable=transform_airports
    )

    load = PythonOperator(
        task_id="load",
        python_callable=load_airports
    )
    """
    load_with_bigquery = BigQueryOperator(
        dag = "airport_etl, 
        task_id="load_with_bigquery"
        bql="script_that_loads_extract_output.sql",
        params={"extract_output": extract_output_loc},
        destination_dataset_table="airport_table"
        bigquery_conn_id='my_gcp_connection' # this is the airflow connection to gcp we defined in the front end. More info here: https://github.com/alexvanboxel/airflow-gcp-examples
    )
    """

extract >> transform >> load
