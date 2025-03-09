from .utils import get_logger
from .models import DocumentType
from .llm_client import LLMClient
logger = get_logger(__name__)

class PromptStrategy:
    def __init__(self):
        self._initialize_prompts()
    
    def _initialize_prompts(self) -> None:
        """Initialize type-specific prompts from a configuration file or define them inline."""
        self.type_specific_prompts = {
            DocumentType.TECHNICAL: {
                'topics': """Analyze this technical document focusing on core system components and relationships.
                
    First, identify the major architectural or technical components that form complete, independent units of functionality.
    Each component should be:
    - A distinct technical system, module, or process
    - Independent enough to be understood on its own
    - Critical to the overall system functionality
    - Connected to at least one other component

    Avoid topics that are:
    - Too granular (implementation details)
    - Too broad (entire system categories)
    - Isolated features without system impact
    - Pure documentation elements

    Think about:
    1. What are the core building blocks?
    2. How do these pieces fit together?
    3. What dependencies exist between components?
    4. What are the key technical boundaries?

    Format: Return a JSON array of component names that represent the highest-level technical building blocks.""",

                'subtopics': """For the technical component '{topic}', identify its essential sub-components and interfaces.

    Each subtopic should:
    - Represent a crucial aspect of this component
    - Have clear technical responsibilities
    - Interface with other parts of the system
    - Contribute to the component's core purpose

    Consider:
    1. What interfaces does this component expose?
    2. What are its internal subsystems?
    3. How does it process data or handle requests?
    4. What services does it provide to other components?
    5. What technical standards or protocols does it implement?

    Format: Return a JSON array of technical subtopic names that form this component's architecture.""",

                'details': """For the technical subtopic '{subtopic}', identify specific implementation aspects and requirements.

    Focus on:
    1. Key algorithms or methods
    2. Data structures and formats
    3. Protocol specifications
    4. Performance characteristics
    5. Error handling approaches
    6. Security considerations
    7. Dependencies and requirements

    Include concrete technical details that are:
    - Implementation-specific
    - Measurable or testable
    - Critical for understanding
    - Relevant to integration

    Format: Return a JSON array of technical specifications and implementation details."""
            },

            DocumentType.SCIENTIFIC: {
                'topics': """Analyze this scientific document focusing on major research components and methodological frameworks.

    Identify main scientific themes that:
    - Represent complete experimental or theoretical units
    - Follow scientific method principles
    - Support the research objectives
    - Build on established scientific concepts

    Consider:
    1. What are the primary research questions?
    2. What methodological approaches are used?
    3. What theoretical frameworks are applied?
    4. What experimental designs are implemented?
    5. How do different research components interact?

    Avoid topics that are:
    - Too specific (individual measurements)
    - Too broad (entire fields of study)
    - Purely descriptive without scientific merit
    - Administrative or non-research elements

    Format: Return a JSON array of primary scientific themes or research components.""",

                'subtopics': """For the scientific theme '{topic}', identify key methodological elements and experimental components.

    Each subtopic should:
    - Represent a distinct experimental or analytical approach
    - Contribute to scientific rigor
    - Support reproducibility
    - Connect to research objectives

    Consider:
    1. What specific methods were employed?
    2. What variables were measured?
    3. What controls were implemented?
    4. What analytical techniques were used?
    5. How were data validated?

    Format: Return a JSON array of scientific subtopics that detail the research methodology.""",

                'details': """For the scientific subtopic '{subtopic}', extract specific experimental parameters and results.

    Focus on:
    1. Measurement specifications
    2. Statistical analyses
    3. Data collection procedures
    4. Validation methods
    5. Error margins
    6. Equipment specifications
    7. Environmental conditions

    Include details that are:
    - Quantifiable
    - Reproducible
    - Statistically relevant
    - Methodologically important

    Format: Return a JSON array of specific scientific parameters and findings."""
            },
            
            DocumentType.NARRATIVE: {
            'topics': """Analyze this narrative document focusing on storytelling elements and plot development.

    Identify major narrative components that:
    - Represent complete story arcs or plot elements
    - Form essential narrative structures
    - Establish key story developments
    - Connect to the overall narrative flow

    Consider:
    1. What are the primary plot points?
    2. What character arcs are developed?
    3. What themes are explored?
    4. What settings are established?
    5. How do different narrative elements interweave?

    Avoid topics that are:
    - Too specific (individual scenes)
    - Too broad (entire genres)
    - Purely stylistic elements
    - Non-narrative content

    Format: Return a JSON array of primary narrative themes or story elements.""",

            'subtopics': """For the narrative theme '{topic}', identify key story elements and developments.

    Each subtopic should:
    - Represent a distinct narrative aspect
    - Support story progression
    - Connect to character development
    - Contribute to theme exploration

    Consider:
    1. What specific plot developments occur?
    2. What character interactions take place?
    3. What conflicts are presented?
    4. What thematic elements are developed?
    5. What setting details are important?

    Format: Return a JSON array of narrative subtopics that detail story components.""",

            'details': """For the narrative subtopic '{subtopic}', extract specific story details and elements.

    Focus on:
    1. Scene descriptions
    2. Character motivations
    3. Dialogue highlights
    4. Setting details
    5. Symbolic elements
    6. Emotional moments
    7. Plot connections

    Include details that are:
    - Story-advancing
    - Character-developing
    - Theme-supporting
    - Atmosphere-building

    Format: Return a JSON array of specific narrative details and elements."""
        },
        
            DocumentType.BUSINESS: {
            'topics': """Analyze this business document focusing on strategic initiatives and market opportunities.

    Identify major business components that:
    - Represent complete business strategies
    - Form essential market approaches
    - Establish key business objectives
    - Connect to organizational goals

    Consider:
    1. What are the primary business objectives?
    2. What market opportunities are targeted?
    3. What strategic initiatives are proposed?
    4. What organizational capabilities are required?
    5. How do different business elements align?

    Avoid topics that are:
    - Too specific (individual tactics)
    - Too broad (entire industries)
    - Administrative elements
    - Non-strategic content

    Format: Return a JSON array of primary business themes or strategic elements.""",

            'subtopics': """For the business theme '{topic}', identify key strategic elements and approaches.

    Each subtopic should:
    - Represent a distinct business aspect
    - Support strategic objectives
    - Connect to market opportunities
    - Contribute to business growth

    Consider:
    1. What specific strategies are proposed?
    2. What market segments are targeted?
    3. What resources are required?
    4. What competitive advantages exist?
    5. What implementation steps are needed?

    Format: Return a JSON array of business subtopics that detail strategic components.""",

            'details': """For the business subtopic '{subtopic}', extract specific strategic details and requirements.

    Focus on:
    1. Market metrics
    2. Financial projections
    3. Resource requirements
    4. Implementation timelines
    5. Success metrics
    6. Risk factors
    7. Growth opportunities

    Include details that are:
    - Measurable
    - Action-oriented
    - Resource-specific
    - Market-focused

    Format: Return a JSON array of specific business details and requirements."""
        },            

            DocumentType.ANALYTICAL: {
                'topics': """Analyze this analytical document focusing on key insights and data patterns.

    Identify major analytical themes that:
    - Represent complete analytical frameworks
    - Reveal significant patterns or trends
    - Support evidence-based conclusions
    - Connect different aspects of analysis

    Consider:
    1. What are the primary analytical questions?
    2. What major patterns emerge from the data?
    3. What key metrics drive the analysis?
    4. How do different analytical components relate?
    5. What are the main areas of investigation?

    Avoid topics that are:
    - Too granular (individual data points)
    - Too broad (entire analytical fields)
    - Purely descriptive without analytical value
    - Administrative or non-analytical elements

    Format: Return a JSON array of primary analytical themes or frameworks.""",

                'subtopics': """For the analytical theme '{topic}', identify key metrics and analytical approaches.

    Each subtopic should:
    - Represent a distinct analytical method or metric
    - Contribute to understanding patterns
    - Support data-driven insights
    - Connect to analytical objectives

    Consider:
    1. What specific analyses were performed?
    2. What metrics were calculated?
    3. What statistical approaches were used?
    4. What patterns were investigated?
    5. How were conclusions validated?

    Format: Return a JSON array of analytical subtopics that detail the investigation methods.""",

                'details': """For the analytical subtopic '{subtopic}', extract specific findings and supporting evidence.

    Focus on:
    1. Statistical results
    2. Trend analyses
    3. Correlation findings
    4. Significance measures
    5. Confidence intervals
    6. Data quality metrics
    7. Validation results

    Include details that are:
    - Quantifiable
    - Statistically significant
    - Evidence-based
    - Methodologically sound

    Format: Return a JSON array of specific analytical findings and metrics."""
            },
            DocumentType.LEGAL: {
                'topics': """Analyze this legal document focusing on key legal principles and frameworks.

    Identify major legal components that:
    - Represent complete legal concepts or arguments
    - Form foundational legal principles
    - Establish key rights, obligations, or requirements
    - Connect to relevant legal frameworks

    Consider:
    1. What are the primary legal issues or questions?
    2. What statutory frameworks apply?
    3. What precedential cases are relevant?
    4. What legal rights and obligations are established?
    5. How do different legal concepts interact?

    Avoid topics that are:
    - Too specific (individual clauses)
    - Too broad (entire bodies of law)
    - Administrative or non-legal elements
    - Purely formatting sections

    Format: Return a JSON array of primary legal themes or frameworks.""",

                'subtopics': """For the legal theme '{topic}', identify key legal elements and requirements.

    Each subtopic should:
    - Represent a distinct legal requirement or concept
    - Support legal compliance or enforcement
    - Connect to statutory or case law
    - Contribute to legal understanding

    Consider:
    1. What specific obligations arise?
    2. What rights are established?
    3. What procedures are required?
    4. What legal tests or standards apply?
    5. What exceptions or limitations exist?

    Format: Return a JSON array of legal subtopics that detail requirements and obligations.""",

                'details': """For the legal subtopic '{subtopic}', extract specific legal provisions and requirements.

    Focus on:
    1. Specific statutory references
    2. Case law citations
    3. Compliance requirements
    4. Procedural steps
    5. Legal deadlines
    6. Jurisdictional requirements
    7. Enforcement mechanisms

    Include details that are:
    - Legally binding
    - Procedurally important
    - Compliance-critical
    - Precedent-based

    Format: Return a JSON array of specific legal provisions and requirements."""
            },
            DocumentType.MEDICAL: {
                'topics': """Analyze this medical document focusing on key clinical concepts and patient care aspects.

    Identify major medical components that:
    - Represent complete clinical concepts
    - Form essential diagnostic or treatment frameworks
    - Establish key medical protocols
    - Connect to standard medical practices

    Consider:
    1. What are the primary medical conditions or issues?
    2. What treatment approaches are discussed?
    3. What diagnostic frameworks apply?
    4. What clinical outcomes are measured?
    5. How do different medical aspects interact?

    Avoid topics that are:
    - Too specific (individual symptoms)
    - Too broad (entire medical fields)
    - Administrative elements
    - Non-clinical content

    Format: Return a JSON array of primary medical themes or clinical concepts.""",

                'subtopics': """For the medical theme '{topic}', identify key clinical elements and protocols.

    Each subtopic should:
    - Represent a distinct clinical aspect
    - Support patient care decisions
    - Connect to medical evidence
    - Contribute to treatment planning

    Consider:
    1. What specific treatments are indicated?
    2. What diagnostic criteria apply?
    3. What monitoring is required?
    4. What contraindications exist?
    5. What patient factors are relevant?

    Format: Return a JSON array of medical subtopics that detail clinical approaches.""",

                'details': """For the medical subtopic '{subtopic}', extract specific clinical guidelines and parameters.

    Focus on:
    1. Dosage specifications
    2. Treatment protocols
    3. Monitoring requirements
    4. Clinical indicators
    5. Risk factors
    6. Side effects
    7. Follow-up procedures

    Include details that are:
    - Clinically relevant
    - Evidence-based
    - Treatment-specific
    - Patient-focused

    Format: Return a JSON array of specific medical parameters and guidelines."""
            },

            DocumentType.INSTRUCTIONAL: {
                'topics': """Analyze this instructional document focusing on key learning objectives and educational frameworks.

    Identify major instructional components that:
    - Represent complete learning units
    - Form coherent educational modules
    - Establish key competencies
    - Connect to learning outcomes

    Consider:
    1. What are the primary learning objectives?
    2. What skill sets are being developed?
    3. What knowledge areas are covered?
    4. What pedagogical approaches are used?
    5. How do different learning components build on each other?

    Avoid topics that are:
    - Too specific (individual facts)
    - Too broad (entire subjects)
    - Administrative elements
    - Non-educational content

    Format: Return a JSON array of primary instructional themes or learning modules.""",

                'subtopics': """For the instructional theme '{topic}', identify key learning elements and approaches.

    Each subtopic should:
    - Represent a distinct learning component
    - Support skill development
    - Connect to learning objectives
    - Contribute to competency building

    Consider:
    1. What specific skills are taught?
    2. What concepts are introduced?
    3. What practice activities are included?
    4. What assessment methods are used?
    5. What prerequisites are needed?

    Format: Return a JSON array of instructional subtopics that detail learning components.""",

                'details': """For the instructional subtopic '{subtopic}', extract specific learning activities and resources.

    Focus on:
    1. Practice exercises
    2. Examples and illustrations
    3. Assessment criteria
    4. Learning resources
    5. Key definitions
    6. Common mistakes
    7. Success indicators

    Include details that are:
    - Skill-building
    - Practice-oriented
    - Assessment-ready
    - Learning-focused

    Format: Return a JSON array of specific instructional elements and activities."""
            },

            DocumentType.ACADEMIC: {
                'topics': """Analyze this academic document focusing on scholarly arguments and theoretical frameworks.

    Identify major academic components that:
    - Represent complete theoretical concepts
    - Form scholarly arguments
    - Establish key academic positions
    - Connect to existing literature

    Consider:
    1. What are the primary theoretical frameworks?
    2. What scholarly debates are addressed?
    3. What research questions are explored?
    4. What methodological approaches are used?
    5. How do different theoretical elements interact?

    Avoid topics that are:
    - Too specific (individual citations)
    - Too broad (entire fields)
    - Administrative elements
    - Non-scholarly content

    Format: Return a JSON array of primary academic themes or theoretical frameworks.""",

                'subtopics': """For the academic theme '{topic}', identify key theoretical elements and arguments.

    Each subtopic should:
    - Represent a distinct theoretical aspect
    - Support scholarly analysis
    - Connect to literature
    - Contribute to academic discourse

    Consider:
    1. What specific arguments are made?
    2. What evidence is presented?
    3. What theoretical models apply?
    4. What counterarguments exist?
    5. What methodological approaches are used?

    Format: Return a JSON array of academic subtopics that detail theoretical components.""",

                'details': """For the academic subtopic '{subtopic}', extract specific scholarly evidence and arguments.

    Focus on:
    1. Research findings
    2. Theoretical implications
    3. Methodological details
    4. Literature connections
    5. Critical analyses
    6. Supporting evidence
    7. Scholarly debates

    Include details that are:
    - Theoretically relevant
    - Evidence-based
    - Methodologically sound
    - Literature-connected

    Format: Return a JSON array of specific academic elements and arguments."""
            },

            DocumentType.PROCEDURAL: {
                'topics': """Analyze this procedural document focusing on systematic processes and workflows.

    Identify major procedural components that:
    - Represent complete process units
    - Form coherent workflow stages
    - Establish key procedures
    - Connect to overall process flow

    Consider:
    1. What are the primary process phases?
    2. What workflow sequences exist?
    3. What critical paths are defined?
    4. What decision points occur?
    5. How do different process elements connect?

    Avoid topics that are:
    - Too specific (individual actions)
    - Too broad (entire systems)
    - Administrative elements
    - Non-procedural content

    Format: Return a JSON array of primary procedural themes or process phases.""",

                'subtopics': """For the procedural theme '{topic}', identify key process elements and requirements.

    Each subtopic should:
    - Represent a distinct process step
    - Support workflow progression
    - Connect to other steps
    - Contribute to process completion

    Consider:
    1. What specific steps are required?
    2. What inputs are needed?
    3. What outputs are produced?
    4. What conditions apply?
    5. What validations occur?

    Format: Return a JSON array of procedural subtopics that detail process steps.""",

                'details': """For the procedural subtopic '{subtopic}', extract specific step requirements and checks.

    Focus on:
    1. Step-by-step instructions
    2. Input requirements
    3. Quality checks
    4. Decision criteria
    5. Exception handling
    6. Success criteria
    7. Completion indicators

    Include details that are:
    - Action-oriented
    - Sequence-specific
    - Quality-focused
    - Process-critical

    Format: Return a JSON array of specific procedural steps and requirements."""
            },
                
            DocumentType.GENERAL: {
            'topics': """Analyze this document focusing on main conceptual themes and relationships.

    Identify major themes that:
    - Represent complete, independent ideas
    - Form logical groupings of related concepts
    - Support the document's main purpose
    - Connect to other important themes

    Consider:
    1. What are the fundamental ideas being presented?
    2. How do these ideas relate to each other?
    3. What are the key areas of focus?
    4. How is the information structured?

    Avoid topics that are:
    - Too specific (individual examples)
    - Too broad (entire subject areas)
    - Isolated facts without context
    - Purely formatting elements

    Format: Return a JSON array of primary themes or concept areas.""",

                'subtopics': """For the theme '{topic}', identify key supporting concepts and related ideas.

    Each subtopic should:
    - Represent a distinct aspect of the main theme
    - Provide meaningful context
    - Support understanding
    - Connect to the overall narrative

    Consider:
    1. What are the main points about this theme?
    2. What examples illustrate it?
    3. What evidence supports it?
    4. How does it develop through the document?

    Format: Return a JSON array of subtopics that develop this theme.""",

                'details': """For the subtopic '{subtopic}', extract specific supporting information and examples.

    Focus on:
    1. Concrete examples
    2. Supporting evidence
    3. Key definitions
    4. Important relationships
    5. Specific applications
    6. Notable implications
    7. Clarifying points

    Include details that:
    - Illustrate the concept
    - Provide evidence
    - Aid understanding
    - Connect to larger themes

    Format: Return a JSON array of specific supporting details and examples."""
            }
        }
        # Add default prompts for any missing document types
        for doc_type in DocumentType:
            if doc_type not in self.type_specific_prompts:
                self.type_specific_prompts[doc_type] = self.type_specific_prompts[DocumentType.GENERAL]
    
    async def detect_document_type(self, content: str, request_id: str, client: LLMClient) -> DocumentType:
        """Use LLM to detect document type with sophisticated analysis."""
        summary_content = content[:self.config['max_summary_length']]
        prompt = f"""You are analyzing a document to determine its primary type and structure. This document requires the most appropriate conceptual organization strategy.

    Key characteristics of each document type:

    TECHNICAL
    - Contains system specifications, API documentation, or implementation details
    - Focuses on HOW things work and technical implementation
    - Uses technical terminology, code examples, or system diagrams
    - Structured around components, modules, or technical processes
    Example indicators: API endpoints, code blocks, system requirements, technical specifications

    SCIENTIFIC
    - Presents research findings, experimental data, or scientific theories
    - Follows scientific method with hypotheses, methods, results
    - Contains statistical analysis or experimental procedures
    - References prior research or scientific literature
    Example indicators: methodology sections, statistical results, citations, experimental procedures

    NARRATIVE
    - Tells a story or presents events in sequence
    - Has character development or plot progression
    - Uses descriptive language and scene-setting
    - Organized chronologically or by story elements
    Example indicators: character descriptions, plot developments, narrative flow, dialogue

    BUSINESS
    - Focuses on business operations, strategy, or market analysis
    - Contains financial data or business metrics
    - Addresses organizational or market challenges
    - Includes business recommendations or action items
    Example indicators: market analysis, financial projections, strategic plans, ROI calculations

    ACADEMIC
    - Centers on scholarly research and theoretical frameworks
    - Engages with academic literature and existing theories
    - Develops theoretical arguments or conceptual models
    - Contributes to academic discourse in a field
    Example indicators: literature reviews, theoretical frameworks, scholarly arguments, academic citations

    LEGAL
    - Focuses on laws, regulations, or legal requirements
    - Contains legal terminology and formal language
    - References statutes, cases, or legal precedents
    - Addresses rights, obligations, or compliance
    Example indicators: legal citations, compliance requirements, jurisdictional references, statutory language

    MEDICAL
    - Centers on clinical care, diagnoses, or treatments
    - Uses medical terminology and protocols
    - Addresses patient care or health outcomes
    - Follows clinical guidelines or standards
    Example indicators: diagnostic criteria, treatment protocols, clinical outcomes, medical terminology

    INSTRUCTIONAL
    - Focuses on teaching or skill development
    - Contains learning objectives and outcomes
    - Includes exercises or practice activities
    - Structured for progressive learning
    Example indicators: learning objectives, practice exercises, assessment criteria, skill development

    ANALYTICAL
    - Presents data analysis or systematic examination
    - Contains trends, patterns, or correlations
    - Uses analytical frameworks or methodologies
    - Focuses on drawing conclusions from data
    Example indicators: data trends, analytical methods, pattern analysis, statistical insights

    PROCEDURAL
    - Provides step-by-step instructions or processes
    - Focuses on HOW to accomplish specific tasks
    - Contains clear sequential steps or workflows
    - Emphasizes proper order and procedures
    Example indicators: numbered steps, workflow diagrams, sequential instructions

    GENERAL
    - Contains broad or mixed content types
    - No strong alignment with other categories
    - Covers multiple topics or approaches
    - Uses general language and structure
    Example indicators: mixed content types, general descriptions, broad overviews, diverse topics

    Key Differentiators:

    1. TECHNICAL vs PROCEDURAL:
    - Technical focuses on system components and how they work
    - Procedural focuses on steps to accomplish tasks

    2. SCIENTIFIC vs ACADEMIC:
    - Scientific focuses on experimental methods and results
    - Academic focuses on theoretical frameworks and scholarly discourse

    3. ANALYTICAL vs SCIENTIFIC:
    - Analytical focuses on data patterns and insights
    - Scientific focuses on experimental validation of hypotheses

    4. INSTRUCTIONAL vs PROCEDURAL:
    - Instructional focuses on learning and skill development
    - Procedural focuses on task completion steps

    5. MEDICAL vs SCIENTIFIC:
    - Medical focuses on clinical care and treatment
    - Scientific focuses on research methodology

    Return ONLY the category name that best matches the document's structure and purpose.

    Document excerpt:
    {summary_content}"""
        try:
            response = await client._retry_generate_completion(
                prompt,
                max_tokens=50,
                request_id=request_id,
                task="detecting_document_type"
            )
            return DocumentType.from_str(response.strip().lower())
        except Exception as e:
            logger.error(f"Error detecting document type: {str(e)}", extra={"request_id": request_id})
            return DocumentType.GENERAL