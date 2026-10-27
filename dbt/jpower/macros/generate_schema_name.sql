{# Use the configured schema as-is (silver, gold, ref) instead of dbt's default
   <target_schema>_<custom_schema>, so tables read as silver.area_supply, gold.... #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
