from .config import Config, get_logger
from termcolor import colored
from datetime import datetime
from typing import Dict, Any

logger = get_logger()


class TokenUsageTracker:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0
        self.call_counts = {}
        self.token_counts_by_task = {}
        self.cost_by_task = {}
        
        # Categorize tasks for better reporting
        self.task_categories = {
            'topics': ['extracting_main_topics', 'consolidating_topics', 'detecting_document_type'],
            'subtopics': ['extracting_subtopics', 'consolidate_subtopics'],
            'details': ['extracting_details', 'consolidate_details'],
            'similarity': ['checking_content_similarity'],
            'verification': ['verifying_against_source'],
            'emoji': ['selecting_emoji'],
            'other': []  # Catch-all for uncategorized tasks
        }
        
        # Initialize counters for each category
        self.call_counts_by_category = {category: 0 for category in self.task_categories}
        self.token_counts_by_category = {category: {'input': 0, 'output': 0} for category in self.task_categories}
        self.cost_by_category = {category: 0 for category in self.task_categories}
        
    def update(self, input_tokens: int, output_tokens: int, task: str):
        """Update token usage with enhanced task categorization."""
        # Update base metrics
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        # Calculate cost based on provider
        task_cost = 0
        if Config.API_PROVIDER == "CLAUDE":
            task_cost = (
                input_tokens * Config.ANTHROPIC_INPUT_TOKEN_PRICE + 
                output_tokens * Config.ANTHROPIC_OUTPUT_TOKEN_PRICE
            )
        elif Config.API_PROVIDER == "DEEPSEEK":
            # Different pricing for chat vs reasoner model
            if Config.DEEPSEEK_COMPLETION_MODEL == Config.DEEPSEEK_CHAT_MODEL:
                task_cost = (
                    input_tokens * Config.DEEPSEEK_CHAT_INPUT_PRICE + 
                    output_tokens * Config.DEEPSEEK_CHAT_OUTPUT_PRICE
                )
            else:  # reasoner model
                task_cost = (
                    input_tokens * Config.DEEPSEEK_REASONER_INPUT_PRICE + 
                    output_tokens * Config.DEEPSEEK_REASONER_OUTPUT_PRICE
                )
        elif Config.API_PROVIDER == "GEMINI":
            task_cost = (
                input_tokens * Config.GEMINI_INPUT_TOKEN_PRICE + 
                output_tokens * Config.GEMINI_OUTPUT_TOKEN_PRICE
            )
        else:  # OPENAI
            task_cost = (
                input_tokens * Config.OPENAI_INPUT_TOKEN_PRICE + 
                output_tokens * Config.OPENAI_OUTPUT_TOKEN_PRICE
            )
            
        self.total_cost += task_cost
        
        # Update task-specific metrics
        if task not in self.token_counts_by_task:
            self.token_counts_by_task[task] = {'input': 0, 'output': 0}
            self.cost_by_task[task] = 0
            
        self.token_counts_by_task[task]['input'] += input_tokens
        self.token_counts_by_task[task]['output'] += output_tokens
        self.call_counts[task] = self.call_counts.get(task, 0) + 1
        self.cost_by_task[task] = self.cost_by_task.get(task, 0) + task_cost
        
        # Update category metrics
        category_found = False
        for category, tasks in self.task_categories.items():
            if any(task.startswith(t) for t in tasks) or (category == 'other' and not category_found):
                self.call_counts_by_category[category] += 1
                self.token_counts_by_category[category]['input'] += input_tokens
                self.token_counts_by_category[category]['output'] += output_tokens
                self.cost_by_category[category] += task_cost
                category_found = True
                break
    
    def get_enhanced_summary(self) -> Dict[str, Any]:
        """Get enhanced usage summary with category breakdowns and percentages."""
        total_calls = sum(self.call_counts.values())
        total_cost = sum(self.cost_by_task.values())
        
        # Calculate percentages for call counts by category
        call_percentages = {}
        for category, count in self.call_counts_by_category.items():
            call_percentages[category] = (count / total_calls * 100) if total_calls > 0 else 0
            
        # Calculate percentages for token counts by category
        token_percentages = {}
        for category, counts in self.token_counts_by_category.items():
            total_tokens = counts['input'] + counts['output']
            token_percentages[category] = (total_tokens / (self.total_input_tokens + self.total_output_tokens) * 100) if (self.total_input_tokens + self.total_output_tokens) > 0 else 0
            
        # Calculate percentages for cost by category
        cost_percentages = {}
        for category, cost in self.cost_by_category.items():
            cost_percentages[category] = (cost / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "total_calls": total_calls,
            "calls_by_task": dict(self.call_counts),
            "token_counts_by_task": self.token_counts_by_task,
            "cost_by_task": {task: round(cost, 6) for task, cost in self.cost_by_task.items()},
            "categories": {
                category: {
                    "calls": count,
                    "calls_percentage": round(call_percentages[category], 2),
                    "tokens": self.token_counts_by_category[category],
                    "tokens_percentage": round(token_percentages[category], 2),
                    "cost_usd": round(self.cost_by_category[category], 6),
                    "cost_percentage": round(cost_percentages[category], 2)
                }
                for category, count in self.call_counts_by_category.items()
            }
        }
        
    def print_usage_report(self):
        """Print a detailed usage report to the console."""
        summary = self.get_enhanced_summary()
        
        # Helper to format USD amounts
        def fmt_usd(amount):
            return f"${amount:.6f}"
        
        # Helper to format percentages
        def fmt_pct(percentage):
            return f"{percentage:.2f}%"
        
        # Helper to format numbers with commas
        def fmt_num(num):
            return f"{num:,}"
        
        # Find max task name length for proper column alignment
        max_task_length = max([len(task) for task in summary['calls_by_task'].keys()], default=30)
        task_col_width = max(max_task_length + 2, 30)
        
        report = [
            "\n" + "="*80,
            colored("📊 TOKEN USAGE AND COST REPORT", "cyan", attrs=["bold"]),
            "="*80,
            "",
            f"Total Tokens: {fmt_num(summary['total_tokens'])} (Input: {fmt_num(summary['total_input_tokens'])}, Output: {fmt_num(summary['total_output_tokens'])})",
            f"Total Cost: {fmt_usd(summary['total_cost_usd'])}",
            f"Total API Calls: {fmt_num(summary['total_calls'])}",
            "",
            colored("BREAKDOWN BY CATEGORY", "yellow", attrs=["bold"]),
            "-"*80,
            "Category".ljust(15) + "Calls".rjust(10) + "Call %".rjust(10) + "Tokens".rjust(12) + "Token %".rjust(10) + "Cost".rjust(12) + "Cost %".rjust(10),
            "-"*80
        ]
        
        for category, data in summary['categories'].items():
            if data['calls'] > 0:
                tokens = data['tokens']['input'] + data['tokens']['output']
                report.append(
                    category.ljust(15) + 
                    fmt_num(data['calls']).rjust(10) + 
                    fmt_pct(data['calls_percentage']).rjust(10) + 
                    fmt_num(tokens).rjust(12) + 
                    fmt_pct(data['tokens_percentage']).rjust(10) + 
                    fmt_usd(data['cost_usd']).rjust(12) + 
                    fmt_pct(data['cost_percentage']).rjust(10)
                )
                
        report.extend([
            "-"*80,
            "",
            colored("DETAILED BREAKDOWN BY TASK", "yellow", attrs=["bold"]),
            "-"*80,
            "Task".ljust(task_col_width) + "Calls".rjust(8) + "Input".rjust(12) + "Output".rjust(10) + "Cost".rjust(12),
            "-"*80
        ])
        
        # Sort tasks by cost (highest first)
        sorted_tasks = sorted(
            summary['cost_by_task'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for task, cost in sorted_tasks:
            if cost > 0:
                report.append(
                    task.ljust(task_col_width) + 
                    fmt_num(summary['calls_by_task'][task]).rjust(8) + 
                    fmt_num(summary['token_counts_by_task'][task]['input']).rjust(12) + 
                    fmt_num(summary['token_counts_by_task'][task]['output']).rjust(10) + 
                    fmt_usd(cost).rjust(12)
                )
                
        report.extend([
            "-"*80,
            "",
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "="*80,
        ])
        
        logger.info("\n".join(report))