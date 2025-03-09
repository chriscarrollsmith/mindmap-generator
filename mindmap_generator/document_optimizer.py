from typing import Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from termcolor import colored
from .config import Config
from .token_usage import TokenUsageTracker
from .config import get_logger

logger = get_logger()

class DocumentOptimizer:
    """Minimal document optimizer that only implements what's needed for mindmap generation."""
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.anthropic_client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.deepseek_client = AsyncOpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )
        # Initialize Google GenAI client - no need for configure method
        self.gemini_client = genai.Client(
            api_key=Config.GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"}
        )
        self.token_tracker = TokenUsageTracker()
        
    async def generate_completion(self, prompt: str, max_tokens: int = 5000, request_id: str = None, task: Optional[str] = None) -> Optional[str]:
        try:
            # Log the start of the request with truncated prompt
            prompt_preview = " ".join(prompt.split()[:40])  # Get first 40 words
            logger.info(
                f"\n{colored('🔄 API Request', 'cyan', attrs=['bold'])}\n"
                f"Task: {colored(task or 'unknown', 'yellow')}\n"
                f"Provider: {colored(Config.API_PROVIDER, 'blue')}\n"
                f"Prompt preview: {colored(prompt_preview + '...', 'white')}"
            )
            if Config.API_PROVIDER == "CLAUDE":
                async with self.anthropic_client.messages.stream(
                    model=Config.CLAUDE_MODEL_STRING,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                ) as stream:
                    message = await stream.get_final_message()
                    response_preview = " ".join(message.content[0].text.split()[:30])
                    self.token_tracker.update(
                        message.usage.input_tokens,
                        message.usage.output_tokens,
                        task or "unknown"
                    )
                    logger.info(
                        f"\n{colored('✅ API Response', 'green', attrs=['bold'])}\n"
                        f"Response preview: {colored(response_preview + '...', 'white')}\n"
                        f"Tokens: {colored(f'Input={message.usage.input_tokens}, Output={message.usage.output_tokens}', 'yellow')}"
                    )
                    return message.content[0].text
            elif Config.API_PROVIDER == "DEEPSEEK":
                kwargs = {
                    "model": Config.DEEPSEEK_COMPLETION_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "stream": False
                }
                if Config.DEEPSEEK_COMPLETION_MODEL == Config.DEEPSEEK_CHAT_MODEL:
                    kwargs["temperature"] = 0.7
                response = await self.deepseek_client.chat.completions.create(**kwargs)
                response_preview = " ".join(response.choices[0].message.content.split()[:30])
                self.token_tracker.update(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    task or "unknown"
                )
                logger.info(
                    f"\n{colored('✅ API Response', 'green', attrs=['bold'])}\n"
                    f"Response preview: {colored(response_preview + '...', 'white')}\n"
                    f"Tokens: {colored(f'Input={response.usage.prompt_tokens}, Output={response.usage.completion_tokens}', 'yellow')}"
                )
                return response.choices[0].message.content
            elif Config.API_PROVIDER == "GEMINI":
                # Use Gemini's live connection API for interactive chat
                response_text = ""
                # Track token usage for Gemini (estimated based on input/output text)
                char_to_token_ratio = 4  # rough estimate: 4 chars per token
                
                # Use the correct models.generate_content method as shown in the documentation
                try:
                    response = self.gemini_client.models.generate_content(
                        model=Config.GEMINI_MODEL_STRING,
                        contents=prompt,
                    )
                    response_text = response.text
                except Exception as model_error:
                    logger.error(f"Gemini API error: {str(model_error)}")
                    return None
                
                # Estimate token usage (Gemini doesn't provide token counts directly)
                estimated_input_tokens = len(prompt) // char_to_token_ratio
                estimated_output_tokens = len(response_text) // char_to_token_ratio
                
                response_preview = " ".join(response_text.split()[:30])
                self.token_tracker.update(
                    estimated_input_tokens,
                    estimated_output_tokens,
                    task or "unknown"
                )
                logger.info(
                    f"\n{colored('✅ API Response', 'green', attrs=['bold'])}\n"
                    f"Response preview: {colored(response_preview + '...', 'white')}\n"
                    f"Tokens (estimated): {colored(f'Input≈{estimated_input_tokens}, Output≈{estimated_output_tokens}', 'yellow')}"
                )
                return response_text
            elif Config.API_PROVIDER == "OPENAI":
                response = await self.openai_client.chat.completions.create(
                    model=Config.OPENAI_COMPLETION_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.7
                )
                response_preview = " ".join(response.choices[0].message.content.split()[:30])
                self.token_tracker.update(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    task or "unknown"
                )
                logger.info(
                    f"\n{colored('✅ API Response', 'green', attrs=['bold'])}\n"
                    f"Response preview: {colored(response_preview + '...', 'white')}\n"
                    f"Tokens: {colored(f'Input={response.usage.prompt_tokens}, Output={response.usage.completion_tokens}', 'yellow')}"
                )
                return response.choices[0].message.content
            else:
                raise ValueError(f"Invalid API_PROVIDER: {Config.API_PROVIDER}")
        except Exception as e:
            logger.error(
                f"\n{colored('❌ API Error', 'red', attrs=['bold'])}\n"
                f"Error: {colored(str(e), 'red')}"
            )
            return None