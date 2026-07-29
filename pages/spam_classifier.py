import re
from collections import Counter


TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.IGNORECASE)
STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been",
    "before", "being", "but", "can", "could", "did", "does", "for", "from",
    "had", "has", "have", "hello", "here", "how", "into", "just", "like",
    "message", "more", "not", "our", "please", "should", "that", "the",
    "their", "them", "then", "there", "they", "this", "through", "very",
    "want", "was", "website", "were", "what", "when", "where", "which",
    "who", "will", "with", "would", "you", "your",
}
MINIMUM_SPAM_MESSAGES = 3


def tokenize(message):
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(message or "")
        if token.lower() not in STOP_WORDS
    }


def learn_spam_terms(spam_messages, legitimate_messages):
    spam_documents = [tokenize(message) for message in spam_messages]
    legitimate_documents = [tokenize(message) for message in legitimate_messages]
    if len(spam_documents) < MINIMUM_SPAM_MESSAGES:
        return {}

    spam_frequency = Counter(
        token for document in spam_documents for token in document
    )
    legitimate_frequency = Counter(
        token for document in legitimate_documents for token in document
    )
    spam_count = len(spam_documents)
    legitimate_count = len(legitimate_documents)
    learned_terms = {}

    for token, occurrences in spam_frequency.items():
        spam_ratio = occurrences / spam_count
        legitimate_ratio = (
            legitimate_frequency[token] / legitimate_count
            if legitimate_count
            else 0
        )
        if occurrences >= 2 and spam_ratio >= 0.6 and legitimate_ratio <= 0.2:
            learned_terms[token] = spam_ratio - legitimate_ratio
    return learned_terms


def is_likely_spam(message, spam_messages, legitimate_messages):
    learned_terms = learn_spam_terms(spam_messages, legitimate_messages)
    matches = {
        token: learned_terms[token]
        for token in tokenize(message)
        if token in learned_terms
    }
    if len(matches) >= 2 and sum(matches.values()) >= 1.2:
        return True, sorted(matches)
    return False, sorted(matches)
