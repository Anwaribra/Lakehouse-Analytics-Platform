{% macro s3_bronze_glob(relative_glob) %}
  's3://{{ env_var("MINIO_BUCKET", "lakehouse") }}/bronze/{{ relative_glob }}'
{% endmacro %}
