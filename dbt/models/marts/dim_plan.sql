-- One row per Stripe price. mrr_amount normalises yearly plans to a monthly value.
select distinct
    price_id,
    plan_key,
    plan_name,
    billing_interval,
    price_amount,
    case billing_interval
        when 'year' then round(price_amount / 12, 2)::decimal(12, 2)
        else price_amount
    end as mrr_amount
from {{ ref('stg_subscriptions') }}