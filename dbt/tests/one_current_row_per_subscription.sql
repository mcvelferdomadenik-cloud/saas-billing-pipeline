-- Fails if any subscription has more than one open (valid_to is null) row.
select subscription_id
from {{ ref('dim_subscription_history') }}
where is_current
group by subscription_id
having count(*) > 1