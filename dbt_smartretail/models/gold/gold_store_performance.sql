{{ config(
    materialized = 'table',
    file_format  = 'delta',
    tags         = ['gold', 'daily', 'store']
) }}

select
    h.store_id,
    s.store_name,
    s.region,
    s.format,
    s.city,
    s.country,
    cast(h.sale_datetime as date)               as sales_date,
    count(distinct h.transaction_id)            as total_transactions,
    round(sum(l.line_total), 2)                 as total_sales,
    round(avg(l.line_total), 2)                 as avg_basket_value,
    count(distinct h.customer_id)               as unique_customers,
    sum(l.quantity)                             as total_units_sold,
    round(
        sum(l.quantity * l.unit_price * l.discount_pct), 2
    )                                           as total_discounts_given,
    count(distinct l.product_id)                as distinct_products_sold,
    current_date()                              as _dbt_run_date
from {{ source('silver', 'transaction_headers') }} h
inner join {{ source('silver', 'transaction_lines') }} l
    on h.transaction_id = l.transaction_id
inner join {{ source('silver', 'stores') }} s
    on h.store_id = s.store_id
group by 1, 2, 3, 4, 5, 6, 7