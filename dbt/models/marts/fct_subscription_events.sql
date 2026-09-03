-- Subscription lifecycle: one row per start, plan change or cancellation,
-- with the MRR before and after so mrr_monthly can be built from it.
with events as (

    select
        e.event_id,
        e.subscription_id,
        e.customer_id,
        e.event_type = 'customer.subscription.deleted' as is_cancellation,
        case
            when e.event_type = 'customer.subscription.created' then 'started'
            when e.event_type = 'customer.subscription.deleted' then 'canceled'
            when plan.mrr_amount > previous_plan.mrr_amount then 'upgraded'
            when plan.mrr_amount < previous_plan.mrr_amount then 'downgraded'
        end as event_type,
        case
            when e.event_type = 'customer.subscription.deleted' then e.canceled_at
            else e.period_start
        end as occurred_at,
        previous_plan.plan_key                as previous_plan_key,
        plan.plan_key                         as plan_key,
        coalesce(previous_plan.mrr_amount, 0) as mrr_before,
        plan.mrr_amount                       as mrr_after
    from {{ ref('stg_subscription_events') }} e
    join {{ ref('stg_subscriptions') }} s using (subscription_id)
    left join {{ ref('dim_plan') }} plan on plan.plan_key = e.plan_key
    left join {{ ref('dim_plan') }} previous_plan on previous_plan.plan_key = e.previous_plan_key

)

select
    event_id,
    subscription_id,
    customer_id,
    event_type,
    occurred_at,
    plan_key,
    previous_plan_key,
    case when is_cancellation then mrr_after else mrr_before end as mrr_before,
    case when is_cancellation then 0 else mrr_after end          as mrr_after
from events
where event_type is not null