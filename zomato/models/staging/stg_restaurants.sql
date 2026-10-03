-- parse the messy inputs (-- →null, 50+ ratings→50, ₹ 200→200, city after last comma):

select
    id::number as restaurant_id,
    name as restaurant_name,
    trim(coalesce(regexp_substr(city, '[^,]+$'), city)) as city,
    -- nullif(rating, '--') turns the placeholder -- into NULL
    try_to_decimal(nullif(rating, '--'), 3, 1) as rating,
    -- pull the number out of text like "50+ ratings".
    try_to_number(regexp_substr(rating_count, '[0-9]+')) as rating_count,
    -- grabs the first run of digits, so "₹ 200" becomes 200.
    try_to_number(regexp_substr(cost, '[0-9]+')) as cost_for_two,
    cuisine,
    lic_no as license_no
from {{ source('raw', 'restaurants') }} where try_to_number(id) is not null
