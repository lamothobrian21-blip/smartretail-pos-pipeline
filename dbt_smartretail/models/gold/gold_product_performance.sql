{{ config(
    materialized = 'table',
    file_format  = 'delta',
    tags         = ['gold', 'product']
) }}

select
    l.product_id,
    p.product_name,
    p.category,
    p.supplier_id,
    round(p.unit_price, 2)                          as list_price,
    round(p.cost_price, 2)                          as cost_price,
    sum(l.quantity)                                 as total_units_sold,
    round(sum(l.line_total), 2)                     as total_revenue,
    round(avg(l.unit_price), 2)                     as avg_selling_price,
    round(avg(l.discount_pct) * 100, 1)             as avg_discount_pct,
    count(distinct h.store_id)                      as stores_selling,
    count(distinct h.transaction_id)                as transaction_count,
    count(distinct h.customer_id)                   as unique_customers,
    round(
        (avg(l.unit_price) - p.cost_price)
        / nullif(avg(l.unit_price), 0) * 100, 1
    )                                               as gross_margin_pct,
    current_date()                                  as _dbt_run_date
from {{ source('silver', 'transaction_lines') }} l
inner join {{ source('silver', 'transaction_headers') }} h
    on l.transaction_id = h.transaction_id
inner join {{ source('silver', 'products') }} p
    on l.product_id = p.product_id
group by
    l.product_id, p.product_name, p.category,
    p.supplier_id, p.unit_price, p.cost_price