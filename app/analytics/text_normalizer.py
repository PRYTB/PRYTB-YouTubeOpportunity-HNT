import re
import unicodedata
from typing import Optional, Dict, Any, Tuple

# List of key tech terms to explicitly protect or preserve case sensitivity/formatting
PRESERVED_TERMS = [
    "GPT-5", "GPT-4", "GPT-4o", "GPT-3.5",
    "Windows 11", "Windows 10",
    "RTX 5090", "RTX 4090", "RTX 3090",
    "Python", "ChatGPT", "Claude", "Gemini", "Llama",
    "YouTube", "DeepSeek", "OpenAI"
]

def clean_text_for_embedding(title: Optional[str], description: Optional[str] = None, max_desc_len: int = 200) -> str:
    """
    Moderate text normalization that preserves essential technical terms, Unicode, and semantic meaning.
    Combines title and a controlled snippet of description.
    Excludes statistical signals (views, subscribers, outlier ratio, channel name).
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
    - Removes URLs
    - Normalizes whitespace
    - Preserves protected terms
    - Removes aggressive non-alphanumeric noise while retaining letters, digits, basic punctuation, and emojis.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode normalization (NFKC converts weird unicode characters to standard forms)
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove URLs
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # 3. Create a map of protected terms to placeholders
    placeholder_map: Dict[str, str] = {}
    temp_text = text
    for idx, term in enumerate(PRESERVED_TERMS):
        placeholder = f"__PROTECTED_TERM_{idx}__"
        # Match word boundaries case-insensitively
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(temp_text):
            placeholder_map[placeholder] = term
            temp_text = pattern.sub(placeholder, temp_text)

    # 4. Convert non-protected text to lowercase
    temp_text = temp_text.lower()

    # 5. Remove unwanted symbols but keep numbers, letters, spaces, emojis, hyphen
    # Remove control characters
    temp_text = "".join(ch for ch in temp_text if unicodedata.category(ch)[0] != "C")
    
    # 6. Normalize whitespace
    temp_text = re.sub(r"\s+", " ", temp_text).strip()

    # 7. Restore protected terms
    for placeholder, term in placeholder_map.items():
        temp_text = temp_text.replace(placeholder.lower(), term)

    return temp_text
