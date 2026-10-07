import os
import json
import snowflake.connector
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = 'gpt-4o-mini'

SAMPLE_N = int(os.getenv("SAMPLE_N", "5"))
TOPICS = ['food quality', 'delivery', 'pricing', 'service', 'packaging', 'other']
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT= f"""
you classify customer reviews for a food delivery app.

For the review you are given, return:
- sentiment_label: positive, negative, or neutral
- sentiment_score: a number between -1.0 and 1.0
- topic: one of {TOPICS}
- key_issue: a short phrase of 6 words or less that describes the main issue in the review, if any. If there is no issue, return null.

Reply as JSON in this extract format:
{{
    "sentiment_label": "<sentiment_label>",
    "sentiment_score": 0.8,
    "topic": "<topic>",
    "key_issue": "<key_issue>"
}} 
"""

# open a Snowflake connection using credentials from environment variables 
def get_connection():
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA")
    )

# Create the ZOMATO.AI schema if it is missing, then creates ZOMATO.AI.REVIEW_ENRICHED if it does not already exist
def create_output_table(cursor):
    cursor.execute("CREATE SCHEMA IF NOT EXISTS ZOMATO.AI")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ZOMATO.AI.REVIEW_ENRICHED (
            REVIEW_ID STRING,
            SENTIMENT_LABEL STRING,
            SENTIMENT_SCORE FLOAT,
            TOPIC STRING,
            KEY_ISSUE STRING,
            MODEL STRING,
            ENRICHED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)

# Select review ids and comments from ZOMATO.RAW.REVIEWS that are not already in the enriched table, limited to SAMPLE_N
def get_reviews_to_enrich(cursor):
    cursor.execute(f"""
        SELECT REVIEW_ID, COMMENT
        FROM ZOMATO.RAW.REVIEWS
        WHERE REVIEW_ID NOT IN (SELECT REVIEW_ID FROM ZOMATO.AI.REVIEW_ENRICHED)
        LIMIT {SAMPLE_N}
    """)
    return cursor.fetchall()

# Send one review comment to gpt-4o-mini with the system prompt and returns the parsed JSON
def classify_review(comment):
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": comment}
        ]
    )
    answer = response.choices[0].message.content
    return json.loads(answer)

# Bulk insert the classified rows into Snowflake, including which model produced them
def save_results(cursor, results):
    """Insert all the enriched rows into Snowflake in one go"""
    print(f"Saving {len(results)} enriched reviews to Snowflake...")
    cursor.executemany(
        """
            INSERT INTO ZOMATO.AI.REVIEW_ENRICHED
                (review_id, sentiment_label, sentiment_score, topic, key_issue, model)
            VALUES(%s, %s, %s, %s, %s, %s)
        """,
        results
    )

# connect, create the output table, fetch unenriched reviews, classify each one, save the results, commit, then close the connection. 
# If a review fails classification, skip it and continue with the rest.
def main():
    conn = get_connection()
    cursor = conn.cursor()
    create_output_table(cursor)
    reviews = get_reviews_to_enrich(cursor)

    if len(reviews) == 0:
        print("Now new reviews to enrich")
        return
    
    print(f"Enriching {len(reviews)} reviews...")

    results = []

    for review_id, comment in reviews:
        print(f"Classifying review {review_id}: {comment}")
        try:
            labels = classify_review(comment)
            print(f"Lavels for review {review_id}: {labels}")
            results.append((
                review_id,
                labels["sentiment_label"],
                float(labels["sentiment_score"]),
                labels["topic"],
                labels["key_issue"],
                MODEL
            ))
        except Exception as e:
            print(f"Error occurred while classifying review {review_id}: {e}")
        
    save_results(cursor, results)
    print(f"Saved {len(results)} enriched reviews to Snowflake")
    conn.commit()
    cursor.close()
    conn.close()
    
if __name__ == "__main__":
    main()