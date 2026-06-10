{{ config(
    materialized = 'table',
    file_format  = 'delta',
    tags         = ['gold', 'daily', 'sales']
) }}

with txn_headers as (
    select * from {{ source('silver', 'transaction_headers') }}
),

txn_lines as (
    select * from {{ source('silver', 'transaction_lines') }}
),

joined as (
    select
        cast(h.sale_datetime as date)                               as sales_date,
        h.store_id,
        l.product_id,
        h.payment_method,
        count(distinct h.transaction_id)                            as total_transactions,
        sum(l.quantity)                                             as total_units,
        sum(l.line_total)                                           as total_sales,
        avg(l.line_total)                                           as average_basket_value,
        sum(l.quantity * l.unit_price)                              as gross_revenue,
        sum(l.quantity * l.unit_price * l.discount_pct)            as total_discount_given,
        count(distinct h.customer_id)                               as unique_customers
    from txn_headers h
    inner join txn_lines l
        on h.transaction_id = l.transaction_id
    group by 1, 2, 3, 4
)

select
    sales_date,
    store_id,
    product_id,
    payment_method,
    total_transactions,
    total_units,
    round(total_sales, 2)           as total_sales,
    round(average_basket_value, 2)  as average_basket_value,
    round(gross_revenue, 2)         as gross_revenue,
    round(total_discount_given, 2)  as total_discount_given,
    unique_customers,
    current_date()                  as _dbt_run_date
from joined