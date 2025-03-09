import asyncio
import json
import re
import random
from typing import Any, List, Dict, Union, Optional
from .config import get_logger
from .document_optimizer import DocumentOptimizer

logger = get_logger()

class LLMClient:
    """Handles all interactions with the Language Learning Model."""

    def __init__(self, optimizer: DocumentOptimizer, retry_config: Dict[str, Any]):
        self.optimizer = optimizer
        self.retry_config = retry_config
        self.control_chars_regex = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]')
        self.unescaped_quotes_regex = re.compile(r'(?<!\\)"(?!,|\s*[}\]])')

    async def _retry_with_exponential_backoff(self, func, *args, **kwargs):
        """Enhanced retry mechanism with jitter and circuit breaker."""
        retries = 0
        max_retries = self.retry_config['max_retries']
        base_delay = self.retry_config['base_delay']
        max_delay = self.retry_config['max_delay']

        while retries < max_retries:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    raise

                delay = min(base_delay * (2 ** (retries - 1)), max_delay)
                actual_delay = random.uniform(0, delay)

                logger.warning(f"Attempt {retries}/{max_retries} failed: {str(e)}. "
                            f"Retrying in {actual_delay:.2f}s")

                await asyncio.sleep(actual_delay)

    async def generate_completion(self, prompt: str, max_tokens: int, request_id: str, task: str) -> str:
        """Generates completion with retries."""
        return await self._retry_with_exponential_backoff(
            self.optimizer.generate_completion,
            prompt,
            max_tokens=max_tokens,
            request_id=request_id,
            task=task
        )

    async def _retry_generate_completion(self, prompt: str, max_tokens: int, request_id: str, task: str) -> str:
        """Retry the LLM completion in case of failures with exponential backoff."""
        retries = 0
        base_delay = 1  # Start with 1 second delay
        
        while retries < self.config['max_retries']:
            try:
                response = await self.optimizer.generate_completion(
                    prompt,
                    max_tokens=max_tokens,
                    request_id=request_id,
                    task=task
                )
                return response
            except Exception as e:
                retries += 1
                if retries >= self.config['max_retries']:
                    logger.error(f"Exceeded maximum retries for {task}", extra={"request_id": request_id})
                    raise
                
                delay = min(base_delay * (2 ** (retries - 1)), 10)  # Cap at 10 seconds
                logger.warning(f"Retrying {task} ({retries}/{self.config['max_retries']}) after {delay}s: {str(e)}", extra={"request_id": request_id})
                await asyncio.sleep(delay)

    def _validate_parsed_response(self, parsed: Any, expected_type: str) -> Union[List[Any], Dict[str, Any]]:
        """Validate and normalize parsed JSON response."""
        if expected_type == "array":
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                # Try to extract array from common fields
                for key in ['items', 'topics', 'elements', 'data']:
                    if isinstance(parsed.get(key), list):
                        return parsed[key]
                logger.debug("No array found in dictionary fields")
                return []
            else:
                logger.debug(f"Unexpected type for array response: {type(parsed)}")
                return []

        return parsed if isinstance(parsed, dict) else {}
    
    def _clean_detail_response(self, response: str) -> List[Dict[str, str]]:
        """Clean and validate detail responses."""
        try:
            # Remove markdown code blocks if present
            if '```' in response:
                matches = re.findall(r'```(?:json)?(.*?)```', response, re.DOTALL)
                if matches:
                    response = matches[0].strip()
                    
            # Basic cleanup
            response = response.strip()
            
            try:
                parsed = json.loads(response)
            except json.JSONDecodeError:
                # Try cleaning quotes and parse again
                response = response.replace("'", '"')
                try:
                    parsed = json.loads(response)
                except json.JSONDecodeError:
                    return []
                    
            # Handle both array and single object responses
            if isinstance(parsed, dict):
                parsed = [parsed]
                
            # Validate each detail
            valid_details = []
            seen_texts = set()
            
            for item in parsed:
                try:
                    text = str(item.get('text', '')).strip()
                    importance = str(item.get('importance', 'medium')).lower()
                    
                    # Skip empty text or duplicates
                    if not text or text in seen_texts:
                        continue
                        
                    if importance not in ['high', 'medium', 'low']:
                        importance = 'medium'
                        
                    seen_texts.add(text)
                    valid_details.append({
                        'text': text,
                        'importance': importance
                    })
                    
                except Exception as e:
                    logger.debug(f"Error processing detail item: {str(e)}")
                    continue
                    
            return valid_details
            
        except Exception as e:
            logger.error(f"Error in detail cleaning: {str(e)}")
            return []

    def _clean_json_response(self, response: str) -> str:
        """Enhanced JSON response cleaning with advanced recovery and validation."""
        if not response or not isinstance(response, str):
            logger.warning("Empty or invalid response type received")
            return "[]"  # Return empty array as safe default
            
        try:
            # First try to find complete JSON structure
            def find_json_structure(text: str) -> Optional[str]:
                # Look for array pattern
                array_match = re.search(r'\[[\s\S]*?\](?=\s*$|\s*[,}\]])', text)
                if array_match:
                    return array_match.group(0)
                    
                # Look for object pattern
                object_match = re.search(r'\{[\s\S]*?\}(?=\s*$|\s*[,\]}])', text)
                if object_match:
                    return object_match.group(0)
                
                return None

            # Handle markdown code blocks first
            if '```' in response:
                code_blocks = re.findall(r'```(?:json)?([\s\S]*?)```', response)
                if code_blocks:
                    for block in code_blocks:
                        if json_struct := find_json_structure(block):
                            response = json_struct
                            break
            else:
                if json_struct := find_json_structure(response):
                    response = json_struct

            # Advanced character cleaning
            def clean_characters(self, text: str) -> str:
                # Remove control characters while preserving valid whitespace
                text = self.control_chars_regex.sub('', text)
                
                # Normalize quotes and apostrophes
                text = text.replace('“', '"').replace('”', '"')  # Smart double quotes to straight double quotes
                text = text.replace('’', "'").replace('‘', "'")  # Smart single quotes to straight single quotes
                text = text.replace("'", '"')  # Convert single quotes to double quotes
                
                # Normalize whitespace
                text = ' '.join(text.split())
                
                # Escape unescaped quotes within strings
                text = self.unescaped_quotes_regex.sub('\\"', text)
                
                return text

            response = clean_characters(response)

            # Fix common JSON syntax issues
            def fix_json_syntax(text: str) -> str:
                # Fix trailing/multiple commas
                text = re.sub(r',\s*([\]}])', r'\1', text)  # Remove trailing commas
                text = re.sub(r',\s*,', ',', text)  # Remove multiple commas
                
                # Fix missing quotes around keys
                text = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
                
                # Ensure proper array/object closure
                brackets_stack = []
                for char in text:
                    if char in '[{':
                        brackets_stack.append(char)
                    elif char in ']}':
                        if not brackets_stack:
                            continue  # Skip unmatched closing brackets
                        if (char == ']' and brackets_stack[-1] == '[') or (char == '}' and brackets_stack[-1] == '{'):
                            brackets_stack.pop()
                        
                # Close any unclosed brackets
                while brackets_stack:
                    text += ']' if brackets_stack.pop() == '[' else '}'
                
                return text

            response = fix_json_syntax(response)

            # Validate and normalize structure
            def normalize_structure(text: str) -> str:
                try:
                    # Try parsing to validate
                    parsed = json.loads(text)
                    
                    # Ensure we have an array
                    if isinstance(parsed, dict):
                        # Convert single object to array
                        return json.dumps([parsed])
                    elif isinstance(parsed, list):
                        return json.dumps(parsed)
                    else:
                        return json.dumps([str(parsed)])
                        
                except json.JSONDecodeError:
                    # If still invalid, attempt emergency recovery
                    if text.strip().startswith('{'):
                        return f"[{text.strip()}]"  # Wrap object in array
                    elif not text.strip().startswith('['):
                        return f"[{text.strip()}]"  # Wrap content in array
                    return text
            
            response = normalize_structure(response)

            # Final validation
            try:
                json.loads(response)  # Verify we have valid JSON
                return response
            except json.JSONDecodeError as e:
                logger.warning(f"Final JSON validation failed: {str(e)}")
                # If all cleaning failed, return empty array
                return "[]"

        except Exception as e:
            logger.error(f"Error during JSON response cleaning: {str(e)}")
            return "[]"
    
    def _parse_llm_response(self, response: str, expected_type: str = "array") -> Union[List[Any], Dict[str, Any]]:
        """Parse and validate LLM response."""
        if not response or not isinstance(response, str):
            logger.warning("Empty or invalid response type received")
            return [] if expected_type == "array" else {}

        try:
            # Extract JSON from markdown code blocks if present
            if '```' in response:
                matches = re.findall(r'```(?:json)?(.*?)```', response, re.DOTALL)
                if matches:
                    response = matches[0].strip()

            # Basic cleanup
            response = response.strip()
            
            try:
                parsed = json.loads(response)
                return self.llm_client._validate_parsed_response(parsed, expected_type)
            except json.JSONDecodeError:
                # Try cleaning quotes and parse again
                response = response.replace("'", '"')
                try:
                    parsed = json.loads(response)
                    return self.llm_client._validate_parsed_response(parsed, expected_type)
                except json.JSONDecodeError:
                    # If we still can't parse, try emergency extraction for arrays
                    if expected_type == "array":
                        items = re.findall(r'"([^"]+)"', response)
                        if items:
                            return items

                        # Try line-by-line extraction
                        lines = response.strip().split('\n')
                        items = [line.strip().strip(',"\'[]{}') for line in lines 
                                if line.strip() and not line.strip().startswith(('```', '{', '}'))]
                        if items:
                            return items

                    return [] if expected_type == "array" else {}

        except Exception as e:
            logger.error(f"Unexpected error in JSON parsing: {str(e)}")
            return [] if expected_type == "array" else {}
