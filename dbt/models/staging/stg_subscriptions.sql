select
    id                                                    as subscription_id,
    data ->> '$.customer'                                 as customer_id,
    data ->> '$.status'                                   as status,
    data ->> '$.items.data[0].price.id'                   as price_id,
    data ->> '$.items.data[0].price.lookup_key'           as plan_key,
    data ->> '$.items.data[0].price.product'              as plan_name,
    data ->> '$.items.data[0].price.recurring.interval'   as billing_interval,
    ((data ->> '$.items.data[0].price.unit_amount')::integer / 100)::decimal(12, 2) as price_amount,
    to_timestamp((data ->> '$.start_date')::bigint)       as started_at,
    to_timestamp((data ->> '$.canceled_at')::bigint)      as canceled_at,
    data ->> '$.cancellation_details.reason'              as cancellation_reason
from {{ source('raw', 'subscriptions') }}