{{ config(
    materialized = 'table',
    file_format  = 'delta',
    tags         = ['gold', 'promotion']
) }}

select
    pr.promotion_id,
    pr.promotion_name,
    pr.discount_type,
    round(pr.discount_value * 100, 1)               as discount_value_pct,
    pr.start_date,
    pr.end_date,
    count(distinct l.transaction_id)                as transactions_with_discount,
    sum(l.quantity)                                 as units_sold_under_promo,
    round(sum(l.line_total), 2)                     as discounted_revenue,
    round(avg(l.discount_pct) * 100, 1)             as avg_discount_applied_pct,
    round(
        sum(l.quantity * l.unit_price * l.discount_pct), 2
    )                                               as total_discount_cost,
    round(
        sum(l.line_total) / nullif(count(distinct l.transaction_id), 0), 2
    )                                               as revenue_per_transaction,
    current_date()                                  as _dbt_run_date
from {{ source('silver', 'transaction_lines') }} l
inner join {{ source('silver', 'promotions') }} pr
    on  l.discount_pct between pr.discount_value - 0.05
                           and pr.discount_value + 0.05
where l.discount_pct > 0
group by
    pr.promotion_id, pr.promotion_name, pr.discount_type,
    pr.discount_value, pr.start_date, pr.end_date