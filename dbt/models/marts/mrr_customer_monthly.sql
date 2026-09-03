-- Customer x month grid with month-end MRR and the movement vs the previous month.
with segments as (

    -- each event opens a segment of constant MRR until the next event on that subscription
    select
        customer_id,
        subscription_id,
        occurred_at as valid_from,
        lead(occurred_at) over (partition by subscription_id order by occurred_at) as valid_to,
        mrr_after as mrr
    from {{ ref('fct_subscription_events') }}

),

months as (

    select unnest(generate_series(
        (select date_trunc('month', min(valid_from)) from segments),
        (select date_trunc('month', max(valid_from)) from segments),
        interval 1 month
    )) as month_start

),

grid as (

    select c.customer_id, m.month_start, m.month_start + interval 1 month as next_month_start
    from {{ ref('stg_customers') }} c
    cross join months m

),

month_end_mrr as (

    -- MRR at the last instant of the month = segments still open at next_month_start
    select
        g.customer_id,
        g.month_start,
        coalesce(sum(s.mrr), 0) as mrr
    from grid g
    left join segments s
        on s.customer_id = g.customer_id
        and s.valid_from < g.next_month_start
        and (s.valid_to is null or s.valid_to >= g.next_month_start)
    group by 1, 2

),

with_history as (

    select
        customer_id,
        month_start::date as month,
        mrr,
        coalesce(lag(mrr) over (partition by customer_id order by month_start), 0) as previous_mrr,
        coalesce(max(mrr) over (
            partition by customer_id order by month_start
            rows between unbounded preceding and 1 preceding
        ), 0) as max_previous_mrr
    from month_end_mrr

)

select
    customer_id,
    month,
    mrr,
    previous_mrr,
    mrr - previous_mrr as mrr_change,
    case
        when previous_mrr = 0 and mrr > 0 and max_previous_mrr = 0 then 'new'
        when previous_mrr = 0 and mrr > 0 then 'reactivation'
        when mrr > previous_mrr then 'expansion'
        when mrr > 0 and mrr < previous_mrr then 'contraction'
        when previous_mrr > 0 and mrr = 0 then 'churn'
    end as movement
from with_history