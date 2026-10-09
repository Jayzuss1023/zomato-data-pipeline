import os
import streamlit as st
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
import snowflake.connector

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-40-mini"
NEW_REVIEWS = 500
TOK_K = 5
CACHE_FILE = "review_embeddings.parquet"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Snowflake connection
# Query to pull 500 rows from STG_REVIEWS and load into pandas DataFrame
def read_reviews_from_snowflake():
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )

    query = f"""
        SELECT REVIEW_ID, CITY, RATING, COMMENT
        FROM ZOMATO.STAGING.STG_REVIEWS
        SAMPLE ({NEW_REVIEWS} ROWS)
    """

    df = conn.cursor.execute(query).fetch_pandas_all()
    conn.close()

    df.columns = [col.lower() for col in df.columns]
    return df


# Send list of strings to OpenAI's embedding endpoint. One vector per string is returned
def embed(texts):
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    return [item.embedding for item in response.data]

st.cache_data()

# If path not exist, fetch reviews from Snowflake, create embedding column and embed each comment
# CACHE_FILE keeps Snowflake and the embedding call to only run the first time
def load_reviews():
    if os.path.exists(CACHE_FILE):
        return pd.read_parquet(CACHE_FILE)
    
    df = read_reviews_from_snowflake()
    df['embedding'] = embed(df['comment'].tolist())
    df.to_parquet(CACHE_FILE)
    return df

st.title("Chat with your Zomato Reviews")
st.caption(f"Searching {NEW_REVIEWS} review, asnwering with {CHAT_MODEL} model")

# Measure similarity between two vectors from the angle between them
# 1: they point the same way
# 0: unrelated
def consine_simiarity(vec_a, vec_b):
    return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))

# embed the question
# score review's vector against the question
# create score column and return 5 highest score reviews
def find_similar_reviews(question, df):
    question_vector = embed([question])[0]

    scores = []
    for review_vector in df['embedding']:
        scores.append(consine_simiarity(question_vector, review_vector))

    df.copy()
    df['score'] = scores
    return df.nlargest(TOK_K, 'score')

# build context: one line per review
# include a system prompt to instruct the model to answer from the given reviews
def ask_llm(question, top_reviews):
    context = ""

    for _, row in top_reviews.iterrows():
        context += f" ({row['city']}, {row['rating']} stars) {row['commnet']}\n"

    system_prompt = (
        "Answer ONLY using the customer reviews provided. "
        "Be concise. If the reviews don't covert it, say so"
    )

    user_prompt = f"Questions: {question}\n\Reviews:\n{context}"

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content

# Main App Flow:
# load reviews from cache
# Present user question text box
# Find top 5 matching reviews from answer
# Ask model to answer reviews provided
# Present answers in a collapsible table
review_df = load_reviews()
question = st.text_input('Ask a question about your reviews:',
                           placeholder='e.g. What are the most complaints about delivery?')

if question:
    top_reviews = find_similar_reviews(question, review_df)
    answer = ask_llm(question, top_reviews)

    st.markdown(f"**Answer:**")
    st.write(answer)

    with st.expander('Reviews used to build this answer'):
        st.dataframe(top_reviews[['city', 'rating', 'comment']], hide_index=True)