# Mindmap Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent document analysis tool that uses Large Language Models to generate comprehensive, hierarchical mindmaps from any text document.

<table>
  <tr>
    <td width="50%"><strong>Interactive Mermaid Diagram</strong></td>
    <td width="50%"><strong>Markdown Outline</strong></td>
  </tr>
  <tr>
    <td><img src="https://github.com/Dicklesworthstone/mindmap-generator/raw/refs/heads/main/screenshots/mermaid_diagram_example_durnovo.webp" alt="Mermaid mindmap diagram example"></td>
    <td><img src="https://github.com/Dicklesworthstone/mindmap-generator/raw/refs/heads/main/screenshots/mindmap_outline_md_example_durnovo.webp" alt="Markdown outline example"></td>
  </tr>
  <tr>
    <td><em>Interactive HTML visualization with expandable nodes</em></td>
    <td><em>Hierarchical Markdown output for easy reference</em></td>
  </tr>
</table>

## 🧠 Overview

The Mindmap Generator is a sophisticated document analysis system that extracts the core concepts, relationships, and details from text documents and organizes them into intuitive, hierarchical mindmaps. Unlike simple text summarization, this tool:

- Intelligently adapts to different document types (legal, technical, scientific, narrative, etc.)
- Creates multi-level hierarchical representations (topics, subtopics, details)
- Ensures factual accuracy by verifying against the source document
- Eliminates redundant or overlapping concepts
- Generates outputs in multiple formats (Mermaid syntax, HTML, Markdown)

The system is built to work with a variety of LLM providers (OpenAI, Anthropic/Claude, DeepSeek, Google Gemini) and optimizes for both cost-efficiency and output quality.

You can read a detailed blog post about the making of this project and the various challenges and design considerations that went into the design and engineering of it [here](https://fixmydocuments.com/blog/04_making_of_the_mindmap_generator).

## 📋 Features

- **Document Type Detection**: Automatically adapts extraction strategies based on document type
- **Hierarchical Content Extraction**: Builds three-level hierarchies (topics → subtopics → details)
- **Reality Checking**: Verifies generated content against the source document to prevent confabulation
- **Duplicate Detection**: Uses both fuzzy matching and semantic similarity to avoid redundancy
- **Multi-format Output**:
  - Mermaid mindmap syntax
  - Interactive HTML with Mermaid rendering
  - Markdown outline
- **Cost Optimization**: Designed to work efficiently with value-priced LLMs
- **Rich Logging**: Detailed, color-coded progress tracking (see an example [here](https://github.com/Dicklesworthstone/mindmap-generator/raw/refs/heads/main/screenshots/logging_output_during_run.webp))

## ⚙️ Installation

1. Install `uv` and Python 3.12 (if needed).
2. Clone the repository:

```bash
git clone https://github.com/Dicklesworthstone/mindmap-generator    
cd mindmap-generator          
```

3. Install the dependencies:

```bash
uv sync
```

4. Set up your environment:

Create a `.env` file with your API keys:

```ini
OPENAI_API_KEY="your-key"
ANTHROPIC_API_KEY="your-key" 
DEEPSEEK_API_KEY="your-key"
GEMINI_API_KEY="your-key"
API_PROVIDER="OPENAI"  # Options: "OPENAI", "CLAUDE", "DEEPSEEK", or "GEMINI"
```

## 🚀 Usage

1. Run the generator with your input document:

```bash
uv run main.py sample.md
```

2. Find your generated outputs in the `mindmap_outputs` directory:
   - `{filename}_mindmap__{provider}.txt` - Mermaid syntax
   - `{filename}_mindmap__{provider}.html` - Interactive HTML visualization
   - `{filename}_mindmap_outline__{provider}.md` - Markdown outline

## Cross-Provider Comparison

### OpenAI (GPT-4o-mini)

GPT-4o-mini excels at producing compact, efficient mindmaps that capture essential concepts without redundancy. Its output is characterized by clear categorization and precise language.

### Anthropic (Claude)

Claude's approach tends to include more nuanced historical context and captures subtle relationships between concepts. Its output is particularly strong in preserving the memo's analytical reasoning.

### DeepSeek

DeepSeek's output is notable for its thoroughness and depth of analysis. It extracts more subtleties from the document but occasionally at the cost of some redundancy.

### Google Gemini

Gemini's approach focuses on thematic coherence, with particularly strong extraction of geopolitical concepts and causal relationships between events.

### Key Observations from Cross-Provider Testing

This multi-provider approach reveals interesting patterns:

1. **Content Organization Differences**: Each provider structures the document's concepts differently, revealing their unique approaches to conceptual organization
2. **Detail Granularity Variance**: The level of detail varies significantly, with DeepSeek providing the most comprehensive extraction and OpenAI the most concise
3. **Emoji Selection Patterns**: Each model has distinct tendencies in selecting representative emojis for concepts
4. **Historical Context Sensitivity**: Models differ in how they handle historical context, with Claude showing particular strength in preserving historical nuance
5. **Structured Knowledge Representation**: The differences highlight various approaches to knowledge organization from the different AI research teams

The sample outputs serve as both demonstration of the tool's capabilities and an interesting comparative study of how different LLM providers approach the same complex historical document.

## 🔍 How It Works: The Architecture

Unlike traditional LLM applications that operate linearly, the Mindmap Generator employs a sophisticated, non-linear architecture that resembles an undirected graph of exploration. Here's an in-depth look at how the system works:

### 📊 The Non-Linear Exploration Model

Traditional LLM applications typically follow a simple pattern:

```
Input → LLM Prompt → Output
```

Or perhaps a pipeline:

```
Input → LLM Prompt 1 → Output 1 → LLM Prompt 2 → Output 2 → Final Result
```

The Mindmap Generator, however, operates as a multi-dimensional exploration system, where:

1. **Multiple parallel processes** explore different aspects of the document simultaneously
2. **Feedback loops** evaluate the quality and uniqueness of extracted information
3. **Heuristic-guided decisions** determine when to explore deeper or stop exploration
4. **Verification mechanisms** ensure factual accuracy throughout

This approach allows the system to efficiently navigate the vast conceptual space of the document while maintaining coherence and accuracy.

### 🧩 Document Type Detection System

The system begins by analyzing a sample of the document to determine its fundamental type, which guides subsequent extraction strategies:

- **Technical documents** focus on system components, interfaces, and implementations
- **Scientific documents** emphasize research methodologies, results, and theoretical frameworks
- **Narrative documents** highlight plot elements, character development, and thematic elements
- **Business documents** extract strategic initiatives, market opportunities, and implementation plans
- **Legal documents** identify legal principles, rights, obligations, and procedural requirements
- **Academic documents** focus on theoretical frameworks, scholarly arguments, and evidence
- **Instructional documents** extract learning objectives, skill development, and assessment methods

Each document type has specialized prompt templates optimized for extracting the most relevant information. Rather than a simple classification, the system uses specific detection heuristics that identify key indicators of document structure and purpose.

### 🌐 Intelligent Chunking System

A key innovation is how the system handles large documents:

1. **Overlapping Chunk Creation**: Documents are divided into manageable chunks with deliberate overlap to preserve context at boundaries
2. **Boundary Optimization**: Chunk boundaries are adjusted to coincide with natural breaks (e.g., end of sentences) rather than arbitrary character counts
3. **Context Preservation**: The overlap between chunks ensures that concepts that span chunk boundaries aren't fragmented
4. **Progressive Exploration**: Chunks are processed in a way that builds cumulative understanding of the document

This approach solves the fundamental limitation of LLM context windows while ensuring no important information is lost at chunk boundaries.

### 🎯 Topic Extraction Engine

The topic extraction process employs a sophisticated multi-stage approach:

1. **Parallel Initial Extraction**: Multiple chunks are analyzed simultaneously to identify potential topics
2. **Frequency Analysis**: Topics that appear across multiple chunks receive higher significance
3. **Consolidation Phase**: Similar topics are merged into cohesive, distinct concepts
4. **Semantic Deduplication**: Multiple similarity detection methods (including LLM-based semantic analysis) ensure topics are genuinely distinct
5. **Importance Ranking**: Topics are weighted based on document coverage, frequency, and semantic significance

This multi-phase approach ensures that the extracted topics provide balanced coverage of the document's content while avoiding redundancy or over-fragmentation.

### 🔄 Adaptive Exploration Strategy

The system employs an adaptive strategy that optimizes resource usage:

1. **Priority-Based Processing**: More important topics receive deeper exploration
2. **Diminishing Returns Detection**: The system recognizes when additional processing yields minimal new insights
3. **Breadth-Depth Balancing**: The exploration automatically adjusts between breadth (covering more topics) and depth (exploring topics in greater detail) based on document complexity
4. **Completion Thresholds**: Sophisticated heuristics determine when sufficient information has been extracted

This adaptive approach ensures that the system allocates computational resources efficiently, focusing effort where it will provide the most value.

### 🧠 Semantic Redundancy Detection

One of the most challenging aspects of mindmap generation is eliminating redundancy while preserving unique information. The system employs a multi-layered approach:

1. **Textual Similarity**: Basic string matching identifies obvious duplicates
2. **Fuzzy Matching**: Fuzzy string algorithms detect near-duplicate content with variations
3. **Token-Based Analysis**: Comparing token patterns identifies structural similarities
4. **LLM-Based Semantic Analysis**: For conceptually similar but textually different content, the system uses the LLM itself to evaluate semantic similarity
5. **Hierarchical Redundancy Checking**: Redundancy is checked within levels (e.g., between topics) and across levels (e.g., between a topic and a subtopic)

This comprehensive approach prevents the mindmap from containing repetitive information while ensuring nothing important is lost.

### 🔍 The Reality Check System

To prevent confabulation (the generation of factually incorrect information), the system implements a sophisticated verification mechanism:

1. **Content Verification**: Each generated node is compared against the source document to ensure it's either explicitly stated or logically derivable
2. **Confidence Scoring**: Verification results include confidence metrics that influence node inclusion
3. **Structural Preservation**: The system balances factual accuracy with maintaining a coherent mindmap structure
4. **Verification Statistics**: Detailed metrics track verification success rates across different node types

This reality check ensures that the mindmap remains a faithful representation of the source document, even when dealing with complex or abstract content.

### 🎨 Semantic Emoji Selection

The system enriches the visual representation of the mindmap through intelligent emoji selection:

1. **Context-Aware Selection**: Emojis are chosen based on the semantic content of each node
2. **Hierarchical Differentiation**: Different node types (topics, subtopics, details) use visually distinct emoji styles
3. **Importance Indicators**: Special markers indicate the importance level of details
4. **Persistent Caching**: Emoji selections are cached to ensure consistency across generations
5. **Fallback Hierarchy**: If optimal emoji selection fails, the system follows a thoughtful fallback strategy

This visual enhancement makes the mindmap more engaging and easier to navigate, with visual cues that communicate additional meaning.

## 🛠️ Technical Challenges and Solutions

### Preventing Cognitive Overload in Value-Priced LLMs

A significant challenge was making the system work effectively with more affordable LLM models:

- **Prompt Optimization**: Each prompt is carefully crafted to be concise yet comprehensive
- **Context Limitation**: The system deliberately limits context to prevent cognitive overload
- **Task Isolation**: Complex tasks are broken down into simpler, focused sub-tasks
- **Progressive Refinement**: Results are incrementally improved rather than attempting perfect outputs in one step
- **Error Recovery**: The system detects and handles cases where LLM outputs are inconsistent or low-quality

These strategies allow the system to leverage less expensive models while maintaining high-quality outputs.

### Asynchronous Processing Architecture

The system employs a sophisticated asynchronous architecture:

1. **Task Orchestration**: Complex dependency graphs manage the flow of tasks
2. **Semaphore-Based Rate Limiting**: Prevents overwhelming API rate limits
3. **Exponential Backoff with Jitter**: Intelligent retry logic for handling failures
4. **Cooperative Task Scheduling**: Efficient resource utilization across concurrent operations
5. **Dynamic Priority Adjustment**: More important tasks receive processing priority

This asynchronous design dramatically improves throughput while maintaining control over execution flow.

### Content Balance Heuristics

The system employs sophisticated heuristics to ensure balanced content extraction:

1. **Minimum Coverage Requirements**: Ensures sufficient breadth across the document
2. **Distribution Balancing**: Prevents over-representation of specific sections
3. **Hierarchical Proportion Control**: Maintains appropriate ratios between topics, subtopics, and details
4. **Importance-Weighted Selection**: More significant content receives greater representation
5. **Content Type Diversity**: Ensures a mix of conceptual, factual, and supporting information

These heuristics ensure that the final mindmap provides a balanced representation of the document's content.

### Error Recovery and Resilience

The system incorporates multiple layers of error handling:

1. **Graceful Degradation**: The system continues operating effectively even when some components fail
2. **Result Validation**: All LLM outputs are validated before being incorporated
3. **Fallback Strategies**: Alternative approaches are employed when primary methods fail
4. **State Preservation**: Intermediate results are cached to prevent lost work
5. **Comprehensive Logging**: Detailed error information facilitates debugging and improvement

This resilience ensures reliable operation even with unreliable LLM responses or API limitations.

## 📊 Performance Optimization and Cost Management

### Comprehensive Token Usage Tracking

The system implements detailed token usage tracking:

1. **Category-Based Tracking**: Usage is broken down by functional categories
2. **Cost Calculation**: Token counts are converted to cost estimates based on provider pricing
3. **Comparative Analysis**: Usage patterns are analyzed to identify optimization opportunities
4. **Trend Monitoring**: Usage patterns over time help identify shifts in performance

This tracking provides transparency and supports ongoing optimization efforts. You can see an example of what it looks like [here](https://github.com/Dicklesworthstone/mindmap-generator/raw/refs/heads/main/screenshots/token_usage_report.webp).

### Cost Efficiency Strategies

Several strategies minimize costs while maintaining output quality:

1. **Early Stopping**: Processing halts when sufficient quality is achieved
2. **Tiered Processing**: Less expensive models handle simpler tasks
3. **Caching**: Frequently used results are cached to prevent redundant API calls
4. **Content Batching**: Multiple items are processed in single API calls where possible
5. **Similarity Pre-filtering**: Cheaper computational methods filter candidates before expensive LLM-based comparisons

These strategies significantly reduce the total cost of generating comprehensive mindmaps.

### Performance Metrics and Dashboards

The system provides rich performance visualization:

1. **Color-Coded Progress**: Visual indicators show processing status at a glance
2. **Hierarchical Metrics**: Performance is tracked at multiple levels of granularity
3. **Completion Ratios**: Progress toward completion is continuously updated
4. **Cost Projections**: Running cost estimates provide financial transparency
5. **Quality Indicators**: Verification rates and confidence scores indicate output reliability

These visual tools make it easy to monitor long-running processes and understand system behavior.

## 📈 Advanced Functionality

### Incremental Improvement Cycles

The system can iteratively improve mindmaps through targeted refinement:

1. **Quality Assessment**: Existing mindmaps are evaluated for balance and coverage
2. **Targeted Enhancement**: Specific areas are identified for improvement
3. **Differential Processing**: Only areas requiring enhancement are reprocessed
4. **Consolidation**: New insights are integrated with existing content
5. **Before/After Comparison**: Changes are tracked to evaluate improvement

This approach allows efficient enhancement of existing mindmaps without complete regeneration.

### Multi-Provider Support

The system is designed to work with multiple LLM providers:

1. **Provider-Specific Optimization**: Prompt templates are tailored to each provider's strengths
2. **Unified Interface**: A consistent interface abstracts provider differences
3. **Dynamic Selection**: The optimal provider can be chosen based on task requirements
4. **Cost Balancing**: Tasks are allocated to minimize overall cost across providers
5. **Fallback Chains**: If one provider fails, the system can automatically retry with alternatives

This flexibility ensures the system remains viable as the LLM landscape evolves.

### Document Type-Specific Enhancement

Different document types receive specialized processing:

1. **Technical Documents**: Function diagrams and dependency mappings
2. **Scientific Documents**: Methodology flowcharts and result visualizations
3. **Narrative Documents**: Character relationship maps and plot progression
4. **Business Documents**: Strategic frameworks and implementation timelines
5. **Legal Documents**: Requirement hierarchies and procedural workflows

These specialized enhancements maximize the value of the generated mindmaps for different document types.

## 📝 Output Examples

### Mermaid Syntax
```
mindmap
    ((📄))
        ((🏛️ Constitutional Framework))
            (📜 Historical Context)
                [🔸 The memo begins by examining the historical context of constitutional interpretation]
                [🔹 References to the Federalist Papers and early American political thought]
                [🔸 Discussion of how the Constitution was designed to balance power]
            (⚖️ Separation of Powers)
                [♦️ Detailed analysis of the three branches of government and their distinct roles]
                [🔸 Examination of checks and balances between branches]
                [🔹 Historical examples of power struggles between branches]
```

### Markdown Outline
```markdown
# Constitutional Framework

## Historical Context
The memo begins by examining the historical context of constitutional interpretation
References to the Federalist Papers and early American political thought
Discussion of how the Constitution was designed to balance power

## Separation of Powers
Detailed analysis of the three branches of government and their distinct roles
Examination of checks and balances between branches
Historical examples of power struggles between branches
```

## 📚 Applications and Use Cases

The Mindmap Generator excels in various scenarios:

### Academic Research
- **Literature Review**: Quickly understand the key concepts and relationships in academic papers
- **Thesis Organization**: Structure complex research findings into coherent frameworks
- **Concept Mapping**: Visualize theoretical relationships across multiple sources

### Business Intelligence
- **Strategic Document Analysis**: Extract actionable insights from lengthy business reports
- **Competitive Research**: Organize information about market competitors
- **Policy Implementation**: Break down complex policies into implementable components

### Legal Analysis
- **Case Brief Creation**: Distill lengthy legal opinions into structured hierarchies
- **Regulatory Compliance**: Map complex regulatory requirements
- **Contract Review**: Identify key obligations and provisions in legal documents

### Educational Content
- **Curriculum Development**: Organize educational materials into logical learning paths
- **Study Guide Creation**: Generate comprehensive study guides from textbooks
- **Knowledge Mapping**: Create visual representations of subject matter domains

### Technical Documentation
- **Architecture Understanding**: Map complex technical systems
- **API Documentation**: Organize endpoint functionality into logical groupings
- **System Requirements**: Structure complex requirement documents

## 📜 License

MIT License

## 🔗 Related Work

If you find this project useful, you might also be interested in my [other open-source projects](https://github.com/Dicklesworthstone):

- [LLM Aided OCR](https://github.com/Dicklesworthstone/llm_aided_ocr)
- [Your Source to Prompt](https://github.com/Dicklesworthstone/your-source-to-prompt.html)
- [Swiss Army Llama](https://github.com/Dicklesworthstone/swiss_army_llama)
- [Fast Vector Similarity](https://github.com/Dicklesworthstone/fast_vector_similarity)
- [PPP Loan Fraud Analysis](https://github.com/Dicklesworthstone/ppp_loan_fraud_analysis)
