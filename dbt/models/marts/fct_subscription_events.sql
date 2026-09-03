-- Subscription lifecycle: one row per start, plan change or cancellation,
-- with the MRR before and after so mrr_monthly can be built from it.
with events as (

    select
        e.event_id,
        e.subscription_id,
        e.customer_id,
        case
            when e.event_type = 'customer.subscription.created' then 'started'
            when e.event_type = 'customer.subscription.deleted' then 'canceled'
            when new_plan.mrr_amount > old_plan.mrr_amount then 'upgraded'
            when new_plan.mrr_amount < old_plan.mrr_amount then 'downgraded'
        end as event_type,
        case
            when e.event_type = 'customer.subscription.deleted' then e.canceled_at
            else e.period_start
        end as occurred_at,
        old_plan.plan_key                as from_plan_key,
        new_plan.plan_key                as to_plan_key,
        coalesce(old_plan.mrr_amount, 0) as mrr_before,
        case when e.event_type = 'customer.subscription.deleted' then 0
             else new_plan.mrr_amount end as mrr_after
    from {{ ref('stg_subscription_events') }} e
    join {{ ref('stg_subscriptions') }} s using (subscription_id)
    left join {{ ref('dim_plan') }} new_plan on new_plan.plan_key = e.plan_key
    left join {{ ref('dim_plan') }} old_plan on old_plan.plan_key = e.previous_plan_key

)

select * from events
where event_type is not null