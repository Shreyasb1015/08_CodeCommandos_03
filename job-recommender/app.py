import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

def preprocess_skills(skills):
    if isinstance(skills, str):
        return ' '.join(skills.split('|'))
    else:
        return ''

def preprocess_experience(experience):
    if isinstance(experience, str):
        try:
            num_value = int(experience.split()[0])
            return num_value
        except ValueError:
            return -1
    else:
        return -1

def recommend_jobs(df, user_skills, user_location, user_experience):
    # Preprocess skills
    df['Key Skills'] = df['Key Skills'].apply(preprocess_skills)
    # Preprocess experience
    df['Job Experience Required'] = df['Job Experience Required'].apply(preprocess_experience).astype(int)

    # One-hot encoding for location
    location_encoder = OneHotEncoder()
    location_encoded = location_encoder.fit_transform(df[['Location']])
    user_location_encoded = location_encoder.transform([[user_location]])

    # Concatenate user skills with existing skills
    all_skills = df['Key Skills'].tolist()

    # Initialize and fit TF-IDF vectorizer
    tfidf_vectorizer = TfidfVectorizer()
    skills_tfidf = tfidf_vectorizer.fit_transform(all_skills)

    # Transform user skills
    user_skills_tfidf = tfidf_vectorizer.transform([user_skills])

    # Compute cosine similarity between user skills and job skills
    skills_similarity = cosine_similarity(user_skills_tfidf, skills_tfidf[:-1])  # Exclude user input from similarity matrix

    # Filter and rank based on location and experience
    filtered_df = df[(df['Location'] == user_location) & (df['Job Experience Required'] >= int(user_experience))]

    # Reset index to align with similarity scores
    filtered_df.reset_index(drop=True, inplace=True)

    # Extract the similarity scores for the filtered indices
    filtered_similarity_scores = skills_similarity[:, filtered_df.index]

    # Compute final scores combining similarity and other features (e.g., location, experience)
    final_scores = filtered_similarity_scores.flatten() * filtered_df['Job Experience Required'].apply(lambda exp: exp / int(user_experience))
    # Combine final scores with corresponding job titles or other relevant information
    filtered_df['Final Score'] = final_scores

    # Sort the combined data based on the final scores in descending order
    top_recommendations = filtered_df.sort_values(by='Final Score', ascending=False)

    return top_recommendations

# Load data
df = pd.read_csv('jobs.csv')

# Streamlit UI
st.title("Job Recommendation System")
st.markdown("---")

# User inputs
user_skills = st.text_input("Enter your skills separated by commas:")
user_location = st.text_input("Enter your location:")
user_experience = st.text_input("Enter your experience (in years):")

# Recommendations
if st.button("Get Recommendations"):
    recommendations = recommend_jobs(df, user_skills, user_location, user_experience)
    st.subheader("Top Job Recommendations:")
    for index, job in recommendations.head(5).iterrows():
        st.write(f"**Job Title:** {job['Job Title']}")
        st.write(f"**Salary:** {job['Job Salary']}")
        st.write(f"**Location:** {job['Location']}")
        st.write(f"**Experience Required:** {job['Job Experience Required']} years")
        st.markdown("---")
