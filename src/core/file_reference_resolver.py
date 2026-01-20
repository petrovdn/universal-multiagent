"""
File Reference Resolver - resolves user queries to relevant files.

This module implements:
1. Keyword extraction from document text
2. Reference resolution from user queries to specific files
3. Integration with ConversationContext for file management

Following Cursor-style "Exploring" approach:
- Parse query to understand what user is asking about
- Look up entities/files that match the query
- Return only relevant files, not all files
"""

from __future__ import annotations
import re
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from src.core.entity_memory import EntityMemory

if TYPE_CHECKING:
    from src.core.context_manager import ConversationContext


# Common Russian stopwords to exclude from keywords
RUSSIAN_STOPWORDS = {
    'и', 'в', 'на', 'с', 'по', 'к', 'у', 'о', 'за', 'от', 'из', 'до',
    'что', 'как', 'это', 'для', 'он', 'она', 'они', 'мы', 'вы', 'я',
    'но', 'а', 'же', 'ли', 'бы', 'не', 'ни', 'да', 'нет',
    'его', 'её', 'их', 'мне', 'тебе', 'вам', 'нам', 'ему', 'ей', 'им',
    'все', 'всё', 'весь', 'вся', 'этот', 'тот', 'эта', 'та', 'эти', 'те',
    'который', 'которая', 'которое', 'которые', 'какой', 'какая', 'какое',
    'чтобы', 'если', 'когда', 'где', 'куда', 'откуда', 'почему', 'зачем',
    'так', 'там', 'тут', 'здесь', 'сейчас', 'потом', 'только', 'уже', 'ещё',
    'быть', 'был', 'была', 'было', 'были', 'есть', 'будет', 'будут',
    'мочь', 'может', 'могут', 'можно', 'нужно', 'надо', 'должен',
    # Document-related stopwords
    'файл', 'документ', 'содержит', 'содержимое', 'текст',
    'расскажи', 'покажи', 'опиши', 'скажи', 'подробнее', 'подробно',
    'про', 'об', 'информация', 'данные',
}

# Important domain keywords to always include
IMPORTANT_KEYWORDS = {
    # Insurance
    'страхов': ['страхов', 'страховка', 'страховой', 'страхование', 'полис', 'каско', 'осаго'],
    # Tax
    'налог': ['налог', 'налоговый', 'налоговое', 'ндфл', 'ифнс'],
    # Vehicle
    'автомобиль': ['автомобиль', 'машина', 'авто', 'транспорт', 'kia', 'sportage'],
    # Strategy
    'стратегия': ['стратегия', 'стратегический', 'okr', 'цели', 'методология'],
    # People/images
    'человек': ['человек', 'девушка', 'мужчина', 'женщина', 'люди', 'игрок'],
    # Sports
    'спорт': ['теннис', 'спорт', 'игра', 'играет', 'мяч'],
}


def normalize_word(word: str) -> str:
    """
    Normalize a word by converting to lowercase and removing special chars.
    Also creates a stem-like form for better matching.
    """
    word = word.lower().strip()
    word = re.sub(r'[^\w\s]', '', word)
    return word


def get_word_stem(word: str) -> str:
    """
    Get a simple stem of a Russian word for fuzzy matching.
    This is a basic stemmer - just removes common suffixes.
    """
    word = normalize_word(word)
    
    # Remove common Russian suffixes for basic stemming
    suffixes = ['овка', 'евка', 'ость', 'ение', 'ание', 'ация', 'ский', 'ская', 'ское', 
                'ного', 'ной', 'ному', 'овый', 'овая', 'овое',
                'ный', 'ная', 'ное', 'ные', 'ных',
                'ой', 'ый', 'ая', 'ое', 'ые', 'ых',
                'ом', 'ем', 'ей', 'ах', 'ям', 'ами',
                'ка', 'ки', 'ку', 'ке', 'кой', 'ков',
                'ы', 'и', 'а', 'я', 'у', 'ю', 'е', 'о']
    
    for suffix in suffixes:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[:-len(suffix)]
    
    return word


def extract_keywords_from_text(text: str) -> List[str]:
    """
    Extract relevant keywords from document text.
    
    Args:
        text: Document text content
        
    Returns:
        List of keywords extracted from the text (lowercased, unique)
    """
    if not text:
        return []
    
    # Split into words
    words = re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', text.lower())
    
    keywords = set()
    
    for word in words:
        # Skip short words and stopwords
        if len(word) < 3 or word in RUSSIAN_STOPWORDS:
            continue
        
        # Check if word matches any important keyword group
        word_stem = get_word_stem(word)
        for key, variants in IMPORTANT_KEYWORDS.items():
            for variant in variants:
                if (word == variant or 
                    word.startswith(variant[:4]) or 
                    word_stem == get_word_stem(variant)):
                    keywords.add(word)
                    # Also add the stem for better matching
                    if len(word_stem) >= 4:
                        keywords.add(word_stem)
                    break
        
        # Also add words that look like domain-specific terms
        if len(word) >= 4 and word not in RUSSIAN_STOPWORDS:
            # Add proper nouns (likely important)
            if word[0].isupper() and len(word) > 1:
                keywords.add(word.lower())
            # Add numbers/codes
            if any(c.isdigit() for c in word):
                keywords.add(word)
            # Add long words that might be terms
            if len(word) >= 5:
                keywords.add(word)
    
    return list(keywords)


def resolve_file_reference(query: str, entity_memory: EntityMemory) -> Optional[str]:
    """
    Resolve a user query to a specific file ID based on keywords.
    
    Uses keyword matching to find the most relevant file.
    
    Args:
        query: User's query/question
        entity_memory: EntityMemory containing file references with keywords
        
    Returns:
        File ID if a matching file is found, None otherwise
    """
    if not query or not entity_memory:
        return None
    
    # Get all file entities
    file_entities = entity_memory._entities.get("file", [])
    if not file_entities:
        return None
    
    # Extract keywords from query
    query_lower = query.lower()
    query_words = set(re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', query_lower))
    query_stems = {get_word_stem(w) for w in query_words if len(w) >= 3}
    
    # Score each file by keyword overlap
    best_file_id = None
    best_score = 0
    
    for entity in file_entities:
        file_keywords = entity.metadata.get("keywords", [])
        if not file_keywords:
            continue
        
        score = 0
        file_keyword_stems = {get_word_stem(kw) for kw in file_keywords}
        
        # Check for exact keyword matches
        for query_word in query_words:
            if query_word in file_keywords:
                score += 3  # Exact match
            
            # Check for stem matches
            query_stem = get_word_stem(query_word)
            for file_kw in file_keywords:
                file_stem = get_word_stem(file_kw)
                if query_stem == file_stem and len(query_stem) >= 4:
                    score += 2  # Stem match
                elif query_stem in file_stem or file_stem in query_stem:
                    if len(min(query_stem, file_stem)) >= 4:
                        score += 1  # Partial stem match
        
        # Check for important keyword group matches
        for key, variants in IMPORTANT_KEYWORDS.items():
            query_has_key = any(v in query_lower or get_word_stem(v) in query_stems 
                               for v in variants)
            file_has_key = any(v in ' '.join(file_keywords).lower() 
                              for v in variants)
            
            if query_has_key and file_has_key:
                score += 5  # Domain match is very important
        
        if score > best_score:
            best_score = score
            best_file_id = entity.entity_id
    
    return best_file_id if best_score > 0 else None


def add_file_with_keywords(context: "ConversationContext", file_id: str, file_data: Dict[str, Any]) -> None:
    """
    Add file to context and entity_memory with extracted keywords.
    
    Args:
        context: ConversationContext to add file to
        file_id: Unique file identifier
        file_data: File metadata including filename, type, and text content
    """
    filename = file_data.get("filename", "unknown")
    file_type = file_data.get("type", "application/octet-stream")
    text_content = file_data.get("text", "")
    
    # Extract keywords from text content
    keywords = extract_keywords_from_text(text_content)
    
    # Also add filename parts as keywords
    filename_parts = re.findall(r'[а-яёА-ЯЁa-zA-Z0-9]+', filename.lower())
    keywords.extend([p for p in filename_parts if len(p) >= 3 and p not in RUSSIAN_STOPWORDS])
    
    # Create description from first few sentences
    sentences = re.split(r'[.!?\n]', text_content)
    description = '. '.join(s.strip() for s in sentences[:2] if s.strip())[:200]
    
    # Add to entity_memory
    context.entity_memory.add_reference(
        entity_type="file",
        entity_id=file_id,
        name=filename,
        metadata={
            "type": file_type,
            "keywords": list(set(keywords)),
            "description": description
        }
    )


def get_relevant_file_ids(query: str, context: "ConversationContext") -> List[str]:
    """
    Get list of file IDs relevant to the query.
    
    Args:
        query: User's query
        context: ConversationContext with files and entity_memory
        
    Returns:
        List of relevant file IDs (may be empty, single, or multiple)
    """
    if not query or not context or not hasattr(context, 'entity_memory'):
        return []
    
    # First try to resolve to a specific file
    resolved_id = resolve_file_reference(query, context.entity_memory)
    
    if resolved_id:
        return [resolved_id]
    
    # If no specific match, return empty (or could return all for "general" queries)
    return []


def find_source_for_reference(query: str, context: "ConversationContext") -> List[str]:
    """
    Find source files for a reference in the user query by searching conversation history.
    
    Looks for keywords from the query in previous assistant messages,
    and returns the source_files from the matching message's metadata.
    
    This enables follow-up questions like "расскажи про человека" to find
    the image where "человек" was mentioned.
    
    Args:
        query: User's follow-up query
        context: ConversationContext with message history
        
    Returns:
        List of file IDs that were sources for the relevant information
    """
    if not query or not context or not hasattr(context, 'messages'):
        return []
    
    # Extract keywords from query
    query_keywords = extract_keywords_from_text(query)
    if not query_keywords:
        # Try simpler extraction for short queries
        query_lower = query.lower()
        query_words = set(re.findall(r'[а-яёА-ЯЁa-zA-Z]+', query_lower))
        query_keywords = [w for w in query_words if len(w) >= 4 and w not in RUSSIAN_STOPWORDS]
    
    if not query_keywords:
        return []
    
    # Search in conversation history (reverse order - most recent first)
    for msg in reversed(context.messages):
        if msg.get("role") != "assistant":
            continue
        
        content = msg.get("content", "").lower()
        metadata = msg.get("metadata", {})
        source_files = metadata.get("source_files", [])
        
        if not source_files:
            continue
        
        # Check if any query keyword appears in the message content
        matched_keywords = []
        for keyword in query_keywords:
            keyword_lower = keyword.lower()
            keyword_stem = get_word_stem(keyword_lower)
            
            # Check for exact match or stem match in content
            if keyword_lower in content:
                matched_keywords.append(keyword)
                # CRITICAL FIX: If multiple files, try to filter by entity_memory
                if len(source_files) > 1 and hasattr(context, 'entity_memory') and context.entity_memory:
                    # Try to find the most relevant file using entity_memory
                    resolved_id = resolve_file_reference(query, context.entity_memory)
                    if resolved_id and resolved_id in source_files:
                        # Found specific file - return only that one
                        return [resolved_id]
                # If single file or couldn't narrow down, return all (legacy behavior)
                return source_files
            
            # Check for stem match
            content_words = set(re.findall(r'[а-яёА-ЯЁa-zA-Z]+', content))
            for content_word in content_words:
                if get_word_stem(content_word) == keyword_stem and len(keyword_stem) >= 4:
                    matched_keywords.append(keyword)
                    # CRITICAL FIX: If multiple files, try to filter by entity_memory
                    if len(source_files) > 1 and hasattr(context, 'entity_memory') and context.entity_memory:
                        resolved_id = resolve_file_reference(query, context.entity_memory)
                        if resolved_id and resolved_id in source_files:
                            return [resolved_id]
                    return source_files
        
        # Also check against extracted_entities in metadata
        extracted_entities = metadata.get("extracted_entities", [])
        for keyword in query_keywords:
            keyword_stem = get_word_stem(keyword.lower())
            for entity in extracted_entities:
                entity_stem = get_word_stem(entity.lower())
                if keyword_stem == entity_stem or keyword.lower() in entity.lower():
                    # CRITICAL FIX: If multiple files, try to filter by entity_memory
                    if len(source_files) > 1 and hasattr(context, 'entity_memory') and context.entity_memory:
                        resolved_id = resolve_file_reference(query, context.entity_memory)
                        if resolved_id and resolved_id in source_files:
                            return [resolved_id]
                    return source_files
    
    return []


def extract_entities_from_response(response: str) -> List[str]:
    """
    Extract key entities/terms from an agent response.
    
    These entities are saved in message metadata to enable
    reference resolution in follow-up queries.
    
    Args:
        response: Agent's response text
        
    Returns:
        List of extracted entity keywords
    """
    if not response:
        return []
    
    # Use the same keyword extraction logic
    keywords = extract_keywords_from_text(response)
    
    # Also extract domain-specific terms using IMPORTANT_KEYWORDS
    response_lower = response.lower()
    response_words = set(re.findall(r'[а-яёА-ЯЁa-zA-Z]+', response_lower))
    
    for key, variants in IMPORTANT_KEYWORDS.items():
        for variant in variants:
            if variant in response_lower:
                keywords.append(variant)
            # Also check if any word starts with the variant stem
            variant_stem = get_word_stem(variant)
            for word in response_words:
                if get_word_stem(word) == variant_stem and len(variant_stem) >= 4:
                    keywords.append(word)
    
    # Remove duplicates and return
    return list(set(keywords))
