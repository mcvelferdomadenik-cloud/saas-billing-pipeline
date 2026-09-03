-- MRR waterfall per month: where revenue came from and where it went.
select
    month,
    sum(mrr)                                                               as mrr,
    count(*) filter (where mrr > 0)                                        as active_customers,
    coalesce(sum(mrr_change) filter (where movement = 'new'), 0)           as new_mrr,
    coalesce(sum(mrr_change) filter (where movement = 'expansion'), 0)     as expansion_mrr,
    coalesce(sum(mrr_change) filter (where movement = 'reactivation'), 0)  as reactivation_mrr,
    coalesce(sum(mrr_change) filter (where movement = 'contraction'), 0)   as contraction_mrr,
    coalesce(sum(mrr_change) filter (where movement = 'churn'), 0)         as churn_mrr,
    count(*) filter (where movement = 'new')                               as new_customers,
    count(*) filter (where movement = 'churn')                             as churned_customers
from {{ ref('mrr_customer_monthly') }}
group by month
order by month