select
    id                                           as customer_id,
    data ->> '$.name'                            as customer_name,
    data ->> '$.email'                           as email,
    to_timestamp((data ->> '$.created')::bigint) as created_at,
    (data ->> '$.delinquent')::boolean           as is_delinquent
from {{ source('raw', 'customers') }}