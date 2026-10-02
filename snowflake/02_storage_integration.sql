USE ROLE ACCOUNTADMIN;


-- MUST EDIT THESE TWO
--   <ROLE_ARN> = arn:aws:iam::<your-account-id>:role/snowflake-zomato-role
--   <BUCKET>   = your bucket, e.g. zomato-dl-yourname
CREATE OR REPLACE STORAGE INTEGRATION ZOMATO_S3_INT
    TYPE = EXTERNAL_STORAGE
    STORAGE_PROVIDER = 'S3'
    ENABLED = TRUE
    STORAGE_AWS_ROLE_ARN = '<ROLE_ARN>'
    STORAGE_ALLOWED_LOCATIONS = ('s3//<BUCKET>');

GRANT USAGE ON INTEGRATION ZOMATO_S3_INT TO ROLE DBT_ROLE;

-- Run this, then copy the two values into the IAM role trust policy (Step D).
DESC INTEGRATION ZOMATO_S3_INT
--   STORAGE_AWS_IAM_USER_ARN  ->  the "AWS": principal in the trust policy
--   STORAGE_AWS_EXTERNAL_ID   ->  the sts:ExternalId condition