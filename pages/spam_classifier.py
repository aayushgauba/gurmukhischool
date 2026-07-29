import re
import math
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
MINIMUM_LEGITIMATE_MESSAGES = 5
MINIMUM_TERM_DOCUMENT_RATIO = 0.05


def tokenize(message):
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(message or "")
        if token.lower() not in STOP_WORDS
    }


def learn_spam_terms(spam_messages, legitimate_messages):
    spam_documents = [tokenize(message) for message in spam_messages]
    legitimate_documents = [tokenize(message) for message in legitimate_messages]
    if (
        len(spam_documents) < MINIMUM_SPAM_MESSAGES
        or len(legitimate_documents) < MINIMUM_LEGITIMATE_MESSAGES
    ):
        return {}

    spam_frequency = Counter(
        token for document in spam_documents for token in document
    )
    legitimate_frequency = Counter(
        token for document in legitimate_documents for token in document
    )
    spam_count = len(spam_documents)
    legitimate_count = len(legitimate_documents)
    minimum_occurrences = max(
        2,
        math.ceil(spam_count * MINIMUM_TERM_DOCUMENT_RATIO),
    )
    learned_terms = {}

    for token, occurrences in spam_frequency.items():
        spam_ratio = occurrences / spam_count
        legitimate_ratio = (
            legitimate_frequency[token] / legitimate_count
            if legitimate_count
            else 0
        )
        legitimate_limit = max(0.1, spam_ratio * 0.75)
        if (
            occurrences >= minimum_occurrences
            and legitimate_ratio <= legitimate_limit
        ):
            learned_terms[token] = max(
                0.1,
                min(1.0, 0.55 + (spam_ratio * 3))
                - min(0.45, legitimate_ratio * 2),
            )
    return learned_terms


def match_spam_terms(message, learned_terms):
    matches = {
        token: learned_terms[token]
        for token in tokenize(message)
        if token in learned_terms
    }
    if len(matches) >= 2 and sum(matches.values()) >= 1.2:
        return True, sorted(matches)
    return False, sorted(matches)


def is_likely_spam(message, spam_messages, legitimate_messages):
    return match_spam_terms(
        message,
        learn_spam_terms(spam_messages, legitimate_messages),
    )
