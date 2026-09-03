select
    id                                                    as charge_id,
    data ->> '$.customer'                                 as customer_id,
    data ->> '$.payment_intent'                           as payment_intent_id,
    data ->> '$.status'                                   as status,
    ((data ->> '$.amount')::integer / 100)::decimal(12, 2) as amount,
    to_timestamp((data ->> '$.created')::bigint)          as created_at,
    data ->> '$.failure_code'                             as failure_code
from {{ source('raw', 'charges') }}