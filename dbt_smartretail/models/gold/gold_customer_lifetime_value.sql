{{ config(
    materialized = 'table',
    file_format  = 'delta',
    tags         = ['gold', 'customer']
) }}

with orders as (
    select
        h.customer_id,
        count(distinct h.transaction_id)        as total_orders,
        sum(l.line_total)                       as total_spend,
        avg(l.line_total)                       as avg_order_value,
        min(cast(h.sale_datetime as date))      as first_purchase_date,
        max(cast(h.sale_datetime as date))      as last_purchase_date,
        count(distinct h.store_id)              as stores_visited,
        count(distinct l.product_id)            as distinct_products_bought
    from {{ source('silver', 'transaction_headers') }} h
    inner join {{ source('silver', 'transaction_lines') }} l
        on h.transaction_id = l.transaction_id
    where h.customer_id is not null
    group by 1
),

customers as (
    select * from {{ source('silver', 'customers') }}
)

select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.loyalty_tier,
    c.registered_date,
    o.total_orders,
    round(o.total_spend, 2)                                         as total_spend,
    round(o.avg_order_value, 2)                                     as avg_order_value,
    o.first_purchase_date,
    o.last_purchase_date,
    o.stores_visited,
    o.distinct_products_bought,
    datediff(o.last_purchase_date, o.first_purchase_date)          as customer_tenure_days,

    case
        when o.total_orders >= 20   then 'VIP'
        when o.total_orders >= 10   then 'LOYAL'
        when o.total_orders >= 3    then 'RETURNING'
        else                             'ONE_TIME'
    end                                                             as purchase_frequency_band,

    case
        when round(o.total_spend, 2) >= 5000  then 'HIGH_VALUE'
        when round(o.total_spend, 2) >= 1000  then 'MID_VALUE'
        else                                       'LOW_VALUE'
    end                                                             as spend_band,

    current_date()                                                  as _dbt_run_date
from customers c
inner join orders o
    on c.customer_id = o.customer_id