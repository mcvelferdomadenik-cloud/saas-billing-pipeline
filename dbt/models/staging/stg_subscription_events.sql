select
    id                                                                     as event_id,
    data ->> '$.type'                                                      as event_type,
    data ->> '$.data.object.id'                                            as subscription_id,
    data ->> '$.data.object.customer'                                      as customer_id,
    data ->> '$.data.previous_attributes.items.data[0].price.lookup_key'   as previous_plan_key,
    data ->> '$.data.object.items.data[0].price.lookup_key'                as plan_key,
    to_timestamp((data ->> '$.data.object.items.data[0].current_period_start')::bigint) as period_start,
    to_timestamp((data ->> '$.data.object.canceled_at')::bigint)           as canceled_at
from {{ source('raw', 'events') }}
where (data ->> '$.type') like 'customer.subscription.%'