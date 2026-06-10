{{ config(
    materialized = 'table',
    file_format  = 'delta',
    tags         = ['gold', 'daily', 'inventory']
) }}

with inventory as (
    select * from {{ source('silver', 'inventory') }}
),

daily_sales_velocity as (
    select
        l.product_id,
        h.store_id,
        avg(l.quantity)  as avg_daily_units_sold,
        sum(l.quantity)  as total_units_sold,
        count(distinct cast(h.sale_datetime as date)) as days_with_sales
    from {{ source('silver', 'transaction_lines') }} l
    inner join {{ source('silver', 'transaction_headers') }} h
        on l.transaction_id = h.transaction_id
    group by 1, 2
)

select
    i.inventory_id,
    i.store_id,
    i.product_id,
    i.stock_on_hand,
    i.reorder_point,
    i.last_updated,
    coalesce(s.avg_daily_units_sold, 0)                             as avg_daily_units_sold,
    coalesce(s.total_units_sold, 0)                                 as total_units_sold,
    coalesce(s.days_with_sales, 0)                                  as days_with_sales,

    case
        when coalesce(s.avg_daily_units_sold, 0) = 0 then 999
        else round(i.stock_on_hand / s.avg_daily_units_sold, 1)
    end                                                             as days_of_stock_remaining,

    case
        when i.stock_on_hand = 0                           then 'OUT_OF_STOCK'
        when i.stock_on_hand <= i.reorder_point * 0.5     then 'CRITICAL'
        when i.stock_on_hand <= i.reorder_point            then 'LOW'
        else                                                    'OK'
    end                                                             as stockout_risk_level,

    current_date()                                                  as report_date
from inventory i
left join daily_sales_velocity s
    on  i.store_id   = s.store_id
    and i.product_id = s.product_id