-- One row per invoice, with plan attributes and payment outcome.
select
    i.invoice_id,
    i.customer_id,
    i.subscription_id,
    p.plan_key,
    p.plan_name,
    p.billing_interval,
    i.billing_reason,
    i.status,
    i.status = 'paid'                         as is_paid,
    i.created_at,
    date_trunc('month', i.period_start)::date as invoice_month,
    i.period_start,
    i.period_end,
    i.paid_at,
    i.amount_due,
    i.amount_paid,
    i.amount_due - i.amount_paid              as amount_unpaid,
    i.attempt_count
from {{ ref('stg_invoices') }} i
left join {{ ref('dim_plan') }} p using (price_id)