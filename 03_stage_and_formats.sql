USE ROLE ACCOUNTADMIN;
USE DATABASE ZOMATO;
USE SCHEMA RAW;


-- Plain CSV (manual upload, no gzip). Files KEEP their header row -> SKIP_HEADER = 1.
-- Comment fields (reviews) contain commas but are quoted, so keep the quote char.
CREATE OR REPLACE FILE FORMAT ZOMATOR.RAW.CSV_FMT
    TYPE = 'CSV'
    COMPRESSION = 'AUTO'
    FIELD_DELIMITER = ','
    FIELD_OPTIONALLY_ENCLOSED_BY: '"'
    SKIP_HEADER = 1
    EMPTY_FIELD_AS_NULL = TRUE
    NULL_IF = ('', '\\N', 'NULL')
    TRIM_SPACE = FALSE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE -- messy source rows (e.g. food.csv missing a
                                            -- trailing field) NULL-fill instead of aborting


CREATE OR REPLACE STAGE ZOMATO.RAW.ZOMATO_RAW_STAGE
    STORAGE_INTEGRATION ZOMATO_S3_INT
    URL = 's3://<BUCKET>/raw/'
    FILE_FORMAT = ZOMATO.RAW.CSV_FMT;

LIST @ZOMATO.RAW.ZOMATO_RAW_STAGE
