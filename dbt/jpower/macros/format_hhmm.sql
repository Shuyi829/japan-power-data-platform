{# 'HH:MM' text from a timestamp. Dispatched so the same models run on DuckDB and Snowflake. #}
{% macro format_hhmm(ts) -%}
    {{ return(adapter.dispatch('format_hhmm', 'jpower')(ts)) }}
{%- endmacro %}

{% macro default__format_hhmm(ts) -%}
    strftime({{ ts }}, '%H:%M')
{%- endmacro %}

{% macro snowflake__format_hhmm(ts) -%}
    to_char({{ ts }}, 'HH24:MI')
{%- endmacro %}
