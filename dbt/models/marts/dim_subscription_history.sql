-- Type-2 dimension: one row per subscription per (status, plan) interval, with MRR.
select
    s.subscription_id,
    s.customer_id,
    s.status,
    s.plan_key,
    p.plan_name,
    p.billing_interval,
    p.mrr_amount,
    s.dbt_valid_from       as valid_from,
    s.dbt_valid_to         as valid_to,
    s.dbt_valid_to is null as is_current
from {{ ref('subscriptions_snapshot') }} s
left join {{ ref('dim_plan') }} p using (plan_key)