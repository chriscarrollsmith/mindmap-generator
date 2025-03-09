import logging
from decouple import Config as DecoupleConfig, RepositoryEnv
from termcolor import colored
from datetime import datetime

config = DecoupleConfig(RepositoryEnv('.env'))

def get_logger():
    """Mindmap-specific logger with colored output for generation stages."""
    logger = logging.getLogger("mindmap_generator")
    if not logger.handlers:
        handler = logging.StreamHandler()
        
        # Custom formatter that adds colors specific to mindmap generation stages
        def colored_formatter(record):
            message = record.msg
            
            # Color-code specific mindmap generation stages and metrics
            if "Starting mindmap generation" in message:
                message = colored("🚀 " + message, "cyan", attrs=["bold"])
            elif "Detected document type:" in message:
                doc_type = message.split(": ")[1]
                message = f"📄 Document Type: {colored(doc_type, 'yellow', attrs=['bold'])}"
            elif "Extracting main topics" in message:
                message = colored("📌 " + message, "blue")
            elif "Processing topic" in message:
                # Highlight topic name and progress
                parts = message.split("'")
                if len(parts) >= 3:
                    topic_name = parts[1]
                    message = f"🔍 Processing: {colored(topic_name, 'green')} {colored(parts[2], 'white')}"
            elif "Successfully extracted" in message:
                if "topics" in message:
                    message = colored("✅ " + message, "green")
                elif "subtopics" in message:
                    message = colored("➕ " + message, "cyan")
                elif "details" in message:
                    message = colored("📝 " + message, "blue")
            elif "Approaching word limit" in message:
                message = colored("⚠️ " + message, "yellow")
            elif "Error" in message or "Failed" in message:
                message = colored("❌ " + message, "red", attrs=["bold"])
            elif "Completion status:" in message:
                # Highlight progress metrics
                message = message.replace("Completion status:", colored("📊 Progress:", "cyan", attrs=["bold"]))
                metrics = message.split("Progress:")[1]
                parts = metrics.split(",")
                colored_metrics = []
                for part in parts:
                    if ":" in part:
                        label, value = part.split(":")
                        colored_metrics.append(f"{label}:{colored(value, 'yellow')}")
                message = "📊 Progress:" + ",".join(colored_metrics)
            elif "Mindmap generation completed" in message:
                message = colored("🎉 " + message, "green", attrs=["bold"])
                
            # Format timestamp and add any extra attributes
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            log_message = f"{colored(timestamp, 'white')} {message}"
            
            # Add any extra attributes in grey
            if hasattr(record, 'extra') and record.extra:
                extra_str = ' '.join(f"{k}={v}" for k, v in record.extra.items())
                log_message += f" {colored(f'[{extra_str}]', 'grey')}"
                
            return log_message
            
        class MindmapFormatter(logging.Formatter):
            def format(self, record):
                return colored_formatter(record)
                
        handler.setFormatter(MindmapFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class Config:
    """Minimal configuration for document processing."""
    # API configuration
    OPENAI_API_KEY = config.get("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = config.get('ANTHROPIC_API_KEY')
    DEEPSEEK_API_KEY = config.get('DEEPSEEK_API_KEY')
    GEMINI_API_KEY = config.get('GEMINI_API_KEY')  # Add Gemini API key
    API_PROVIDER = config.get('API_PROVIDER') # "OPENAI", "CLAUDE", "DEEPSEEK", or "GEMINI"
    
    # Model settings
    CLAUDE_MODEL_STRING = "claude-3-5-haiku-latest"
    OPENAI_COMPLETION_MODEL = "gpt-4o-mini-2024-07-18"
    DEEPSEEK_COMPLETION_MODEL = "deepseek-chat"  # "deepseek-reasoner" or "deepseek-chat"
    DEEPSEEK_CHAT_MODEL = "deepseek-chat"
    DEEPSEEK_REASONER_MODEL = "deepseek-reasoner"
    GEMINI_MODEL_STRING = "gemini-2.0-flash-lite"  # Add Gemini model string
    CLAUDE_MAX_TOKENS = 200000
    OPENAI_MAX_TOKENS = 8192
    DEEPSEEK_MAX_TOKENS = 8192
    GEMINI_MAX_TOKENS = 8192  # Add Gemini max tokens
    TOKEN_BUFFER = 500
    
    # Cost tracking (prices in USD per token)
    OPENAI_INPUT_TOKEN_PRICE = 0.15/1000000  # GPT-4o-mini input price
    OPENAI_OUTPUT_TOKEN_PRICE = 0.60/1000000  # GPT-4o-mini output price
    ANTHROPIC_INPUT_TOKEN_PRICE = 0.80/1000000  # Claude 3.5 Haiku input price
    ANTHROPIC_OUTPUT_TOKEN_PRICE = 4.00/1000000  # Claude 3.5 Haiku output price
    DEEPSEEK_CHAT_INPUT_PRICE = 0.27/1000000  # Chat input price (cache miss)
    DEEPSEEK_CHAT_OUTPUT_PRICE = 1.10/1000000  # Chat output price
    DEEPSEEK_REASONER_INPUT_PRICE = 0.14/1000000  # Reasoner input price (cache miss)
    DEEPSEEK_REASONER_OUTPUT_PRICE = 2.19/1000000  # Reasoner output price (includes CoT)
    GEMINI_INPUT_TOKEN_PRICE = 0.075/1000000  # Gemini 2.0 Flash Lite input price estimate
    GEMINI_OUTPUT_TOKEN_PRICE = 0.30/1000000  # Gemini 2.0 Flash Lite output price estimate