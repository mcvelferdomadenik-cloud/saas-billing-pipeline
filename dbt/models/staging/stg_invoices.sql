select
    id                                                              as invoice_id,
    data ->> '$.customer'                                           as customer_id,
    data ->> '$.parent.subscription_details.subscription'           as subscription_id,
    data ->> '$.lines.data[0].pricing.price_details.price'          as price_id,
    data ->> '$.status'                                             as status,
    data ->> '$.billing_reason'                                     as billing_reason,
    to_timestamp((data ->> '$.created')::bigint)                    as created_at,
    to_timestamp((data ->> '$.lines.data[0].period.start')::bigint) as period_start,
    to_timestamp((data ->> '$.lines.data[0].period.end')::bigint)   as period_end,
    to_timestamp((data ->> '$.status_transitions.paid_at')::bigint) as paid_at,
    ((data ->> '$.amount_due')::integer / 100)::decimal(12, 2)      as amount_due,
    ((data ->> '$.amount_paid')::integer / 100)::decimal(12, 2)     as amount_paid,
    (data ->> '$.attempt_count')::integer                           as attempt_count
from {{ source('raw', 'invoices') }}