-- a dbt model that measures how fast deliveries are, broken down by city and hour of the day. 
-- p50: the median delivery time in minutes
-- p90: the 90th-percentile delivery time. 90% of deliveries were faster than this
select
city,
hour(order_timestamp) as order_hour,
count_if(is_delivered) as delivered_orders,
round(median(delivery_time_min),1) as p50,
round(percentile_cont(0.9) within group (order by delivery_time_min), 1) as p90
from {{ ref('fct_orders') }}
where is_delivered group by 1,2