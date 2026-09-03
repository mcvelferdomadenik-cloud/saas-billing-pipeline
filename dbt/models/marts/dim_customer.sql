-- One row per customer with cohort, current plan and lifetime value.
with subs as (

    select
        customer_id,
        min(started_at)                          as first_subscribed_at,
        arg_max(plan_key, started_at)            as current_plan_key,
        arg_max(status, started_at)              as subscription_status,
        max(canceled_at)                         as canceled_at,
        arg_max(cancellation_reason, started_at) as cancellation_reason
    from {{ ref('stg_subscriptions') }}
    group by customer_id

),

invoices as (

    select
        customer_id,
        sum(amount_paid)                    as lifetime_revenue,
        count(*)                            as invoice_count,
        count(*) filter (where not is_paid) as unpaid_invoice_count
    from {{ ref('fct_invoices') }}
    group by customer_id

)

select
    c.customer_id,
    c.customer_name,
    c.email,
    c.created_at,
    date_trunc('month', s.first_subscribed_at)::date as cohort_month,
    s.current_plan_key,
    s.subscription_status,
    s.canceled_at,
    s.cancellation_reason,
    coalesce(i.lifetime_revenue, 0)                  as lifetime_revenue,
    coalesce(i.invoice_count, 0)                     as invoice_count,
    coalesce(i.unpaid_invoice_count, 0)              as unpaid_invoice_count
from {{ ref('stg_customers') }} c
left join subs s using (customer_id)
left join invoices i using (customer_id) 