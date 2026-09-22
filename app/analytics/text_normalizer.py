import re
import unicodedata
from typing import Optional, Dict, Any, List, Tuple

# List of key tech/entity terms to explicitly protect or preserve case sensitivity/formatting
PRESERVED_TERMS = [
    "Artificial Intelligence", "AI Safety", "AI Agents", "AI Regulation",
    "Cybersecurity", "Network Security", "ChatGPT", "GPT-5", "GPT-4", "GPT-4o", "GPT-3.5",
    "Google", "OpenAI", "Claude", "Gemini", "Llama", "DeepSeek", "Python",
    "Windows 11", "Windows 10", "RTX 5090", "RTX 4090", "YouTube"
]

# Common Spanish and English stopwords for intent validation and filtering
SPANISH_STOPWORDS = {
    'de', 'la', 'el', 'en', 'y', 'a', 'los', 'del', 'las', 'un', 'por', 'con', 'no',
    'una', 'su', 'para', 'es', 'al', 'lo', 'como', 'más', 'o', 'pero', 'sus', 'le',
    'ha', 'me', 'si', 'sin', 'sobre', 'este', 'ya', 'entre', 'cuando', 'todo', 'esta',
    'ser', 'son', 'dos', 'también', 'fue', 'había', 'era', 'muy', 'años', 'hasta',
    'desde', 'está', 'mi', 'porque', 'qué', 'solo', 'han', 'yo', 'hay', 'como', 'cómo', 'c¾mo'
}

ENGLISH_STOPWORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for',
    'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his',
    'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will', 'my',
    'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out', 'if',
    'about', 'who', 'get', 'which', 'go', 'me', 'how', 'why'
}

COMMON_STOPWORDS = SPANISH_STOPWORDS.union(ENGLISH_STOPWORDS)

# Terms that are generic noise in titles/descriptions when building semantic vectors
GENERIC_STOP_WORDS = {
    "what", "how", "why", "video", "explained", "full", "guide", "tutorial",
    "watch", "channel", "subscribe", "link", "description", "video", "videos"
}

def normalize_intent_string(text: str) -> str:
    """
    Normalizes a raw subniche intent string:
    - Cleans via normalize_single_text
    - Deduplicates adjacent identical tokens (e.g. 'de de software' -> 'de software')
    - Removes trailing/leading duplicate tokens
    - Filters out single-character tokens unless preserved
    """
    if not text or not isinstance(text, str):
        return ""
    
    cleaned = normalize_single_text(text)
    tokens = [w for w in cleaned.split() if len(w) > 1 or w in PRESERVED_TERMS]
    
    # Deduplicate adjacent tokens (e.g., "de de" -> "de")
    deduped = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
            
    return " ".join(deduped)

def validate_intent_semantic_quality(intent: str) -> Tuple[bool, str]:
    """
    Validates whether a normalized intent represents a meaningful semantic topic.
    Rejects:
    - Empty or whitespace-only intents
    - Stopword-only intents (e.g., 'es la', 'de en', 'es es la')
    - Connective-word-only intents
    - Intents with zero non-stopword / meaningful tokens
    Returns (is_valid: bool, rejection_reason: str).
    """
    if not intent or not isinstance(intent, str) or not intent.strip():
        return False, "EMPTY_INTENT"
        
    cleaned_intent = normalize_intent_string(intent)
    tokens = cleaned_intent.lower().split()
    
    if not tokens:
        return False, "NO_VALID_TOKENS"
        
    # 1. Stopword-only check
    meaningful_tokens = [t for t in tokens if t not in COMMON_STOPWORDS and t not in GENERIC_STOP_WORDS]
    
    if not meaningful_tokens:
        return False, "STOPWORD_ONLY_ARTIFACT"
        
    return True, "VALID"

def clean_text_for_embedding(title: Optional[str], description: Optional[str] = None, max_desc_len: int = 300) -> str:
    """
    Constructs semantic_text from title + useful snippet of description.
    Excludes statistical signals (views, subscribers, channel name, outlier ratio).
    Applies moderate normalization while preserving technical entities.
    """
    clean_title = normalize_single_text(title or "")
    
    clean_desc = ""
    if description and isinstance(description, str) and description.strip():
        # Truncate description to max_desc_len controlled chars
        desc_snippet = description.strip()[:max_desc_len]
        clean_desc = normalize_single_text(desc_snippet)

    if clean_title and clean_desc:
        combined = f"{clean_title} . {clean_desc}"
    else:
        combined = clean_title or clean_desc or "untitled"

    return combined.strip()


def normalize_single_text(text: str) -> str:
    """
    Normalizes a single text string:
    - Normalizes Unicode (NFKC)
    - Removes URLs & social media links
    - Preserves protected entities
    - Lowercases non-protected text
    - Removes structural noisy terms if they add no semantic value
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # 3. Create a map of protected terms to placeholders
    placeholder_map: Dict[str, str] = {}
    temp_text = text
    for idx, term in enumerate(PRESERVED_TERMS):
        placeholder = f"__PROTECTED_TERM_{idx}__"
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(temp_text):
            placeholder_map[placeholder] = term
            temp_text = pattern.sub(placeholder, temp_text)

    # 4. Convert non-protected text to lowercase
    temp_text = temp_text.lower()

    # 5. Remove control characters and non-alphanumeric punctuation except space and hyphen
    temp_text = "".join(ch for ch in temp_text if unicodedata.category(ch)[0] != "C")
    temp_text = re.sub(r"[^\w\s-]", " ", temp_text)
    
    # 6. Normalize whitespace
    temp_text = re.sub(r"\s+", " ", temp_text).strip()

    # 7. Restore protected terms
    for placeholder, term in placeholder_map.items():
        temp_text = temp_text.replace(placeholder.lower(), term)

    return temp_text

