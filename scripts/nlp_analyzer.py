from transformers import pipeline
import pandas as pd

# Initialize the sentiment analysis pipeline using a pre-trained model.
# Using a distilled version for a balance of performance and size.
# If this model is not available or you prefer another, this can be changed.
# For example: 'nlptown/bert-base-multilingual-uncased-sentiment' for multilingual
# or 'cardiffnlp/twitter-roberta-base-sentiment' for Twitter-specific tasks.
# Using a general-purpose model first.
SENTIMENT_MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
try:
    sentiment_analyzer = pipeline("sentiment-analysis", model=SENTIMENT_MODEL_NAME)
    print(f"Sentiment analysis pipeline loaded successfully with model: {SENTIMENT_MODEL_NAME}")
except Exception as e:
    print(f"Error loading sentiment analysis model '{SENTIMENT_MODEL_NAME}': {e}")
    print("Please ensure you have an internet connection for the first download, or the model is cached.")
    print("Falling back to a placeholder function for sentiment analysis.")
    # Placeholder function if model loading fails
    def sentiment_analyzer_placeholder(text): # Renamed to avoid conflict if pipeline fails
        # Simple rule-based placeholder
        text_lower = text.lower()
        if "bad" in text_lower or "sad" in text_lower or "angry" in text_lower:
            return [{"label": "NEGATIVE", "score": 0.9}]
        elif "good" in text_lower or "happy" in text_lower or "great" in text_lower:
            return [{"label": "POSITIVE", "score": 0.9}]
        else:
            return [{"label": "NEUTRAL", "score": 0.5}] # Or adjust as needed
    sentiment_analyzer = sentiment_analyzer_placeholder


def analyze_sentiment_text(text_content):
    """
    Analyzes the sentiment of a single piece of text.
    Returns a dictionary with 'label' and 'score'.
    """
    if not text_content or not isinstance(text_content, str):
        return {"label": "INVALID_INPUT", "score": 0.0}
    try:
        results = sentiment_analyzer(text_content)
        # The pipeline can return a list of results, we'll take the first one.
        if results and isinstance(results, list):
            return {"label": results[0]['label'], "score": round(results[0]['score'], 4)}
        else: # Fallback for unexpected result format
            return {"label": "ANALYSIS_ERROR", "score": 0.0}
    except Exception as e:
        print(f"Error during sentiment analysis for text: '{text_content[:50]}...': {e}")
        return {"label": "ANALYSIS_FAILED", "score": 0.0}

def add_sentiment_to_dataframe(df, text_column_name="text"):
    """
    Adds sentiment analysis results (label and score) to a Pandas DataFrame.
    Assumes the DataFrame has a column with text to be analyzed.

    Args:
        df (pd.DataFrame): The input DataFrame.
        text_column_name (str): The name of the column containing the text.

    Returns:
        pd.DataFrame: The DataFrame with added 'sentiment_label' and 'sentiment_score' columns.
    """
    if df.empty or text_column_name not in df.columns:
        print(f"DataFrame is empty or text column '{text_column_name}' not found.")
        df['sentiment_label'] = "N/A"
        df['sentiment_score'] = 0.0
        return df

    sentiments = df[text_column_name].apply(lambda x: analyze_sentiment_text(str(x)))
    df['sentiment_label'] = sentiments.apply(lambda x: x['label'])
    df['sentiment_score'] = sentiments.apply(lambda x: x['score'])

    return df

# --- Zero-Shot Topic Classification ---
ZERO_SHOT_MODEL_NAME = "facebook/bart-large-mnli"
try:
    topic_classifier = pipeline("zero-shot-classification", model=ZERO_SHOT_MODEL_NAME)
    print(f"Zero-shot classification pipeline loaded successfully with model: {ZERO_SHOT_MODEL_NAME}")
except Exception as e:
    print(f"Error loading zero-shot classification model '{ZERO_SHOT_MODEL_NAME}': {e}")
    print("Please ensure you have an internet connection for the first download, or the model is cached.")
    print("Falling back to a placeholder function for topic classification.")
    # Placeholder function if model loading fails
    def topic_classifier_placeholder(text, candidate_labels): # Renamed for clarity
        # Simple rule-based placeholder
        return {"labels": [candidate_labels[0] if candidate_labels else "general"], "scores": [0.1]}
    topic_classifier = topic_classifier_placeholder

def classify_text_zero_shot(text_content, candidate_topics):
    """
    Classifies a single piece of text against a list of candidate topics
    using a zero-shot classification model.
    Returns a dictionary with 'topic' (highest scoring) and 'score'.
    """
    if not text_content or not isinstance(text_content, str) or not candidate_topics:
        return {"topic": "INVALID_INPUT", "score": 0.0}
    try:
        results = topic_classifier(text_content, candidate_labels=candidate_topics)
        if results and 'labels' in results and 'scores' in results:
            # The pipeline returns lists of labels and scores, sorted by score.
            return {"topic": results['labels'][0], "score": round(results['scores'][0], 4)}
        else:
            return {"topic": "ANALYSIS_ERROR", "score": 0.0}
    except Exception as e:
        print(f"Error during zero-shot classification for text: '{text_content[:50]}...': {e}")
        return {"topic": "ANALYSIS_FAILED", "score": 0.0}

def add_topic_classification_to_dataframe(df, candidate_topics, text_column_name="text"):
    """
    Adds zero-shot topic classification results to a Pandas DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        candidate_topics (list): A list of strings representing the topics to classify against.
        text_column_name (str): The name of the column containing the text.

    Returns:
        pd.DataFrame: The DataFrame with added 'topic' and 'topic_score' columns.
    """
    if df.empty or text_column_name not in df.columns:
        print(f"DataFrame is empty or text column '{text_column_name}' not found.")
        df['topic'] = "N/A"
        df['topic_score'] = 0.0
        return df

    if not candidate_topics:
        print("No candidate topics provided for classification.")
        df['topic'] = "NO_TOPICS_DEFINED"
        df['topic_score'] = 0.0
        return df

    topics = df[text_column_name].apply(lambda x: classify_text_zero_shot(str(x), candidate_topics))
    df['topic'] = topics.apply(lambda x: x['topic'])
    df['topic_score'] = topics.apply(lambda x: x['score'])

    return df

if __name__ == "__main__":
    print("\n--- Testing Sentiment Analysis ---")
    sample_texts = [
        "This is a wonderful day, full of joy and happiness!",
        "I am feeling very sad and frustrated about the news.",
        "The weather is okay today, neither good nor bad.",
        "This is outrageous and completely unacceptable behavior.",
        "What an amazing achievement, congratulations!",
        "" # Empty string
    ]

    # Test single text analysis
    for text in sample_texts:
        if text:
            sentiment = analyze_sentiment_text(text)
            print(f"Text: {text}\nSentiment: {sentiment}\n")
        else:
            print(f"Text: (Empty String)\nSentiment: {analyze_sentiment_text(text)}\n")

    # Test DataFrame integration
    print("\n--- Testing Sentiment DataFrame Integration ---") # Clarified title
    data = {
        'id': [1, 2, 3, 4],
        'post_text': [
            "Loved the new movie, it was fantastic!",
            "The service at the restaurant was terrible.",
            "Just a regular Tuesday morning.",
            "This is an interesting development."
        ],
        'user': ['Alice', 'Bob', 'Charlie', 'David']
    }
    sample_df = pd.DataFrame(data)

    print("Original DataFrame for Sentiment Analysis:") # Clarified title
    print(sample_df)

    df_with_sentiment = add_sentiment_to_dataframe(sample_df, text_column_name="post_text")

    print("\nDataFrame with Sentiment Analysis:")
    print(df_with_sentiment)

    print("\nNLP Analyzer (Sentiment part) script finished.") # Clarified message

    # --- Testing Zero-Shot Topic Classification ---
    print("\n--- Testing Zero-Shot Topic Classification ---")
    sample_texts_for_topics = [
        "There are reports of escalating violence in the northern region.",
        "Peace talks are scheduled to begin next week between the warring factions.",
        "This new policy aims to improve healthcare and education.",
        "The election results were announced today amidst tight security.",
        "Humanitarian aid is urgently needed for the displaced populations."
    ]
    # Define candidate topics relevant to conflict and extremism monitoring
    conflict_topics = [
        "armed conflict", "ceasefire violation", "peace talks",
        "humanitarian crisis", "displacement", "election security",
        "extremist propaganda", "hate speech", "human rights abuse",
        "political instability", "social unrest"
    ]

    for text in sample_texts_for_topics:
        if text: # Added check for empty string, though not in sample
            topic_info = classify_text_zero_shot(text, conflict_topics)
            print(f"Text: {text}\nTopic: {topic_info['topic']} (Score: {topic_info['score']})\n")

    print("\n--- Testing Topic Classification DataFrame Integration ---")
    topic_data = {
        'id': [101, 102, 103],
        'message_text': [
            "A new round of negotiations has been announced.",
            "Protests have broken out in the capital city over new legislation.",
            "The government is deploying troops to the border region."
        ]
    }
    topic_df = pd.DataFrame(topic_data)
    print("Original DataFrame for Topic Classification:")
    print(topic_df)

    df_with_topics = add_topic_classification_to_dataframe(topic_df, conflict_topics, text_column_name="message_text")
    print("\nDataFrame with Topic Classification:")
    print(df_with_topics)

    print("\nNLP Analyzer script (with topic classification) finished testing.")
