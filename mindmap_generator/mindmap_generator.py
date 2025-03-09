import re
import os
import json
import time
import asyncio
import hashlib
import copy
from typing import Dict, Any, List, Union, Optional, Set
from termcolor import colored
from fuzzywuzzy import fuzz
from .config import get_logger
from .document_optimizer import DocumentOptimizer
from .models import DocumentType, ContentItem
from .llm_client import LLMClient
from .prompt_strategy import PromptStrategy
logger = get_logger()


class MindMapGenerationError(Exception):
    """Custom exception for mindmap generation errors."""
    pass



class MindMapGenerator:
    def __init__(self):
        self.prompt_strategy = PromptStrategy()
        self.optimizer = DocumentOptimizer()
        self.config = {
            'max_summary_length': 2500,
            'max_tokens': 3000,
            'valid_types': [t.name.lower() for t in DocumentType],
            'default_type': DocumentType.GENERAL.name.lower(),
            'max_retries': 3,
            'request_timeout': 30,  # seconds
            'chunk_size': 8192,     # bytes for file operations
            'max_topics': 6,        # Maximum main topics
            'max_subtopics': 4,     # Maximum subtopics per topic
            'max_details': 8,       # Maximum details per subtopic
            'similarity_threshold': {
                'topic': 75,        # Allow more diverse main topics
                'subtopic': 70,     # Allow more nuanced subtopics
                'detail': 65        # Allow more specific details
            },
            'reality_check': {
                'batch_size': 8,    # Number of nodes to verify in parallel
                'min_verified_topics': 4,  # Minimum verified topics needed
                'min_verified_ratio': 0.6  # Minimum ratio of verified content
            }
        }
        self.verification_stats = {
            'total_nodes': 0,
            'verified_nodes': 0,
            'topics': {'total': 0, 'verified': 0},
            'subtopics': {'total': 0, 'verified': 0},
            'details': {'total': 0, 'verified': 0}
        }
        self._emoji_cache = {}
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 1,
            'max_delay': 10,
            'jitter': 0.1,
            'timeout': 30
        }
        self._emoji_file = os.path.join(os.path.dirname(__file__), "emoji_cache.json")
        self._load_emoji_cache()
        self.llm_client = LLMClient(self.optimizer, self.retry_config)
        self.numbered_pattern = re.compile(r'^\s*\d+\.\s*(.+)$')
        self.parentheses_regex = re.compile(r'(\((?!\()|(?<!\))\))')
        self.percentage_regex1 = re.compile(r'(\d+(?:\.\d+)?)\s+(?=percent|of\s|share|margin|CAGR)', re.IGNORECASE)
        self.percentage_regex2 = re.compile(r'\s+percent\b', re.IGNORECASE)
        self.backslash_regex = re.compile(r'\\{2,}')
        self.special_chars_regex = re.compile(r'[^a-zA-Z0-9\s\[\]\(\)\{\}\'_\-.,`*%\\]')
        self.paren_replacements = {
            '(': '❨',  # U+2768 MEDIUM LEFT PARENTHESIS ORNAMENT
            ')': '❩',  # U+2769 MEDIUM RIGHT PARENTHESIS ORNAMENT
        }

    def _load_emoji_cache(self):
        """Load emoji cache from disk if available."""
        try:
            if os.path.exists(self._emoji_file):
                with open(self._emoji_file, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                    # Convert tuple string keys back to actual tuples
                    self._emoji_cache = {tuple(eval(k)): v for k, v in loaded_cache.items()}
                    logger.info(f"Loaded {len(self._emoji_cache)} emoji mappings from cache")
            else:
                self._emoji_cache = {}
        except Exception as e:
            logger.warning(f"Failed to load emoji cache: {str(e)}")
            self._emoji_cache = {}

    def _save_emoji_cache(self):
        """Save emoji cache to disk for reuse across runs."""
        try:
            # Convert tuple keys to strings for JSON serialization
            serializable_cache = {str(k): v for k, v in self._emoji_cache.items()}
            with open(self._emoji_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_cache, f)
            logger.info(f"Saved {len(self._emoji_cache)} emoji mappings to cache")
        except Exception as e:
            logger.warning(f"Failed to save emoji cache: {str(e)}")

    def _get_importance_marker(self, importance: str) -> str:
        """Get the appropriate diamond marker based on importance level."""
        markers = {
            'high': '♦️',    # Red diamond for high importance
            'medium': '🔸',  # Orange diamond for medium importance
            'low': '🔹'      # Blue diamond for low importance
        }
        return markers.get(importance.lower(), '🔹')

    async def _save_emoji_cache_async(self):
        """Asynchronous version of save_emoji_cache to avoid blocking."""
        try:
            # Convert to a non-blocking call
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_emoji_cache)
        except Exception as e:
            logger.warning(f"Failed to save emoji cache asynchronously: {str(e)}")
            
    async def _select_emoji(self, text: str, node_type: str = 'topic') -> str:
        """Select appropriate emoji for node content with persistent cache."""
        cache_key = (text, node_type)
        
        # First check in-memory cache
        if cache_key in self._emoji_cache:
            return self._emoji_cache[cache_key]
            
        # If not in cache, generate emoji
        try:
            prompt = f"""Select the single most appropriate emoji to represent this {node_type}: "{text}"

            Requirements:
            1. Return ONLY the emoji character - no explanations or other text
            2. Choose an emoji that best represents the concept semantically
            3. For abstract concepts, use metaphorical or symbolic emojis
            4. Default options if unsure:
            - Topics: 📄 (document)
            - Subtopics: 📌 (pin)
            - Details: 🔹 (bullet point)
            5. Be creative but clear - the emoji should intuitively represent the concept

            Examples:
            - "Market Growth" → 📈
            - "Customer Service" → 👥
            - "Financial Report" → 💰
            - "Product Development" → ⚙️
            - "Global Expansion" → 🌐
            - "Research and Development" → 🔬
            - "Digital Transformation" → 💻
            - "Supply Chain" → 🔄
            - "Healthcare Solutions" → 🏥
            - "Security Measures" → 🔒

            Return ONLY the emoji character without any explanation."""
            
            response = await self.llm_client._retry_generate_completion(
                prompt,
                max_tokens=20,
                request_id='',
                task="selecting_emoji"
            )
            
            # Clean the response to get just the emoji
            emoji = response.strip()
            
            # If no emoji was returned or response is too long, use defaults
            if not emoji or len(emoji) > 4:  # Most emojis are 2 chars, some are 4
                defaults = {
                    'topic': '📄',
                    'subtopic': '📌',
                    'detail': '🔹'
                }
                emoji = defaults.get(node_type, '📄')
                
            # Add to in-memory cache
            self._emoji_cache[cache_key] = emoji
            
            # Save cache to disk periodically (every 10 new emojis)
            if len(self._emoji_cache) % 10 == 0:
                await asyncio.create_task(self._save_emoji_cache_async())
                
            return emoji
            
        except Exception as e:
            logger.warning(f"Error selecting emoji: {str(e)}")
            return '📄' if node_type == 'topic' else '📌' if node_type == 'subtopic' else '🔹'

    @staticmethod
    def _create_node(name: str, importance: str = 'high', emoji: str = "") -> Dict[str, Any]:
        """Create a node dictionary with the given parameters.
        
        Args:
            name (str): The name/text content of the node
            importance (str): The importance level ('high', 'medium', 'low')
            emoji (str): The emoji to represent this node
            
        Returns:
            Dict[str, Any]: Node dictionary with all necessary attributes
        """
        return {
            'name': name,
            'importance': importance.lower(),
            'emoji': emoji,
            'subtopics': [],  # Initialize empty lists for children
            'details': []
        }
        
    def _escape_text(self, text: str) -> str:
        """Replace parentheses with Unicode alternatives and handle other special characters."""
        # Replace regular parentheses in content text with Unicode alternatives
        for original, replacement in self.paren_replacements.items():
            text = text.replace(original, replacement)
            
        # Handle percentages
        text = self.percentage_regex1.sub(r'\1%', text)
        text = self.percentage_regex2.sub('%', text)
        
        # Replace special characters while preserving needed symbols
        text = self.special_chars_regex.sub('', text)
        
        # Clean up multiple backslashes
        text = self.backslash_regex.sub(r'\\', text)
        
        return text

    def _format_node_line(self, node: Dict[str, Any], indent_level: int) -> str:
        """Format a single node in Mermaid syntax."""
        indent = '    ' * indent_level
        
        # For root node, always return just the document emoji
        if indent_level == 1:
            return f"{indent}((📄))"
        
        # Get the node text and escape it
        if 'text' in node:
            # For detail nodes
            importance = node.get('importance', 'low')
            marker = {'high': '♦️', 'medium': '🔸', 'low': '🔹'}[importance]
            text = self._escape_text(node['text'])
            return f"{indent}[{marker} {text}]"
        else:
            # For topic and subtopic nodes
            node_name = self._escape_text(node['name'])
            emoji = node.get('emoji', '')
            if emoji and node_name:
                node_name = f"{emoji} {node_name}"
            
            # For main topics (level 2)
            if indent_level == 2:
                return f"{indent}(({node_name}))"
            
            # For subtopics (level 3)
            return f"{indent}({node_name})"

    def _add_node_to_mindmap(self, node: Dict[str, Any], mindmap_lines: List[str], indent_level: int) -> None:
        """Recursively add a node and its children to the mindmap."""
        # Add the current node
        node_line = self._format_node_line(node, indent_level)
        mindmap_lines.append(node_line)
        
        # Add all subtopics first
        for subtopic in node.get('subtopics', []):
            self._add_node_to_mindmap(subtopic, mindmap_lines, indent_level + 1)
            
            # Then add details under each subtopic
            for detail in subtopic.get('details', []):
                detail_line = self._format_node_line({
                    'text': detail['text'],
                    'name': detail['text'],
                    'importance': detail['importance']  # Pass through the importance level
                }, indent_level + 2)
                mindmap_lines.append(detail_line)

    async def _batch_redundancy_check(self, items, content_type='topic', context_prefix='', batch_size=10):
        """Perform early batch redundancy checks to avoid wasting LLM calls.
        
        Args:
            items: List of items to check (topics or subtopics)
            content_type: Type of content ('topic' or 'subtopic')
            context_prefix: Optional context prefix for subtopics (e.g. parent topic name)
            batch_size: Maximum batch size for parallel processing
            
        Returns:
            List of non-redundant items
        """
        if not items or len(items) <= 1:
            return items
            
        # Process in batches for efficient parallel checking
        start_count = len(items)
        logger.info(f"Starting early redundancy check for {len(items)} {content_type}s...")
        
        # Track items to keep (non-redundant)
        unique_items = []
        seen_names = {}
        
        # First, use simple fuzzy matching to catch obvious duplicates
        for item in items:
            item_name = item['name']
            if not await self.is_similar_to_existing(item_name, seen_names, content_type):
                unique_items.append(item)
                seen_names[item_name] = item
        
        # If we still have lots of items, use more aggressive LLM-based similarity
        if len(unique_items) > 3 and len(unique_items) > len(items) * 0.8:  # Only if enough items and not much reduction yet
            try:
                # Create pairs for comparison
                pairs_to_check = []
                for i in range(len(unique_items)-1):
                    for j in range(i+1, len(unique_items)):
                        pairs_to_check.append((i, j))
                
                # Process in batches with semaphore for rate limiting
                redundant_indices = set()
                semaphore = asyncio.Semaphore(3)  # Limit concurrent LLM calls
                
                async def check_pair(i, j):
                    if i in redundant_indices or j in redundant_indices:
                        return None
                        
                    async with semaphore:
                        try:
                            context1 = context2 = content_type
                            if context_prefix:
                                context1 = context2 = f"{content_type} of {context_prefix}"
                                
                            is_redundant = await self.check_similarity_llm(
                                unique_items[i]['name'],
                                unique_items[j]['name'],
                                context1,
                                context2
                            )
                            
                            if is_redundant:
                                # Keep item with more detailed information
                                i_detail = len(unique_items[i].get('name', ''))
                                j_detail = len(unique_items[j].get('name', ''))
                                return (j, i) if i_detail > j_detail else (i, j)
                        except Exception as e:
                            logger.warning(f"Early redundancy check failed: {str(e)}")
                            
                    return None
                    
                # Process batches to maintain parallelism
                for batch_idx in range(0, len(pairs_to_check), batch_size):
                    batch = pairs_to_check[batch_idx:batch_idx + batch_size]
                    results = await asyncio.gather(*(check_pair(i, j) for i, j in batch))
                    
                    # Process results
                    for result in results:
                        if result:
                            redundant_idx, keep_idx = result
                            if redundant_idx not in redundant_indices:
                                redundant_indices.add(redundant_idx)
                                logger.info(f"Found redundant {content_type}: '{unique_items[redundant_idx]['name']}' similar to '{unique_items[keep_idx]['name']}'")
                
                # Filter out redundant items
                unique_items = [item for i, item in enumerate(unique_items) if i not in redundant_indices]
            except Exception as e:
                logger.error(f"Error in aggressive redundancy check: {str(e)}")
        
        reduction = start_count - len(unique_items)
        if reduction > 0:
            logger.info(f"Early redundancy check removed {reduction} redundant {content_type}s ({reduction/start_count*100:.1f}%)")
        
        return unique_items

    async def is_similar_to_existing(self, name: str, existing_names: Union[dict, set], content_type: str = 'topic') -> bool:
        """Check if name is similar to any existing names using stricter fuzzy matching thresholds.
        
        Args:
            name: Text to check for similarity
            existing_names: Dictionary or set of existing names to compare against
            content_type: Type of content being compared ('topic', 'subtopic', or 'detail')
            
        Returns:
            bool: True if similar content exists, False otherwise
        """
        # Lower thresholds to catch more duplicates
        base_threshold = {
            'topic': 75,      # Lower from 85 to catch more duplicates
            'subtopic': 70,   # Lower from 80 to catch more duplicates
            'detail': 65      # Lower from 75 to catch more duplicates
        }[content_type]
        
        # Get threshold for this content type
        threshold = base_threshold
        
        # Adjust threshold based on text length - be more lenient with longer texts
        if len(name) < 10:
            threshold = min(threshold + 10, 95)  # Stricter for very short texts
        elif len(name) > 100:
            threshold = max(threshold - 15, 55)  # More lenient for long texts
        
        # Make adjustments for content types to catch more duplicates
        if content_type == 'subtopic':
            threshold = max(threshold - 10, 60)  # Lower threshold to catch more duplicates
        elif content_type == 'detail':
            threshold = max(threshold - 10, 55)  # Lower threshold to catch more duplicates
        
        # Clean and normalize input text
        name = re.sub(r'\s+', ' ', name.lower().strip())
        name = re.sub(r'[^\w\s]', '', name)
        
        # Special handling for numbered items
        numbered_pattern = self.numbered_pattern
        name_without_number = numbered_pattern.sub(r'\1', name)
        
        # Handle both dict and set inputs
        existing_items = existing_names.keys() if isinstance(existing_names, dict) else existing_names
        
        for existing_name in existing_items:
            # Skip if lengths are vastly different
            existing_clean = re.sub(r'\s+', ' ', str(existing_name).lower().strip())
            existing_clean = re.sub(r'[^\w\s]', '', existing_clean)
            
            if abs(len(name) - len(existing_clean)) > len(name) * 0.7:  # Increased from 0.5
                continue
            
            # Calculate multiple similarity metrics
            basic_ratio = fuzz.ratio(name, existing_clean)
            partial_ratio = fuzz.partial_ratio(name, existing_clean)
            token_sort_ratio = fuzz.token_sort_ratio(name, existing_clean)
            token_set_ratio = fuzz.token_set_ratio(name, existing_clean)
            
            # For numbered items, compare without numbers
            existing_without_number = numbered_pattern.sub(r'\1', existing_clean)
            if name_without_number != name or existing_without_number != existing_clean:
                number_ratio = fuzz.ratio(name_without_number, existing_without_number)
                basic_ratio = max(basic_ratio, number_ratio)
            
            # Weight ratios differently based on content type - higher weights to catch more duplicates
            if content_type == 'topic':
                final_ratio = max(
                    basic_ratio,
                    token_sort_ratio * 1.1,  # Increased weight
                    token_set_ratio * 1.0    # Increased weight
                )
            elif content_type == 'subtopic':
                final_ratio = max(
                    basic_ratio,
                    partial_ratio * 1.0,     # Increased weight
                    token_sort_ratio * 0.95, # Increased weight
                    token_set_ratio * 0.9    # Increased weight
                )
            else:  # details
                final_ratio = max(
                    basic_ratio * 0.95,
                    partial_ratio * 0.9,
                    token_sort_ratio * 0.85,
                    token_set_ratio * 0.8
                )
            
            # Increase ratio for shorter texts to catch more duplicates
            if len(name) < 30:
                final_ratio *= 1.1  # Boost ratio for short texts
            
            # Check against adjusted threshold
            if final_ratio > threshold:
                logger.debug(
                    f"Found similar {content_type}:\n"
                    f"New: '{name}'\n"
                    f"Existing: '{existing_clean}'\n"
                    f"Ratio: {final_ratio:.2f} (threshold: {threshold})"
                )
                return True
        
        return False

    async def check_similarity_llm(self, text1: str, text2: str, context1: str, context2: str) -> bool:
        """LLM-based similarity check between two text elements with stricter criteria."""
        prompt = f"""Compare these two text elements and determine if they express similar core information, making one redundant in the mindmap.

        Text 1 (from {context1}):
        "{text1}"

        Text 2 (from {context2}):
        "{text2}"

        A text is REDUNDANT if ANY of these apply:
        1. It conveys the same primary information or main point as the other text
        2. It covers the same concept from a similar angle or perspective
        3. The semantic meaning overlaps significantly with the other text
        4. A reader would find having both entries repetitive or confusing
        5. One could be safely removed without losing important information

        A text is DISTINCT ONLY if ALL of these apply:
        1. It focuses on a clearly different aspect or perspective
        2. It provides substantial unique information not present in the other
        3. It serves a fundamentally different purpose in context
        4. Both entries together provide significantly more value than either alone
        5. The conceptual overlap is minimal

        When in doubt, mark as REDUNDANT to create a cleaner, more focused mindmap.

        Respond with EXACTLY one of these:
        REDUNDANT (overlapping information about X)
        DISTINCT (different aspect: X)

        where X is a very brief explanation."""

        try:
            response = await self.llm_client._retry_generate_completion(
                prompt,
                max_tokens=50,
                request_id='similarity_check',
                task="checking_content_similarity"
            )
            
            # Consider anything not explicitly marked as DISTINCT to be REDUNDANT
            result = not response.strip().upper().startswith("DISTINCT")
            
            logger.info(
                f"\n{colored('🔍 Content comparison:', 'cyan')}\n"
                f"Text 1: {colored(text1[:100] + '...', 'yellow')}\n"
                f"Text 2: {colored(text2[:100] + '...', 'yellow')}\n"
                f"Result: {colored('REDUNDANT' if result else 'DISTINCT', 'green')}\n"
                f"LLM Response: {colored(response.strip(), 'white')}"
            )
            return result
        except Exception as e:
            logger.error(f"Error in LLM similarity check: {str(e)}")
            # Default to considering items similar if the check fails
            return True

    async def _process_content_batch(self, content_items: List[ContentItem]) -> Set[int]:
        """Process a batch of content items to identify redundant content with parallel processing.
        
        Args:
            content_items: List of ContentItem objects to process
            
        Returns:
            Set of indices identifying redundant items that should be removed
        """
        redundant_indices = set()
        comparison_tasks = []
        comparison_counter = 0
        
        # Create cache of preprocessed texts to avoid recomputing
        processed_texts = {}
        for idx, item in enumerate(content_items):
            # Normalize text for comparison
            text = re.sub(r'\s+', ' ', item.text.lower().strip())
            text = re.sub(r'[^\w\s]', '', text)
            processed_texts[idx] = text
        
        # Limit concurrent API calls
        semaphore = asyncio.Semaphore(10)  # Adjust based on API limits
        
        # Prepare all comparison tasks first
        for i in range(len(content_items)):
            item1 = content_items[i]
            text1 = processed_texts[i]
            
            for j in range(i + 1, len(content_items)):
                item2 = content_items[j]
                text2 = processed_texts[j]
                
                # Quick exact text match check - avoid API call
                if text1 == text2:
                    # Log this immediately since we're not using the API
                    comparison_counter += 1
                    logger.info(f"\nMaking comparison {comparison_counter}... (exact match found)")
                    
                    # Add to candidates for removal with perfect confidence
                    confidence = 1.0
                    
                    # Determine which to keep based on importance and path
                    item1_importance = self._get_importance_value(item1.importance)
                    item2_importance = self._get_importance_value(item2.importance)
                    
                    if ((item2_importance > item1_importance) or
                        (item2_importance == item1_importance and 
                        len(item2.path) < len(item1.path))):
                        redundant_indices.add(i)
                        logger.info(
                            f"\n{colored('🔄 Removing redundant content:', 'yellow')}\n"
                            f"Keeping: {colored(item2.text[:100] + '...', 'green')}\n"
                            f"Removing: {colored(item1.text[:100] + '...', 'red')}\n"
                            f"Confidence: {colored(f'{confidence:.2f}', 'cyan')}"
                        )
                        break  # Stop processing this item if we're removing it
                    else:
                        redundant_indices.add(j)
                        logger.info(
                            f"\n{colored('🔄 Removing redundant content:', 'yellow')}\n"
                            f"Keeping: {colored(item1.text[:100] + '...', 'green')}\n"
                            f"Removing: {colored(item2.text[:100] + '...', 'red')}\n"
                            f"Confidence: {colored(f'{confidence:.2f}', 'cyan')}"
                        )
                    continue
                
                # Skip if lengths are very different
                len_ratio = min(len(text1), len(text2)) / max(len(text1), len(text2))
                if len_ratio < 0.5:  # Texts differ in length by more than 50%
                    continue
                
                # Skip if one item is already marked for removal
                if i in redundant_indices or j in redundant_indices:
                    continue
                    
                # Add to parallel comparison tasks
                async def check_similarity_with_context(idx1, idx2):
                    """Run similarity check with semaphore and return context for logging"""
                    nonlocal comparison_counter
                    
                    # Atomically increment comparison counter
                    comparison_id = comparison_counter = comparison_counter + 1
                    
                    # Log start of comparison
                    logger.info(f"\nMaking comparison {comparison_id}...")
                    
                    # Run the LLM comparison with rate limiting
                    async with semaphore:
                        try:
                            is_redundant = await self.check_similarity_llm(
                                content_items[idx1].text, 
                                content_items[idx2].text,
                                content_items[idx1].path_str, 
                                content_items[idx2].path_str
                            )
                            
                            # Calculate confidence if redundant
                            confidence = 0.0
                            if is_redundant:
                                # Calculate fuzzy string similarity metrics
                                fuzz_ratio = fuzz.ratio(processed_texts[idx1], processed_texts[idx2]) / 100.0
                                token_sort_ratio = fuzz.token_sort_ratio(processed_texts[idx1], processed_texts[idx2]) / 100.0
                                token_set_ratio = fuzz.token_set_ratio(processed_texts[idx1], processed_texts[idx2]) / 100.0
                                
                                # Combine metrics for overall confidence
                                confidence = (fuzz_ratio * 0.4 + 
                                            token_sort_ratio * 0.3 + 
                                            token_set_ratio * 0.3)
                            
                            return {
                                'comparison_id': comparison_id,
                                'is_redundant': is_redundant,
                                'confidence': confidence,
                                'idx1': idx1,
                                'idx2': idx2,
                                'success': True
                            }
                        except Exception as e:
                            logger.error(f"Error in comparison {comparison_id}: {str(e)}")
                            return {
                                'comparison_id': comparison_id,
                                'success': False,
                                'error': str(e),
                                'idx1': idx1,
                                'idx2': idx2
                            }
                
                # Add task to our list
                comparison_tasks.append(check_similarity_with_context(i, j))
        
        # Run all comparison tasks in parallel
        if comparison_tasks:
            logger.info(f"Starting {len(comparison_tasks)} parallel similarity comparisons")
            results = await asyncio.gather(*comparison_tasks)
            
            # Process results
            # First, collect all redundancies with confidence scores
            redundancy_candidates = []
            for result in results:
                if not result['success']:
                    continue
                    
                if result['is_redundant'] and result['confidence'] > 0.8:  # High confidence threshold
                    redundancy_candidates.append(result)
            
            # Sort by confidence (highest first)
            redundancy_candidates.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Process each redundancy candidate
            for result in redundancy_candidates:
                i, j = result['idx1'], result['idx2']
                
                # Skip if either item is already marked for removal
                if i in redundant_indices or j in redundant_indices:
                    continue
                    
                # Determine which to keep based on importance and path
                item1 = content_items[i]
                item2 = content_items[j]
                item1_importance = self._get_importance_value(item1.importance)
                item2_importance = self._get_importance_value(item2.importance)
                
                if ((item2_importance > item1_importance) or
                    (item2_importance == item1_importance and 
                    len(item2.path) < len(item1.path))):
                    redundant_indices.add(i)
                    logger.info(
                        f"\n{colored('🔄 Removing redundant content:', 'yellow')}\n"
                        f"Keeping: {colored(item2.text[:100] + '...', 'green')}\n"
                        f"Removing: {colored(item1.text[:100] + '...', 'red')}\n"
                        f"Confidence: {colored(f'{result["confidence"]:.2f}', 'cyan')}"
                    )
                else:
                    redundant_indices.add(j)
                    logger.info(
                        f"\n{colored('🔄 Removing redundant content:', 'yellow')}\n"
                        f"Keeping: {colored(item1.text[:100] + '...', 'green')}\n"
                        f"Removing: {colored(item2.text[:100] + '...', 'red')}\n"
                        f"Confidence: {colored(f'{result["confidence"]:.2f}', 'cyan')}"
                    )
        
        logger.info(f"\nBatch processing complete. Made {comparison_counter} comparisons.")
        return redundant_indices                

    def _get_importance_value(self, importance: str) -> int:
        """Convert importance string to numeric value for comparison."""
        return {'high': 3, 'medium': 2, 'low': 1}.get(importance.lower(), 0)

    def _extract_content_for_filtering(self, node: Dict[str, Any], current_path: List[str]) -> None:
        """Extract all content items with their full paths for filtering."""
        if not node:
            return

        # Process current node (including root node)
        if 'name' in node:
            current_node_path = current_path + ([node['name']] if node['name'] else [])
            
            # Add the node itself unless it's the root "Document Mindmap" node
            if len(current_path) > 0 or (node['name'] and node['name'] != 'Document Mindmap'):
                # Determine node type based on path depth
                node_type = 'root' if len(current_path) == 0 else 'topic' if len(current_path) == 1 else 'subtopic'
                
                content_item = ContentItem(
                    text=node['name'],
                    path=current_node_path,
                    node_type=node_type,
                    importance=node.get('importance', 'medium')
                )
                
                # Only add if path is non-empty
                if current_node_path:
                    path_tuple = tuple(current_node_path)
                    self.all_content.append(content_item)
                    self.content_by_path[path_tuple] = content_item

            # Process details at current level
            for detail in node.get('details', []):
                if isinstance(detail, dict) and 'text' in detail:
                    # Only add details if we have a valid parent path
                    if current_node_path:
                        detail_path = current_node_path + ['detail']
                        detail_item = ContentItem(
                            text=detail['text'],
                            path=detail_path,
                            node_type='detail',
                            importance=detail.get('importance', 'medium')
                        )
                        detail_path_tuple = tuple(detail_path)
                        self.all_content.append(detail_item)
                        self.content_by_path[detail_path_tuple] = detail_item

            # Process subtopics
            for subtopic in node.get('subtopics', []):
                self._extract_content_for_filtering(subtopic, current_node_path)
        else:
            # If no name but has subtopics, process them with current path
            for subtopic in node.get('subtopics', []):
                self._extract_content_for_filtering(subtopic, current_path)

    async def final_pass_filter_for_duplicative_content(self, mindmap_data: Dict[str, Any], batch_size: int = 50) -> Dict[str, Any]:
        """Enhanced filter for duplicative content with more aggressive detection and safer rebuilding."""
        USE_VERBOSE = True  # Toggle for verbose logging
        
        def vlog(message: str, color: str = 'white', bold: bool = False):
            """Helper for verbose logging"""
            if USE_VERBOSE:
                attrs = ['bold'] if bold else []
                logger.info(colored(message, color, attrs=attrs))
                
        vlog("\n" + "="*80, 'cyan', True)
        vlog("🔍 STARTING ENHANCED DUPLICATE CONTENT FILTER PASS", 'cyan', True)
        vlog("="*80 + "\n", 'cyan', True)
        
        # Debug input structure
        vlog("\n📥 INPUT MINDMAP STRUCTURE:", 'blue', True)
        vlog(f"Mindmap keys: {list(mindmap_data.keys())}")
        if 'central_theme' in mindmap_data:
            central_theme = mindmap_data['central_theme']
            vlog(f"Central theme keys: {list(central_theme.keys())}")
            vlog(f"Number of initial topics: {len(central_theme.get('subtopics', []))}")
            topics = central_theme.get('subtopics', [])
            vlog("\nInitial topic names:")
            for i, topic in enumerate(topics, 1):
                vlog(f"{i}. {topic.get('name', 'UNNAMED')} ({len(topic.get('subtopics', []))} subtopics)")
        else:
            vlog("WARNING: No 'central_theme' found in mindmap!", 'red', True)
            return mindmap_data  # Return original if no central theme
        
        # Initialize instance variables for content tracking
        vlog("\n🔄 Initializing content tracking...", 'yellow')
        self.all_content = []
        self.content_by_path = {}
        
        # Extract all content items for filtering
        vlog("\n📋 Starting content extraction from central theme...", 'blue', True)
        try:
            # Fixed extraction method - should properly extract all content
            self._extract_content_for_filtering(mindmap_data.get('central_theme', {}), [])
            
            # Verify extraction worked
            vlog(f"✅ Successfully extracted {len(self.all_content)} total content items:", 'green')
            content_types = {}
            for item in self.all_content:
                content_types[item.node_type] = content_types.get(item.node_type, 0) + 1
            for node_type, count in content_types.items():
                vlog(f"  - {node_type}: {count} items", 'green')
        except Exception as e:
            vlog(f"❌ Error during content extraction: {str(e)}", 'red', True)
            return mindmap_data  # Return original data on error
        
        # Check if we have any content to filter
        initial_count = len(self.all_content)
        if initial_count == 0:
            vlog("❌ No content extracted - mindmap appears empty", 'red', True)
            return mindmap_data  # Return original data
        
        # Process content in batches for memory efficiency
        vlog("\n🔄 Processing content in batches...", 'yellow', True)
        content_batches = [
            self.all_content[i:i+batch_size] 
            for i in range(0, len(self.all_content), batch_size)
        ]
        
        all_to_remove = set()
        
        for batch_idx, batch in enumerate(content_batches):
            vlog(f"Processing batch {batch_idx+1}/{len(content_batches)} ({len(batch)} items)...", 'yellow')
            batch_to_remove = await self._process_content_batch(batch)
            
            # Adjust indices to global positions
            global_indices = {batch_idx * batch_size + i for i in batch_to_remove}
            all_to_remove.update(global_indices)
            
            vlog(f"Batch {batch_idx+1} complete: identified {len(batch_to_remove)} redundant items", 'green')
        
        # Get indices of items to keep
        keep_indices = set(range(len(self.all_content))) - all_to_remove
        
        # Convert to set of paths to keep
        vlog("\n🔄 Converting to paths for rebuild...", 'blue')
        keep_paths = {tuple(self.all_content[i].path) for i in keep_indices}
        vlog(f"Keeping {len(keep_paths)} unique paths", 'blue')
        
        # Safety check - add at least one path if none remain
        if not keep_paths and len(self.all_content) > 0:
            vlog("⚠️ No paths remained after filtering! Adding at least one path", 'yellow', True)
            first_item = self.all_content[0]
            keep_paths.add(tuple(first_item.path))
        
        # Rebuild the mindmap with only the paths to keep
        vlog("\n🏗️ Rebuilding mindmap...", 'yellow', True)
        
        def rebuild_mindmap(node: Dict[str, Any], current_path: List[str]) -> Optional[Dict[str, Any]]:
            """Recursively rebuild mindmap keeping only non-redundant content."""
            # Add special case for root node
            if not node:
                return None
                
            # For root node, always keep it and process its subtopics
            if not current_path:
                result = copy.deepcopy(node)
                result['subtopics'] = []
                
                # Process main topics
                for topic in node.get('subtopics', []):
                    if topic.get('name'):
                        topic_path = [topic['name']]
                        rebuilt_topic = rebuild_mindmap(topic, topic_path)
                        if rebuilt_topic:
                            result['subtopics'].append(rebuilt_topic)
                
                # Always return root node even if no subtopics remain
                return result
                    
            # For non-root nodes, check if current path should be kept
            path_tuple = tuple(current_path)
            if path_tuple not in keep_paths:
                return None
                
            result = copy.deepcopy(node)
            result['subtopics'] = []
            
            # Process subtopics
            for subtopic in node.get('subtopics', []):
                if subtopic.get('name'):
                    subtopic_path = current_path + [subtopic['name']]
                    rebuilt_subtopic = rebuild_mindmap(subtopic, subtopic_path)
                    if rebuilt_subtopic:
                        result['subtopics'].append(rebuilt_subtopic)
            
            # Filter details
            if 'details' in result:
                filtered_details = []
                for detail in result['details']:
                    if isinstance(detail, dict) and 'text' in detail:
                        detail_path = current_path + ['detail']
                        if tuple(detail_path) in keep_paths:
                            filtered_details.append(detail)
                result['details'] = filtered_details
            
            # Only return node if it has content
            if result['subtopics'] or result.get('details'):
                return result
            return None
        
        # Rebuild mindmap without redundant content
        filtered_data = rebuild_mindmap(mindmap_data.get('central_theme', {}), [])
        
        # Safety check - add the original data's central theme if rebuild failed completely
        if not filtered_data:
            vlog("❌ Filtering removed all content - using original mindmap", 'red', True)
            return mindmap_data
            
        # Another safety check - ensure we have subtopics
        if not filtered_data.get('subtopics'):
            vlog("❌ Filtering removed all subtopics - using original mindmap", 'red', True) 
            return mindmap_data
        
        # Put the central theme back into a complete mindmap structure
        result_mindmap = {'central_theme': filtered_data}
        
        # Calculate and log statistics
        removed_count = initial_count - len(keep_indices)
        reduction_percentage = (removed_count / initial_count * 100) if initial_count > 0 else 0
        
        vlog(
            f"\n{colored('✅ Duplicate content filtering complete', 'green', attrs=['bold'])}\n"
            f"Original items: {colored(str(initial_count), 'yellow')}\n"
            f"Filtered items: {colored(str(len(keep_indices)), 'yellow')}\n"
            f"Removed {colored(str(removed_count), 'red')} duplicate items "
            f"({colored(f'{reduction_percentage:.1f}%', 'red')} reduction)"
        )
        
        return result_mindmap

    async def generate_mindmap(self, document_content: str, request_id: str) -> str:
        """Generate a complete mindmap from document content with balanced coverage of all topics.
        
        Args:
            document_content (str): The document content to analyze
            request_id (str): Unique identifier for request tracking
            
        Returns:
            str: Complete Mermaid mindmap syntax
            
        Raises:
            MindMapGenerationError: If mindmap generation fails
        """
        try:
            logger.info("Starting mindmap generation process...", extra={"request_id": request_id})
            
            # Initialize content caching and LLM call tracking
            self._content_cache = {}
            self._llm_calls = {
                'topics': 0,
                'subtopics': 0,
                'details': 0
            }
            
            # Initialize tracking of unique concepts
            self._unique_concepts = {
                'topics': set(),
                'subtopics': set(),
                'details': set()
            }
            
            # Enhanced completion tracking
            completion_status = {
                'total_topics': 0,
                'processed_topics': 0,
                'total_subtopics': 0,
                'processed_subtopics': 0,
                'total_details': 0
            }
            
            # Set strict LLM call limits with increased bounds
            max_llm_calls = {
                'topics': 20,      # Increased from 15
                'subtopics': 30,   # Increased from 20
                'details': 40      # Increased from 24
            }

            # Set minimum content requirements with better distribution
            min_requirements = {
                'topics': 4,       # Minimum topics to process
                'subtopics_per_topic': 2,  # Minimum subtopics per topic
                'details_per_subtopic': 3   # Minimum details per subtopic
            }
            
            # Calculate document word count and set limit 
            doc_words = len(document_content.split())
            word_limit = min(doc_words * 0.9, 8000)  # Cap at 8000 words
            current_word_count = 0
            
            logger.info(f"Document size: {doc_words} words. Generation limit: {word_limit:,} words", extra={"request_id": request_id})

            # Helper function to check if we have enough content with stricter enforcement
            def has_sufficient_content():
                if completion_status['processed_topics'] < min_requirements['topics']:
                    return False
                if completion_status['total_topics'] > 0:
                    avg_subtopics_per_topic = (completion_status['processed_subtopics'] / 
                                            completion_status['processed_topics'])
                    if avg_subtopics_per_topic < min_requirements['subtopics_per_topic']:
                        return False
                # Process at least 75% of available topics before considering early stop
                if completion_status['total_topics'] > 0:
                    topics_processed_ratio = completion_status['processed_topics'] / completion_status['total_topics']
                    if topics_processed_ratio < 0.75:
                        return False
                return True
                                        
            # Check cache first for document type with strict caching
            doc_type_key = hashlib.md5(document_content[:1000].encode()).hexdigest()
            if doc_type_key in self._content_cache:
                doc_type = self._content_cache[doc_type_key]
            else:
                doc_type = await self.prompt_strategy.detect_document_type(document_content, request_id, self.llm_client)
                self._content_cache[doc_type_key] = doc_type
                self._llm_calls['topics'] += 1

            logger.info(f"Detected document type: {doc_type.name}", extra={"request_id": request_id})
            
            type_prompts = self.type_specific_prompts[doc_type]
            
            # Extract main topics with enhanced LLM call limit and uniqueness check
            if self._llm_calls['topics'] < max_llm_calls['topics']:
                logger.info("Extracting main topics...", extra={"request_id": request_id})
                main_topics = await self._extract_main_topics(document_content, type_prompts['topics'], request_id)
                self._llm_calls['topics'] += 1
                
                # NEW: Perform early redundancy check on main topics
                main_topics = await self._batch_redundancy_check(main_topics, 'topic')
                
                completion_status['total_topics'] = len(main_topics)
            else:
                logger.info("Using cached main topics to avoid excessive LLM calls")
                main_topics = self._content_cache.get('main_topics', [])
                completion_status['total_topics'] = len(main_topics)
            
            if not main_topics:
                raise MindMapGenerationError("No main topics could be extracted from the document")
                
            # Cache main topics with timestamp
            self._content_cache['main_topics'] = {
                'data': main_topics,
                'timestamp': time.time()
            }

            # Process topics with completion tracking
            processed_topics = {}
            # NEW: Track already processed topics for redundancy checking
            processed_topic_names = {}
            
            for topic_idx, topic in enumerate(main_topics, 1):
                # Don't stop early if we haven't processed minimum topics
                should_continue = (topic_idx <= min_requirements['topics'] or 
                                not has_sufficient_content() or
                                completion_status['processed_topics'] < len(main_topics) * 0.75)
                                
                if not should_continue:
                    logger.info(f"Stopping after processing {topic_idx} topics - sufficient content gathered")
                    break
        
                topic_name = topic['name']
                
                # NEW: Check if this topic is redundant with already processed topics
                is_redundant = False
                for processed_name in processed_topic_names:
                    if await self.is_similar_to_existing(topic_name, {processed_name: True}, 'topic'):
                        logger.info(f"Skipping redundant topic: '{topic_name}' (similar to '{processed_name}')")
                        is_redundant = True
                        break
                        
                if is_redundant:
                    continue
                    
                # Track this topic for future redundancy checks
                processed_topic_names[topic_name] = True
                
                # Enhanced word limit check with buffer
                if current_word_count > word_limit * 0.95:  # Increased from 0.9 to ensure more completion
                    logger.info(f"Approaching word limit at {current_word_count}/{word_limit:.0f} words")
                    break

                logger.info(f"Processing topic {topic_idx}/{len(main_topics)}: '{topic_name}' "
                        f"(Words: {current_word_count}/{word_limit:.0f})",
                        extra={"request_id": request_id})
                
                # Track unique concepts with validation
                if topic_name not in self._unique_concepts['topics']:
                    self._unique_concepts['topics'].add(topic_name)
                    completion_status['processed_topics'] += 1

                try:
                    # Enhanced subtopic processing with caching
                    topic_key = hashlib.md5(f"{topic_name}:{doc_type_key}".encode()).hexdigest()
                    if topic_key in self._content_cache:
                        subtopics = self._content_cache[topic_key]
                        logger.info(f"Using cached subtopics for topic: {topic_name}")
                    else:
                        if self._llm_calls['subtopics'] < max_llm_calls['subtopics']:
                            subtopics = await self._extract_subtopics(
                                topic, document_content, type_prompts['subtopics'], request_id
                            )
                            
                            # NEW: Perform early redundancy check on subtopics
                            subtopics = await self._batch_redundancy_check(
                                subtopics, 'subtopic', context_prefix=topic_name
                            )
                            
                            self._content_cache[topic_key] = subtopics
                            self._llm_calls['subtopics'] += 1
                        else:
                            logger.info("Reached subtopic LLM call limit")
                            break
                            
                    topic['subtopics'] = []
                    
                    if subtopics:
                        completion_status['total_subtopics'] += len(subtopics)
                        processed_subtopics = {}
                        
                        # NEW: Track already processed subtopics for redundancy checking
                        processed_subtopic_names = {}
                        
                        # Process each subtopic with completion tracking
                        for subtopic_idx, subtopic in enumerate(subtopics, 1):
                            if self._llm_calls['details'] >= max_llm_calls['details']:
                                logger.info("Reached maximum LLM calls for detail extraction")
                                break
                                
                            subtopic_name = subtopic['name']
                            
                            # NEW: Check redundancy with already processed subtopics
                            is_redundant = False
                            for processed_name in processed_subtopic_names:
                                if await self.is_similar_to_existing(subtopic_name, {processed_name: True}, 'subtopic'):
                                    logger.info(f"Skipping redundant subtopic: '{subtopic_name}' (similar to '{processed_name}')")
                                    is_redundant = True
                                    break
                                    
                            if is_redundant:
                                continue
                                
                            # Track this subtopic for future redundancy checks
                            processed_subtopic_names[subtopic_name] = True
                            
                            # Track word count for subtopics
                            subtopic_words = len(subtopic_name.split())
                            if current_word_count + subtopic_words > word_limit * 0.95:
                                logger.info("Approaching word limit during subtopic processing")
                                break
                                
                            current_word_count += subtopic_words
                            
                            # Track unique subtopics
                            self._unique_concepts['subtopics'].add(subtopic_name)
                            completion_status['processed_subtopics'] += 1

                            try:
                                # Enhanced detail processing with caching
                                subtopic_key = hashlib.md5(f"{subtopic_name}:{topic_key}".encode()).hexdigest()
                                if subtopic_key in self._content_cache:
                                    details = self._content_cache[subtopic_key]
                                    logger.info(f"Using cached details for subtopic: {subtopic_name}")
                                else:
                                    if self._llm_calls['details'] < max_llm_calls['details']:
                                        details = await self._extract_details(
                                            subtopic, document_content, type_prompts['details'], request_id
                                        )
                                        self._content_cache[subtopic_key] = details
                                        self._llm_calls['details'] += 1
                                    else:
                                        details = []
                                
                                subtopic['details'] = []
                                
                                if details:
                                    completion_status['total_details'] += len(details)
                                    
                                    # Process details with completion tracking
                                    seen_details = {}
                                    unique_details = []
                                    
                                    for detail in details:
                                        detail_words = len(detail['text'].split())
                                        
                                        if current_word_count + detail_words > word_limit * 0.98:
                                            logger.info("Approaching word limit during detail processing")
                                            break
                                            
                                        if not await self.is_similar_to_existing(detail['text'], seen_details, 'detail'):
                                            current_word_count += detail_words
                                            seen_details[detail['text']] = True
                                            unique_details.append(detail)
                                            self._unique_concepts['details'].add(detail['text'])
                                    
                                    subtopic['details'] = unique_details
                                
                                processed_subtopics[subtopic_name] = subtopic
                                
                            except Exception as e:
                                logger.error(f"Error processing details for subtopic '{subtopic_name}': {str(e)}")
                                processed_subtopics[subtopic_name] = subtopic
                                continue
                        
                        topic['subtopics'] = list(processed_subtopics.values())
                    
                    processed_topics[topic_name] = topic
                        
                except Exception as e:
                    logger.error(f"Error processing topic '{topic_name}': {str(e)}")
                    processed_topics[topic_name] = topic
                    continue
                
                # Log completion status
                logger.info(
                    f"Completion status: "
                    f"Topics: {completion_status['processed_topics']}/{completion_status['total_topics']}, "
                    f"Subtopics: {completion_status['processed_subtopics']}/{completion_status['total_subtopics']}, "
                    f"Details: {completion_status['total_details']}"
                )
            
            if not processed_topics:
                raise MindMapGenerationError("No topics could be processed")
            
            # Enhanced final statistics logging
            completion_stats = {
                'words_generated': current_word_count,
                'word_limit': word_limit,
                'completion_percentage': (current_word_count/word_limit)*100,
                'topics_processed': completion_status['processed_topics'],
                'total_topics': completion_status['total_topics'],
                'unique_topics': len(self._unique_concepts['topics']),
                'unique_subtopics': len(self._unique_concepts['subtopics']),
                'unique_details': len(self._unique_concepts['details']),
                'llm_calls': self._llm_calls,
                'early_stopping': has_sufficient_content()
            }
            
            logger.info(
                f"Mindmap generation completed:"
                f"\n- Words generated: {completion_stats['words_generated']}/{completion_stats['word_limit']:.0f} "
                f"({completion_stats['completion_percentage']:.1f}%)"
                f"\n- Topics processed: {completion_stats['topics_processed']}/{completion_stats['total_topics']}"
                f"\n- Unique topics: {completion_stats['unique_topics']}"
                f"\n- Unique subtopics: {completion_stats['unique_subtopics']}"
                f"\n- Unique details: {completion_stats['unique_details']}"
                f"\n- LLM calls: topics={completion_stats['llm_calls']['topics']}, "
                f"subtopics={completion_stats['llm_calls']['subtopics']}, "
                f"details={completion_stats['llm_calls']['details']}"
                f"\n- Early stopping: {completion_stats['early_stopping']}",
                extra={"request_id": request_id}
            )
            
            logger.info("Starting initial mindmap generation...")
            concepts = {
                'central_theme': self._create_node('Document Mindmap', 'high')
            }
            concepts['central_theme']['subtopics'] = list(processed_topics.values())
                
            logger.info("Starting duplicate content filtering...")
            try:
                # Explicitly await the filtering
                filtered_concepts = await self.final_pass_filter_for_duplicative_content(
                    concepts,
                    batch_size=25
                )
                
                if not filtered_concepts:
                    logger.warning("Filtering removed all content, using original mindmap")
                    filtered_concepts = concepts
                    
                # NEW: Perform reality check against original document
                logger.info("Starting reality check to filter confabulations...")
                verified_concepts = await self.verify_mindmap_against_source(
                    filtered_concepts, 
                    document_content
                )
                
                if not verified_concepts or not verified_concepts.get('central_theme', {}).get('subtopics'):
                    logger.warning("Reality check removed all content, using filtered mindmap with warning")
                    verified_concepts = filtered_concepts
                
                # Print enhanced usage report with detailed breakdowns
                self.optimizer.token_tracker.print_usage_report()

                try:
                    self._save_emoji_cache()  # Save cache at the end of processing
                except Exception as e:
                    logger.warning(f"Failed to save emoji cache: {str(e)}")
                                    
                logger.info("Successfully verified against source document, generating final mindmap...")
                return self._generate_mermaid_mindmap(verified_concepts)
                
            except Exception as e:
                logger.error(f"Error during content filtering or verification: {str(e)}")
                logger.warning("Using unfiltered mindmap due to filtering/verification error")
                
                # Print usage report even if verification fails
                self.optimizer.token_tracker.print_usage_report()
                
                return self._generate_mermaid_mindmap(concepts)

        except Exception as e:
            logger.error(f"Error in mindmap generation: {str(e)}", extra={"request_id": request_id})
            raise MindMapGenerationError(f"Failed to generate mindmap: {str(e)}")

    async def _extract_main_topics(self, content: str, topics_prompt: str, request_id: str) -> List[Dict[str, Any]]:
        """Extract main topics using LLM with more aggressive deduplication and content preservation.
        
        Args:
            content (str): The document content to analyze
            topics_prompt (str): The prompt template for topic extraction
            request_id (str): Unique identifier for the request
            
        Returns:
            List[Dict[str, Any]]: List of extracted topics with their metadata
            
        Raises:
            MindMapGenerationError: If topic extraction fails
        """
        MAX_TOPICS = 8  # Increased from 6 to ensure complete coverage
        MIN_TOPICS = 4  # Minimum topics to process
        MAX_CONCURRENT_TASKS = 50  # Limit concurrent LLM calls
        
        async def extract_from_chunk(chunk: str) -> List[Dict[str, Any]]:
            """Extract topics from a single content chunk."""
            consolidated_prompt = f"""You are an expert at identifying unique, distinct main topics within content.
                        
            {topics_prompt}

            Additional requirements:
            1. Each topic must be truly distinct from others - avoid overlapping concepts
            2. Combine similar themes into single, well-defined topics
            3. Ensure topics are specific enough to be meaningful but general enough to support subtopics
            4. Aim for 4-8 most significant topics that capture the key distinct areas
            5. Focus on conceptual separation - each topic should represent a unique aspect or dimension
            6. Avoid topics that are too similar or could be subtopics of each other
            7. Prioritize broader topics that can encompass multiple subtopics
            8. Eliminate redundancy - each topic should cover a distinct area with no overlap

            IMPORTANT: 
            1. DO NOT include specific statistics, percentages, or numerical data unless explicitly stated in the source text
            2. DO NOT refer to modern studies, surveys, or analyses that aren't mentioned in the document
            3. DO NOT make up correlation coefficients, growth rates, or other numerical relationships
            4. Keep your content strictly based on what's in the document, not general knowledge about the topic
            5. Use general descriptions rather than specific numbers if the document doesn't provide exact figures

            Current content chunk:
            {chunk}

            IMPORTANT: Respond with ONLY a JSON array of strings representing the main distinct topics.
            Example format: ["First Distinct Topic", "Second Distinct Topic"]"""

            try:
                response = await self.optimizer.generate_completion(
                    consolidated_prompt,
                    max_tokens=1000,
                    request_id=request_id,
                    task="extracting_main_topics"
                )
                
                logger.debug(f"Raw topics response for chunk: {response}", 
                            extra={"request_id": request_id})
                
                parsed_response = self.llm_client._parse_llm_response(response, "array")
                
                chunk_topics = []
                seen_names = set()
                
                for topic_name in parsed_response:
                    if isinstance(topic_name, str) and topic_name.strip():
                        cleaned_name = re.sub(r'[`*_#]', '', topic_name)
                        cleaned_name = ' '.join(cleaned_name.split())
                        
                        if cleaned_name and cleaned_name not in seen_names:
                            seen_names.add(cleaned_name)
                            # Select appropriate emoji for topic
                            emoji = await self._select_emoji(cleaned_name, 'topic')
                            chunk_topics.append({
                                'name': cleaned_name,
                                'emoji': emoji,
                                'processed': False,  # Track processing status
                                'importance': 'high',  # Main topics are always high importance
                                'subtopics': [],
                                'details': []
                            })
                
                return chunk_topics
                
            except Exception as e:
                logger.error(f"Error extracting topics from chunk: {str(e)}", 
                            extra={"request_id": request_id})
                return []

        try:
            # Create content chunks with overlap to ensure context preservation
            chunk_size = min(8000, len(content) // 3) if len(content) > 6000 else 4000
            overlap = 250  # Characters of overlap between chunks
            
            # Create overlapping chunks
            content_chunks = []
            start = 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                # Extend to nearest sentence end if possible
                if end < len(content):
                    next_period = content.find('.', end)
                    if next_period != -1 and next_period - end < 200:  # Don't extend too far
                        end = next_period + 1
                chunk = content[start:end]
                content_chunks.append(chunk)
                start = end - overlap if end < len(content) else end

            # Initialize concurrent processing controls
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            topics_with_metrics = {}  # Track topic frequency and importance
            unique_topics_seen = set()
            max_chunks_to_process = 5  # Increased from 3

            async def process_chunk(chunk: str, chunk_idx: int) -> List[Dict[str, Any]]:
                """Process a single chunk with semaphore control."""
                if chunk_idx >= max_chunks_to_process:
                    return []
                    
                if len(unique_topics_seen) >= MAX_TOPICS * 1.5:
                    return []
                    
                async with semaphore:
                    return await self.llm_client._retry_with_exponential_backoff(
                        lambda: extract_from_chunk(chunk)
                    )

            # Process chunks concurrently
            chunk_results = await asyncio.gather(
                *(process_chunk(chunk, idx) for idx, chunk in enumerate(content_chunks))
            )

            # Process results with more aggressive deduplication
            all_topics = []
            for chunk_topics in chunk_results:
                # Track topic frequency and merge similar topics
                for topic in chunk_topics:
                    topic_key = topic['name'].lower()
                    
                    # Check for similar existing topics with stricter criteria
                    similar_found = False
                    for existing_key in list(topics_with_metrics.keys()):
                        if await self.is_similar_to_existing(topic_key, {existing_key: True}, 'topic'):
                            topics_with_metrics[existing_key]['frequency'] += 1
                            similar_found = True
                            break
                    
                    if not similar_found:
                        topics_with_metrics[topic_key] = {
                            'topic': topic,
                            'frequency': 1,
                            'first_appearance': len(all_topics)
                        }
                
                # Only add unique topics
                for topic in chunk_topics:
                    if topic['name'] not in unique_topics_seen:
                        unique_topics_seen.add(topic['name'])
                        all_topics.append(topic)
                        
                        if len(unique_topics_seen) >= MAX_TOPICS * 1.5:
                            break

                # Early stopping checks
                if len(unique_topics_seen) >= MIN_TOPICS:
                    topic_frequencies = [metrics['frequency'] for metrics in topics_with_metrics.values()]
                    if len(topic_frequencies) >= MIN_TOPICS:
                        avg_frequency = sum(topic_frequencies) / len(topic_frequencies)
                        if avg_frequency >= 1.5:  # Topics appear in multiple chunks
                            break

            if not all_topics:
                error_msg = "No valid topics extracted from document"
                logger.error(error_msg, extra={"request_id": request_id})
                raise MindMapGenerationError(error_msg)

            # Add consolidation step when we have too many potential topics
            if len(all_topics) > MIN_TOPICS * 1.5:
                consolidation_prompt = f"""You are merging and consolidating similar topics from a document.

                Here are the current potential topics extracted:
                {json.dumps([topic['name'] for topic in all_topics], indent=2)}

                Requirements:
                1. Identify topics that cover the same or similar concepts
                2. Merge overlapping topics into a single, well-defined topic
                3. Choose the most representative, precise, and concise name for each topic
                4. Ensure each final topic is clearly distinct from others
                5. Aim for exactly {MIN_TOPICS}-{MAX_TOPICS} distinct topics that cover the key areas
                6. Completely eliminate redundancy - each topic should represent a unique conceptual area
                7. Broader topics are preferred over narrower ones if they can encompass the same content
                8. Choose clear, concise topic names that accurately represent the content

                Return ONLY a JSON array of consolidated topic names.
                Example: ["First Consolidated Topic", "Second Consolidated Topic"]"""

                try:
                    response = await self.llm_client._retry_generate_completion(
                        consolidation_prompt,
                        max_tokens=1000,
                        request_id=request_id,
                        task="consolidating_topics"
                    )
                    
                    consolidated_names = self.llm_client._parse_llm_response(response, "array")
                    
                    if consolidated_names and len(consolidated_names) >= MIN_TOPICS:
                        # Create new topics from consolidated names
                        consolidated_topics = []
                        seen_names = set()
                        
                        for name in consolidated_names:
                            if isinstance(name, str) and name.strip():
                                cleaned_name = re.sub(r'[`*_#]', '', name)
                                cleaned_name = ' '.join(cleaned_name.split())
                                
                                if cleaned_name and cleaned_name not in seen_names:
                                    emoji = await self._select_emoji(cleaned_name, 'topic')
                                    consolidated_topics.append({
                                        'name': cleaned_name,
                                        'emoji': emoji,
                                        'processed': False,
                                        'importance': 'high',
                                        'subtopics': [],
                                        'details': []
                                    })
                                    seen_names.add(cleaned_name)
                        
                        if len(consolidated_topics) >= MIN_TOPICS:
                            all_topics = consolidated_topics
                            logger.info(f"Successfully consolidated topics from {len(unique_topics_seen)} to {len(consolidated_topics)}")
                except Exception as e:
                    logger.warning(f"Topic consolidation failed: {str(e)}", extra={"request_id": request_id})

            # Sort and select final topics with stricter deduplication
            sorted_topics = sorted(
                topics_with_metrics.values(),
                key=lambda x: (-x['frequency'], x['first_appearance'])
            )

            final_topics = []
            seen_final = set()
            
            # Select final topics with more aggressive deduplication
            for topic_data in sorted_topics:
                topic = topic_data['topic']
                if len(final_topics) >= MAX_TOPICS:
                    break
                    
                if topic['name'] not in seen_final:
                    similar_exists = False
                    for existing_topic in final_topics:
                        if await self.is_similar_to_existing(topic['name'], {existing_topic['name']: True}, 'topic'):
                            similar_exists = True
                            break
                    
                    if not similar_exists:
                        seen_final.add(topic['name'])
                        final_topics.append(topic)

            # Add additional topics if needed 
            if len(final_topics) < MIN_TOPICS:
                for topic in all_topics:
                    if len(final_topics) >= MIN_TOPICS:
                        break
                        
                    if topic['name'] not in seen_final:
                        similar_exists = False
                        for existing_topic in final_topics:
                            if await self.is_similar_to_existing(topic['name'], {existing_topic['name']: True}, 'topic'):
                                similar_exists = True
                                break
                        
                        if not similar_exists:
                            seen_final.add(topic['name'])
                            final_topics.append(topic)

            # Final LLM-based deduplication when we have enough topics
            if len(final_topics) > MIN_TOPICS:
                for i in range(len(final_topics)-1, 0, -1):
                    if len(final_topics) <= MIN_TOPICS:
                        break
                        
                    for j in range(i-1, -1, -1):
                        try:
                            is_duplicate = await self.check_similarity_llm(
                                final_topics[i]['name'], 
                                final_topics[j]['name'],
                                "main topic", 
                                "main topic"
                            )
                            
                            if is_duplicate and len(final_topics) > MIN_TOPICS:
                                logger.info(f"LLM detected duplicate topics: '{final_topics[i]['name']}' and '{final_topics[j]['name']}'")
                                del final_topics[i]
                                break
                        except Exception as e:
                            logger.warning(f"LLM duplicate check failed: {str(e)}")
                            continue

            logger.info(
                f"Successfully extracted {len(final_topics)} main topics "
                f"(min: {MIN_TOPICS}, max: {MAX_TOPICS})",
                extra={"request_id": request_id}
            )

            return final_topics

        except Exception as e:
            error_msg = f"Failed to extract main topics: {str(e)}"
            logger.error(error_msg, extra={"request_id": request_id})
            raise MindMapGenerationError(error_msg)

    async def _extract_subtopics(self, topic: Dict[str, Any], content: str, subtopics_prompt_template: str, request_id: str) -> List[Dict[str, Any]]:
        """Extract subtopics using LLM with more aggressive deduplication and content preservation."""
        MAX_SUBTOPICS = self.config['max_subtopics']
        MAX_CONCURRENT_TASKS = 50  # Limit concurrent LLM calls
        
        content_hash = hashlib.md5(content.encode()).hexdigest()
        cache_key = f"subtopics_{topic['name']}_{content_hash}_{request_id}"
        
        if not hasattr(self, '_subtopics_cache'):
            self._subtopics_cache = {}
            
        if not hasattr(self, '_processed_chunks_by_topic'):
            self._processed_chunks_by_topic = {}
        
        if topic['name'] not in self._processed_chunks_by_topic:
            self._processed_chunks_by_topic[topic['name']] = set()

        async def extract_from_chunk(chunk: str) -> List[Dict[str, Any]]:
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_hash in self._processed_chunks_by_topic[topic['name']]:
                return []
                
            self._processed_chunks_by_topic[topic['name']].add(chunk_hash)
                
            enhanced_prompt = f"""You are an expert at identifying distinct, relevant subtopics that support a main topic.

            Topic: {topic['name']}

            {subtopics_prompt_template.format(topic=topic['name'])}

            Additional requirements:
            1. Each subtopic must provide unique value and perspective with NO conceptual overlap
            2. Include both high-level and specific subtopics that are clearly distinct
            3. Ensure strong connection to main topic without repeating the topic itself
            4. Focus on distinct aspects or dimensions that don't overlap with each other
            5. Include 4-6 important subtopics that cover different facets of the topic
            6. Balance breadth and depth of coverage with zero redundancy
            7. Choose clear, concise subtopic names that accurately represent the content
            8. Eliminate subtopics that could be merged without significant information loss

            IMPORTANT: 
            1. DO NOT include specific statistics, percentages, or numerical data unless explicitly stated in the source text
            2. DO NOT refer to modern studies, surveys, or analyses that aren't mentioned in the document
            3. DO NOT make up correlation coefficients, growth rates, or other numerical relationships
            4. Keep your content strictly based on what's in the document, not general knowledge about the topic
            5. Use general descriptions rather than specific numbers if the document doesn't provide exact figures

            Content chunk:
            {chunk}

            IMPORTANT: Return ONLY a JSON array of strings representing distinct subtopics.
            Example: ["First Distinct Subtopic", "Second Distinct Subtopic"]"""

            try:
                response = await self.optimizer.generate_completion(
                    enhanced_prompt,
                    max_tokens=1000,
                    request_id=request_id,
                    task=f"extracting_subtopics_{topic['name']}"
                )
                
                logger.debug(f"Raw subtopics response for {topic['name']}: {response}", 
                            extra={"request_id": request_id})
                
                parsed_response = self.llm_client._parse_llm_response(response, "array")
                
                chunk_subtopics = []
                seen_names = {}
                
                for subtopic_name in parsed_response:
                    if isinstance(subtopic_name, str) and subtopic_name.strip():
                        cleaned_name = re.sub(r'[`*_#]', '', subtopic_name)
                        cleaned_name = ' '.join(cleaned_name.split())
                        
                        if cleaned_name and not await self.is_similar_to_existing(cleaned_name, seen_names, 'subtopic'):
                            emoji = await self._select_emoji(cleaned_name, 'subtopic')
                            node = self._create_node(
                                name=cleaned_name,
                                emoji=emoji
                            )
                            chunk_subtopics.append(node)
                            seen_names[cleaned_name] = node
                
                return chunk_subtopics
                
            except Exception as e:
                logger.error(f"Error extracting subtopics from chunk for {topic['name']}: {str(e)}", 
                            extra={"request_id": request_id})
                return []

        try:
            if cache_key in self._subtopics_cache:
                return self._subtopics_cache[cache_key]
                
            chunk_size = min(8000, len(content) // 3) if len(content) > 6000 else 4000
            content_chunks = [content[i:i + chunk_size] 
                            for i in range(0, len(content), chunk_size)]
            
            # Initialize concurrent processing controls
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            seen_names = {}
            all_subtopics = []
            
            async def process_chunk(chunk: str) -> List[Dict[str, Any]]:
                """Process a single chunk with semaphore control."""
                async with semaphore:
                    return await self.llm_client._retry_with_exponential_backoff(
                        lambda: extract_from_chunk(chunk)
                    )

            # Process chunks concurrently
            chunk_results = await asyncio.gather(
                *(process_chunk(chunk) for chunk in content_chunks)
            )

            # Process results with more aggressive deduplication
            for chunk_subtopics in chunk_results:
                for subtopic in chunk_subtopics:
                    if not await self.is_similar_to_existing(subtopic['name'], seen_names, 'subtopic'):
                        seen_names[subtopic['name']] = subtopic
                        all_subtopics.append(subtopic)

            if not all_subtopics:
                logger.warning(f"No subtopics found for topic {topic['name']}", 
                            extra={"request_id": request_id})
                return []

            # Always perform consolidation to reduce duplicative content
            consolidation_prompt = f"""You are consolidating subtopics for the main topic: {topic['name']}

            Current subtopics:
            {json.dumps([st['name'] for st in all_subtopics], indent=2)}

            Requirements:
            1. Aggressively merge subtopics that cover similar information or concepts
            2. Eliminate any conceptual redundancy between subtopics
            3. Choose the clearest and most representative name for each consolidated subtopic
            4. Each final subtopic must address a unique aspect of the main topic
            5. Select 3-5 truly distinct subtopics that together fully cover the topic
            6. Ensure zero information repetition between subtopics
            7. Prioritize broader subtopics that can encompass multiple narrower ones
            8. Choose clear, concise subtopic names that accurately represent the content

            Return ONLY a JSON array of consolidated subtopic names.
            Example: ["First Consolidated Subtopic", "Second Consolidated Subtopic"]"""

            try:
                consolidation_response = await self.llm_client._retry_generate_completion(
                    consolidation_prompt,
                    max_tokens=1000,
                    request_id=request_id,
                    task=f"consolidate_subtopics_{topic['name']}"
                )
                
                consolidated_names = self.llm_client._parse_llm_response(consolidation_response, "array")
                
                if consolidated_names:
                    seen_names = {}
                    consolidated_subtopics = []
                    
                    for name in consolidated_names:
                        if isinstance(name, str) and name.strip():
                            cleaned_name = re.sub(r'[`*_#]', '', name)
                            cleaned_name = ' '.join(cleaned_name.split())
                            
                            if cleaned_name and not await self.is_similar_to_existing(cleaned_name, seen_names, 'subtopic'):
                                emoji = await self._select_emoji(cleaned_name, 'subtopic')
                                node = self._create_node(
                                    name=cleaned_name,
                                    emoji=emoji
                                )
                                consolidated_subtopics.append(node)
                                seen_names[cleaned_name] = node
                    
                    if consolidated_subtopics:
                        all_subtopics = consolidated_subtopics
                        logger.info(f"Successfully consolidated subtopics for {topic['name']} from {len(all_subtopics)} to {len(consolidated_subtopics)}")
                        
            except Exception as e:
                logger.warning(f"Subtopic consolidation failed for {topic['name']}: {str(e)}", 
                            extra={"request_id": request_id})
                # If consolidation fails, do a simple deduplication pass
                seen = set()
                deduplicated_subtopics = []
                for subtopic in all_subtopics:
                    if subtopic['name'] not in seen:
                        seen.add(subtopic['name'])
                        deduplicated_subtopics.append(subtopic)
                all_subtopics = sorted(deduplicated_subtopics, 
                                    key=lambda x: len(x['name']), 
                                    reverse=True)[:MAX_SUBTOPICS]
            
            # Final LLM-based deduplication when we have enough subtopics
            if len(all_subtopics) > 3:  # Only if we have enough to potentially remove some
                for i in range(len(all_subtopics)-1, 0, -1):
                    if len(all_subtopics) <= 3:  # Ensure we keep at least 3 subtopics
                        break
                        
                    for j in range(i-1, -1, -1):
                        try:
                            is_duplicate = await self.check_similarity_llm(
                                all_subtopics[i]['name'], 
                                all_subtopics[j]['name'],
                                f"subtopic of {topic['name']}", 
                                f"subtopic of {topic['name']}"
                            )
                            
                            if is_duplicate:
                                logger.info(f"LLM detected duplicate subtopics: '{all_subtopics[i]['name']}' and '{all_subtopics[j]['name']}'")
                                del all_subtopics[i]
                                break
                        except Exception as e:
                            logger.warning(f"LLM duplicate check failed: {str(e)}")
                            continue
            
            final_subtopics = all_subtopics[:MAX_SUBTOPICS]
            self._subtopics_cache[cache_key] = final_subtopics
            
            logger.info(f"Successfully extracted {len(final_subtopics)} subtopics for {topic['name']}", 
                        extra={"request_id": request_id})
            return final_subtopics
            
        except Exception as e:
            logger.error(f"Failed to extract subtopics for topic {topic['name']}: {str(e)}", 
                        extra={"request_id": request_id})
            return []

    def _validate_detail(self, detail: Dict[str, Any]) -> bool:
        """Validate a single detail entry with more flexible constraints."""
        try:
            # Basic structure validation
            if not isinstance(detail, dict):
                logger.debug(f"Detail not a dict: {type(detail)}")
                return False
                
            # Required fields check
            if not all(k in detail for k in ['text', 'importance']):
                logger.debug(f"Missing required fields. Found keys: {detail.keys()}")
                return False
                
            # Text validation
            if not isinstance(detail['text'], str) or not detail['text'].strip():
                logger.debug("Invalid or empty text field")
                return False
                
            # Importance validation with case insensitivity
            valid_importance = ['high', 'medium', 'low']
            if detail['importance'].lower() not in valid_importance:
                logger.debug(f"Invalid importance: {detail['importance']}")
                return False
                
            # More generous length limit
            if len(detail['text']) > 500:  # Increased from 200
                logger.debug(f"Text too long: {len(detail['text'])} chars")
                return False
                
            return True
            
        except Exception as e:
            logger.debug(f"Validation error: {str(e)}")
            return False

    async def _extract_details(self, subtopic: Dict[str, Any], content: str, details_prompt_template: str, request_id: str) -> List[Dict[str, Any]]:
        """Extract details for a subtopic with more aggressive deduplication and content preservation."""
        MINIMUM_VALID_DETAILS = 5  # Early stopping threshold
        MAX_DETAILS = self.config['max_details']
        MAX_CONCURRENT_TASKS = 50  # Limit concurrent LLM calls
        
        # Create cache key
        content_hash = hashlib.md5(content.encode()).hexdigest()
        cache_key = f"details_{subtopic['name']}_{content_hash}_{request_id}"
        
        if not hasattr(self, '_details_cache'):
            self._details_cache = {}
        
        if not hasattr(self, '_processed_chunks_by_subtopic'):
            self._processed_chunks_by_subtopic = {}
        
        if subtopic['name'] not in self._processed_chunks_by_subtopic:
            self._processed_chunks_by_subtopic[subtopic['name']] = set()

        if not hasattr(self, '_current_details'):
            self._current_details = []

        async def extract_from_chunk(chunk: str) -> List[Dict[str, Any]]:
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_hash in self._processed_chunks_by_subtopic[subtopic['name']]:
                return []
                
            self._processed_chunks_by_subtopic[subtopic['name']].add(chunk_hash)
                
            enhanced_prompt = f"""You are an expert at identifying distinct, important details that support a specific subtopic.

            Subtopic: {subtopic['name']}

            {details_prompt_template.format(subtopic=subtopic['name'])}

            Additional requirements:
            1. Each detail MUST provide 3-5 sentences of specific, substantive information
            2. Include CONCRETE EXAMPLES, numbers, dates, or direct references from the text
            3. EXTRACT actual quotes or paraphrase specific passages from the source document
            4. Make each detail UNIQUELY VALUABLE - it should contain information not found in other details
            5. Focus on DEPTH rather than breadth - explore fewer ideas more thoroughly
            6. Include specific evidence, reasoning, or context that supports the subtopic
            7. Balance factual information with analytical insights
            8. Avoid generic statements that could apply to many documents

            Content chunk:
            {chunk}

            IMPORTANT: Return ONLY a JSON array where each object has:
            - "text": The detail text (3-5 sentences with specific examples and evidence)
            - "importance": "high", "medium", or "low" based on significance
            """

            try:
                response = await self.optimizer.generate_completion(
                    enhanced_prompt,
                    max_tokens=1000,
                    request_id=request_id,
                    task=f"extracting_details_{subtopic['name']}"
                )
                
                raw_details = self.llm_client._clean_detail_response(response)
                chunk_details = []
                seen_texts = {}
                
                for detail in raw_details:
                    if self._validate_detail(detail) and not await self.is_similar_to_existing(detail['text'], seen_texts, 'detail'):
                        seen_texts[detail['text']] = True
                        
                        # Ensure importance is valid
                        detail['importance'] = detail['importance'].lower()
                        if detail['importance'] not in ['high', 'medium', 'low']:
                            detail['importance'] = 'medium'
                        
                        # Add to results
                        chunk_details.append({
                            'text': detail['text'],
                            'importance': detail['importance']
                        })
                        self._current_details.append(detail)
                        
                        if len(self._current_details) >= MINIMUM_VALID_DETAILS:
                            logger.info(f"Reached minimum required details ({MINIMUM_VALID_DETAILS}) during chunk processing")
                            return chunk_details
                
                return chunk_details
                    
            except Exception as e:
                logger.error(f"Error extracting details from chunk for {subtopic['name']}: {str(e)}", 
                            extra={"request_id": request_id})
                return chunk_details if 'chunk_details' in locals() else []

        try:
            if cache_key in self._details_cache:
                return self._details_cache[cache_key]

            self._current_details = []
            chunk_size = min(8000, len(content) // 3) if len(content) > 6000 else 4000
            content_chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
            
            # Initialize concurrent processing controls
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            seen_texts = {}
            all_details = []
            early_stop = asyncio.Event()

            async def process_chunk(chunk: str) -> List[Dict[str, Any]]:
                """Process a single chunk with semaphore control."""
                if early_stop.is_set():
                    return []
                    
                async with semaphore:
                    chunk_details = await self.llm_client._retry_with_exponential_backoff(
                        lambda: extract_from_chunk(chunk)
                    )
                    
                    # Check if we've reached minimum details
                    if len(self._current_details) >= MINIMUM_VALID_DETAILS:
                        early_stop.set()
                    
                    return chunk_details

            # Process chunks concurrently
            chunk_results = await asyncio.gather(
                *(process_chunk(chunk) for chunk in content_chunks)
            )

            # Process results with more aggressive deduplication
            for chunk_details in chunk_results:
                for detail in chunk_details:
                    if not await self.is_similar_to_existing(detail['text'], seen_texts, 'detail'):
                        seen_texts[detail['text']] = True
                        all_details.append(detail)

                        if len(all_details) >= MINIMUM_VALID_DETAILS:
                            break

                if len(all_details) >= MINIMUM_VALID_DETAILS:
                    logger.info(f"Reached minimum required details ({MINIMUM_VALID_DETAILS})")
                    break

            # Always perform consolidation to reduce duplicative content
            consolidation_prompt = f"""You are consolidating details for the subtopic: {subtopic['name']}

            Current details:
            {json.dumps([d['text'] for d in all_details], indent=2)}

            Requirements:
            1. Aggressively merge details that convey similar information or concepts
            2. Eliminate all redundancy and repetitive information 
            3. Choose the most clear, concise, and informative phrasing for each detail
            4. Each final detail must provide unique information not covered by others
            5. Select 3-5 truly distinct details that together fully support the subtopic
            6. Ensure that even similar-sounding details have completely different content
            7. Choose clear, concise detail text that accurately represents the information
            8. Mark each detail with appropriate importance (high/medium/low)

            Return ONLY a JSON array of consolidated details with text and importance.
            Example:
            [
                {{"text": "First distinct detail", "importance": "high"}},
                {{"text": "Second distinct detail", "importance": "medium"}}
            ]"""

            try:
                consolidation_response = await self.llm_client._retry_generate_completion(
                    consolidation_prompt,
                    max_tokens=1000,
                    request_id=request_id,
                    task=f"consolidate_details_{subtopic['name']}"
                )
                
                consolidated_raw = self.llm_client._clean_detail_response(consolidation_response)
                
                if consolidated_raw:
                    seen_texts = {}
                    consolidated_details = []
                    
                    for detail in consolidated_raw:
                        if self._validate_detail(detail) and not await self.is_similar_to_existing(detail['text'], seen_texts, 'detail'):
                            seen_texts[detail['text']] = True
                            detail['importance'] = detail['importance'].lower()
                            if detail['importance'] not in ['high', 'medium', 'low']:
                                detail['importance'] = 'medium'
                            consolidated_details.append(detail)
                            
                    if consolidated_details:
                        all_details = consolidated_details
                        logger.info(f"Successfully consolidated details for {subtopic['name']} from {len(all_details)} to {len(consolidated_details)}")
                    
            except Exception as e:
                logger.warning(f"Detail consolidation failed for {subtopic['name']}: {str(e)}", 
                            extra={"request_id": request_id})
                # If consolidation fails, do a simple deduplication pass
                seen = set()
                deduplicated_details = []
                for detail in all_details:
                    if detail['text'] not in seen:
                        seen.add(detail['text'])
                        deduplicated_details.append(detail)
                all_details = deduplicated_details
                if len(self._current_details) >= MINIMUM_VALID_DETAILS:
                    logger.info(f"Using {len(self._current_details)} previously collected valid details")
                    all_details = self._current_details
                else:
                    importance_order = {"high": 0, "medium": 1, "low": 2}
                    all_details = sorted(
                        all_details,
                        key=lambda x: (importance_order.get(x["importance"].lower(), 3), -len(x["text"]))
                    )[:MAX_DETAILS]

            # Final LLM-based deduplication when we have enough details
            if len(all_details) > 3:  # Only if we have enough to potentially remove some
                details_to_remove = set()
                for i in range(len(all_details)-1):
                    if i in details_to_remove:
                        continue
                        
                    if len(all_details) - len(details_to_remove) <= 3:  # Ensure we keep at least 3 details
                        break
                        
                    for j in range(i+1, len(all_details)):
                        if j in details_to_remove:
                            continue
                        
                        try:
                            is_duplicate = await self.check_similarity_llm(
                                all_details[i]['text'], 
                                all_details[j]['text'],
                                f"detail of {subtopic['name']}", 
                                f"detail of {subtopic['name']}"
                            )
                            
                            if is_duplicate:
                                logger.info("LLM detected duplicate details")
                                
                                # Determine which to keep based on importance
                                importance_i = {"high": 3, "medium": 2, "low": 1}[all_details[i]['importance']]
                                importance_j = {"high": 3, "medium": 2, "low": 1}[all_details[j]['importance']]
                                
                                if importance_i >= importance_j:
                                    details_to_remove.add(j)
                                else:
                                    details_to_remove.add(i)
                                    break  # Break inner loop if we're removing i
                        except Exception as e:
                            logger.warning(f"LLM duplicate check failed: {str(e)}")
                            continue
                            
                # Apply removals
                all_details = [d for i, d in enumerate(all_details) if i not in details_to_remove]
            
            # Sort details by importance first, then by length (longer details typically have more substance)
            importance_order = {"high": 0, "medium": 1, "low": 2}
            final_details = sorted(
                all_details, 
                key=lambda x: (importance_order.get(x["importance"].lower(), 3), -len(x["text"]))
            )[:MAX_DETAILS]            
            self._details_cache[cache_key] = final_details
            
            logger.info(f"Successfully extracted {len(final_details)} details for {subtopic['name']}", 
                            extra={"request_id": request_id})
            return final_details
                
        except Exception as e:
            logger.error(f"Failed to extract details for subtopic {subtopic['name']}: {str(e)}", 
                        extra={"request_id": request_id})
            if hasattr(self, '_current_details') and len(self._current_details) > 0:
                logger.info(f"Returning {len(self._current_details)} collected details despite error")
                return self._current_details[:MAX_DETAILS]
            return []

    async def verify_mindmap_against_source(self, mindmap_data: Dict[str, Any], original_document: str) -> Dict[str, Any]:
        """Verify all mindmap nodes against the original document with lenient criteria and improved error handling."""
        try:
            logger.info("\n" + "="*80)
            logger.info(colored("🔍 STARTING REALITY CHECK TO IDENTIFY POTENTIAL CONFABULATIONS", "cyan", attrs=["bold"]))
            logger.info("="*80 + "\n")
            
            # Split document into chunks to handle context window limitations
            chunk_size = 8000  # Adjust based on model context window
            overlap = 250  # Characters of overlap between chunks
            
            # Create overlapping chunks
            doc_chunks = []
            start = 0
            while start < len(original_document):
                end = min(start + chunk_size, len(original_document))
                # Extend to nearest sentence end if possible
                if end < len(original_document):
                    next_period = original_document.find('.', end)
                    if next_period != -1 and next_period - end < 200:  # Don't extend too far
                        end = next_period + 1
                chunk = original_document[start:end]
                doc_chunks.append(chunk)
                start = end - overlap if end < len(original_document) else end
            
            logger.info(f"Split document into {len(doc_chunks)} chunks for verification")
            
            # Extract all nodes from mindmap for verification
            all_nodes = []
            
            def extract_nodes(node, path=None):
                """Recursively extract all nodes with their paths."""
                if path is None:
                    path = []
                
                if not node:
                    return
                    
                current_path = path.copy()
                
                # Add current node if it has a name
                if 'name' in node and node['name']:
                    node_type = 'root' if not path else 'topic' if len(path) == 1 else 'subtopic'
                    all_nodes.append({
                        'text': node['name'],
                        'path': current_path,
                        'type': node_type,
                        'verified': False,
                        'node_ref': node,  # Store reference to original node
                        'node_id': id(node),  # Store unique object ID as backup
                        'structural_importance': 'high' if node_type in ['root', 'topic'] else 'medium'
                    })
                    current_path = current_path + [node['name']]
                
                # Add details
                for detail in node.get('details', []):
                    if isinstance(detail, dict) and 'text' in detail:
                        all_nodes.append({
                            'text': detail['text'],
                            'path': current_path,
                            'type': 'detail',
                            'verified': False,
                            'node_ref': detail,  # Store reference to original node
                            'node_id': id(detail),  # Store unique object ID as backup
                            'structural_importance': 'low',
                            'importance': detail.get('importance', 'medium')
                        })
                
                # Process subtopics
                for subtopic in node.get('subtopics', []):
                    extract_nodes(subtopic, current_path)
            
            # Start extraction from central theme
            extract_nodes(mindmap_data.get('central_theme', {}))
            logger.info(f"Extracted {len(all_nodes)} nodes for verification")
            
            # Create verification batches to limit concurrent API calls
            batch_size = 5  # Number of nodes to verify in parallel
            node_batches = [all_nodes[i:i+batch_size] for i in range(0, len(all_nodes), batch_size)]
            
            # Track verification statistics
            verification_stats = {
                'total': len(all_nodes),
                'verified': 0,
                'not_verified': 0,
                'by_type': {
                    'topic': {'total': 0, 'verified': 0},
                    'subtopic': {'total': 0, 'verified': 0},
                    'detail': {'total': 0, 'verified': 0}
                }
            }
            
            for node_type in ['topic', 'subtopic', 'detail']:
                verification_stats['by_type'][node_type]['total'] = len([n for n in all_nodes if n.get('type') == node_type])
            
            # Function to verify a single node against a document chunk
            async def verify_node_in_chunk(node, chunk):
                """Verify if a node's content is actually present in or can be logically derived from a document chunk."""
                if not node or not chunk:
                    return False
                    
                # Check if node has required keys
                required_keys = ['type', 'text']
                if not all(key in node for key in required_keys):
                    logger.warning(f"Node missing required keys: {node}")
                    return True  # Consider verified if we can't properly check it
                    
                # Special handling for root node
                if node['type'] == 'root':
                    return True  # Always consider root node verified
                    
                node_text = node['text']
                node_type = node['type']
                path_str = ' → '.join(node['path']) if node['path'] else 'root'
                
                prompt = f"""You are an expert fact-checker verifying if information in a mindmap can be reasonably derived from the original document.

            Task: Determine if this {node_type} is supported by the document text or could be reasonably inferred from it.

            {node_type.title()}: "{node_text}"
            Path: {path_str}

            Document chunk:
            ```
            {chunk}
            ```

            VERIFICATION GUIDELINES:
            1. The {node_type} can be EXPLICITLY mentioned OR reasonably inferred from the document, even through logical deduction
            2. Logical synthesis, interpretation, and summarization of concepts in the document are STRONGLY encouraged
            3. Content that represents a reasonable conclusion or implication from the document should be VERIFIED
            4. Content that groups, categorizes, or abstracts ideas from the document should be VERIFIED
            5. High-level insights that connect multiple concepts from the document should be VERIFIED
            6. Only mark as unsupported if it contains specific claims that DIRECTLY CONTRADICT the document
            7. GIVE THE BENEFIT OF THE DOUBT - if the content could plausibly be derived from the document, verify it
            8. When uncertain, LEAN TOWARDS VERIFICATION rather than rejection - mindmaps are meant to be interpretive, not literal
            9. For details specifically, allow for more interpretive latitude - they represent insights derived from the document
            10. Consider historical and domain context that would be natural to include in an analysis

            Answer ONLY with one of these formats:
            - "YES: [brief explanation of how it's supported or can be derived]" 
            - "NO: [brief explanation of why it contains information that directly contradicts the document]"

            IMPORTANT: Remember to be GENEROUS in your interpretation. If there's any reasonable way the content could be derived from the document, even through multiple logical steps, mark it as verified. Only reject content that introduces completely new facts not derivable from the document or directly contradicts it."""

                try:
                    response = await self.llm_client._retry_generate_completion(
                        prompt,
                        max_tokens=150,
                        request_id='verify_node',
                        task="verifying_against_source"
                    )
                    
                    # Parse the response to get verification result
                    response = response.strip().upper()
                    is_verified = response.startswith("YES")
                    
                    # Log detailed verification result for debugging
                    logger.debug(
                        f"\n{colored('Verification result for', 'blue')}: {colored(node_text[:50] + '...', 'yellow')}\n"
                        f"Result: {colored('VERIFIED' if is_verified else 'NOT VERIFIED', 'green' if is_verified else 'red')}\n"
                        f"Response: {response[:100]}"
                    )
                    
                    return is_verified
                    
                except Exception as e:
                    logger.error(f"Error verifying node: {str(e)}")
                    # Be more lenient on errors - consider verified
                    return True
            
            # Process each node batch
            for batch_idx, batch in enumerate(node_batches):
                logger.info(f"Verifying batch {batch_idx+1}/{len(node_batches)} ({len(batch)} nodes)")
                
                # For each node, try to verify against any document chunk
                for node in batch:
                    if node.get('verified', False):
                        continue  # Skip if already verified
                        
                    node_verified = False
                    
                    # Try to verify against each chunk
                    for chunk_idx, chunk in enumerate(doc_chunks):
                        if await verify_node_in_chunk(node, chunk):
                            node['verified'] = True
                            node_verified = True
                            verification_stats['verified'] += 1
                            node_type = node.get('type', 'unknown')
                            if node_type in verification_stats['by_type']:
                                verification_stats['by_type'][node_type]['verified'] += 1
                            logger.info(
                                f"{colored('✅ VERIFIED', 'green', attrs=['bold'])}: "
                                f"{node.get('type', 'NODE').upper()} '{node.get('text', '')[:50]}...' "
                                f"(Found in chunk {chunk_idx+1})"
                            )
                            break
                    
                    if not node_verified:
                        verification_stats['not_verified'] += 1
                        logger.info(
                            f"{colored('❓ NOT VERIFIED', 'yellow', attrs=['bold'])}: "
                            f"{node.get('type', 'NODE').upper()} '{node.get('text', '')[:50]}...' "
                            f"(Not found in any chunk)"
                        )
            
            # Calculate verification percentages
            verification_percentage = (verification_stats['verified'] / verification_stats['total'] * 100) if verification_stats['total'] > 0 else 0
            for node_type in ['topic', 'subtopic', 'detail']:
                type_stats = verification_stats['by_type'][node_type]
                type_stats['percentage'] = (type_stats['verified'] / type_stats['total'] * 100) if type_stats['total'] > 0 else 0
            
            # Log verification statistics
            logger.info("\n" + "="*80)
            logger.info(colored("🔍 REALITY CHECK RESULTS", "cyan", attrs=['bold']))
            logger.info(f"Total nodes checked: {verification_stats['total']}")
            logger.info(f"Verified: {verification_stats['verified']} ({verification_percentage:.1f}%)")
            logger.info(f"Not verified: {verification_stats['not_verified']} ({100-verification_percentage:.1f}%)")
            logger.info("\nBreakdown by node type:")
            for node_type in ['topic', 'subtopic', 'detail']:
                type_stats = verification_stats['by_type'][node_type]
                logger.info(f"  {node_type.title()}s: {type_stats['verified']}/{type_stats['total']} verified ({type_stats['percentage']:.1f}%)")
            logger.info("="*80 + "\n")
            
            # Check if we need to preserve structure despite verification results
            min_topics_required = 3
            min_verification_ratio = 0.4  # Lower threshold - only filter if less than 40% verified
            
            # Count verified topics
            verified_topics = len([n for n in all_nodes if n.get('type') == 'topic' and n.get('verified', False)])
            
            # If verification removed too much content, we need to preserve structure
            if verified_topics < min_topics_required or verification_percentage < min_verification_ratio * 100:
                logger.warning(f"Verification would remove too much content (only {verified_topics} topics verified). Using preservation mode.")
                
                # Mark important structural nodes as verified to preserve mindmap structure
                for node in all_nodes:
                    # Always keep root and topic nodes
                    if node.get('type') in ['root', 'topic']:
                        node['verified'] = True
                    # Keep subtopics with a high enough importance
                    elif node.get('type') == 'subtopic' and not node.get('verified', False):
                        # Keep subtopics if they have verified details or are needed for structure
                        has_verified_details = any(
                            n.get('verified', False) and n.get('type') == 'detail' and n.get('path') == node.get('path', []) + [node.get('text', '')]
                            for n in all_nodes
                        )
                        if has_verified_details:
                            node['verified'] = True
                
                # Recalculate statistics
                verification_stats['verified'] = len([n for n in all_nodes if n.get('verified', False)])
                verification_stats['not_verified'] = len(all_nodes) - verification_stats['verified']
                verification_percentage = (verification_stats['verified'] / verification_stats['total'] * 100) if verification_stats['total'] > 0 else 0
                
                logger.info("\n" + "="*80)
                logger.info(colored("🔄 UPDATED REALITY CHECK WITH STRUCTURE PRESERVATION", "yellow", attrs=['bold']))
                logger.info(f"Verified after preservation: {verification_stats['verified']} ({verification_percentage:.1f}%)")
                logger.info(f"Not verified after preservation: {verification_stats['not_verified']} ({100-verification_percentage:.1f}%)")
                logger.info("="*80 + "\n")
            
            # Rebuild mindmap with preserving structure
            def rebuild_mindmap(node):
                """Recursively rebuild mindmap keeping only verified nodes."""
                if not node:
                    return None
                    
                result = copy.deepcopy(node)
                result['subtopics'] = []
                
                # Process subtopics and keep only verified ones
                verified_subtopics = []
                for subtopic in node.get('subtopics', []):
                    if not subtopic.get('name'):
                        continue
                        
                    # Check if this subtopic is verified by comparing with stored nodes
                    subtopic_verified = False
                    subtopic_id = id(subtopic)
                    
                    for n in all_nodes:
                        # First try to match by direct object reference
                        if n.get('node_ref') is subtopic and n.get('verified', False):
                            subtopic_verified = True
                            break
                        # Fallback to matching by object ID if reference comparison fails
                        elif n.get('node_id') == subtopic_id and n.get('verified', False):
                            subtopic_verified = True
                            break
                        # Last resort: match by name and path
                        elif (n.get('type') in ['topic', 'subtopic'] and 
                            n.get('text') == subtopic.get('name') and 
                            n.get('verified', False)):
                            subtopic_verified = True
                            break
                    
                    if subtopic_verified:
                        rebuilt_subtopic = rebuild_mindmap(subtopic)
                        if rebuilt_subtopic:
                            verified_subtopics.append(rebuilt_subtopic)
                
                result['subtopics'] = verified_subtopics
                
                # Filter details to keep only verified ones
                if 'details' in result:
                    verified_details = []
                    for detail in result.get('details', []):
                        if not isinstance(detail, dict) or 'text' not in detail:
                            continue
                            
                        # Check if this detail is verified
                        detail_verified = False
                        detail_id = id(detail)
                        
                        for n in all_nodes:
                            # First try to match by direct object reference
                            if n.get('node_ref') is detail and n.get('verified', False):
                                detail_verified = True
                                break
                            # Fallback to matching by object ID
                            elif n.get('node_id') == detail_id and n.get('verified', False):
                                detail_verified = True
                                break
                            # Last resort: match by text content
                            elif n.get('type') == 'detail' and n.get('text') == detail.get('text') and n.get('verified', False):
                                detail_verified = True
                                break
                        
                        if detail_verified:
                            verified_details.append(detail)
                    
                    result['details'] = verified_details
                
                # Only return node if it has content
                if result.get('subtopics') or result.get('details'):
                    return result
                return None
            
            # Rebuild mindmap with only verified content
            verified_mindmap = {
                'central_theme': rebuild_mindmap(mindmap_data.get('central_theme', {}))
            }
            
            # Final safety check - if we have no content after verification, use original
            if not verified_mindmap.get('central_theme') or not verified_mindmap.get('central_theme', {}).get('subtopics'):
                logger.warning("After verification, no valid content remains - using original mindmap with warning")
                return mindmap_data
            
            # Calculate how much content was preserved
            original_count = len(all_nodes)
            verified_count = len([n for n in all_nodes if n.get('verified', False)])
            preservation_rate = (verified_count / original_count * 100) if original_count > 0 else 0
            
            logger.info(
                f"\n{colored('✅ REALITY CHECK COMPLETE', 'green', attrs=['bold'])}\n"
                f"Preserved {verified_count}/{original_count} nodes ({preservation_rate:.1f}%)"
            )
            
            return verified_mindmap
        
        except Exception as e:
            # Better error handling with detailed logging
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error during verification: {str(e)}\n{error_details}")
            # Return the original mindmap in case of any errors
            return mindmap_data

    def _generate_mermaid_mindmap(self, concepts: Dict[str, Any]) -> str:
        """Generate complete Mermaid mindmap syntax from concepts.
        
        Args:
            concepts (Dict[str, Any]): The complete mindmap concept hierarchy
            
        Returns:
            str: Complete Mermaid mindmap syntax
        """
        mindmap_lines = ["mindmap"]
        
        # Start with root node - ignore any name/text for root, just use document emoji
        self._add_node_to_mindmap({'name': ''}, mindmap_lines, indent_level=1)
        
        # Add all main topics under root
        for topic in concepts.get('central_theme', {}).get('subtopics', []):
            self._add_node_to_mindmap(topic, mindmap_lines, indent_level=2)
        
        return "\n".join(mindmap_lines)

    def _convert_mindmap_to_markdown(self, mermaid_syntax: str) -> str:
        """Convert Mermaid mindmap syntax to properly formatted Markdown outline.
        
        Args:
            mermaid_syntax (str): The Mermaid mindmap syntax string
            
        Returns:
            str: Properly formatted Markdown outline
        """
        markdown_lines = []
        
        # Split into lines and process each (skip the 'mindmap' header)
        lines = mermaid_syntax.split('\n')[1:]
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
                
            # Count indentation level (number of 4-space blocks)
            indent_level = len(re.match(r'^\s*', line).group()) // 4
            
            # Extract the content between node shapes
            content = line.strip()
            
            # Handle different node types based on indent level
            if indent_level == 1 and '((📄))' in content:  # Root node
                continue  # Skip the document emoji node
                
            elif indent_level == 2:  # Main topics
                # Extract content between (( and ))
                node_text = re.search(r'\(\((.*?)\)\)', content)
                if node_text:
                    if markdown_lines:  # Add extra newline between main topics
                        markdown_lines.append("")
                    current_topic = node_text.group(1).strip()
                    markdown_lines.append(f"# {current_topic}")
                    markdown_lines.append("")  # Add blank line after topic
                    
            elif indent_level == 3:  # Subtopics
                # Extract content between ( and )
                node_text = re.search(r'\((.*?)\)', content)
                if node_text:
                    if markdown_lines and not markdown_lines[-1].startswith("#"):
                        markdown_lines.append("")
                    current_subtopic = node_text.group(1).strip()
                    markdown_lines.append(f"## {current_subtopic}")
                    markdown_lines.append("")  # Add blank line after subtopic
                    
            elif indent_level == 4:  # Details
                # Extract content between [ and ]
                node_text = re.search(r'\[(.*?)\]', content)
                if node_text:
                    detail_text = node_text.group(1).strip()
                    markdown_lines.append(detail_text)
                    markdown_lines.append("")  # Add blank line after each detail
        
        # Join lines with proper spacing
        markdown_text = "\n".join(markdown_lines)
        
        # Clean up any lingering Mermaid syntax artifacts
        markdown_text = re.sub(r'\\\(', '(', markdown_text)
        markdown_text = re.sub(r'\\\)', ')', markdown_text)
        markdown_text = re.sub(r'\\(?=[()])', '', markdown_text)
        
        # Clean up multiple consecutive blank lines
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        return markdown_text.strip()
    
