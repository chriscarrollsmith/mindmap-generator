from typing import Dict, Any, Optional
from enum import Enum, auto
from typing import List
from dataclasses import dataclass, field

class MinimalDatabaseStub:
    """Minimal database stub that provides just enough for the mindmap generator."""
    @staticmethod
    async def get_document_by_id(document_id: str) -> Dict[str, Any]:
        """Stub that returns minimal document info."""
        return {
            "id": document_id,
            "original_file_name": f"document_{document_id}.txt",
            "sanitized_filename": document_id,
            "status": "processing",
            "progress_percentage": 0
        }
        
    @staticmethod
    async def get_optimized_text(document_id: str, request_id: str) -> Optional[str]:
        """In our simplified version, this just returns the raw text content."""
        return MinimalDatabaseStub._stored_text
        
    @staticmethod
    async def update_document_status(*args, **kwargs) -> Dict[str, Any]:
        """Stub that just returns success."""
        return {"status": "success"}
        
    @staticmethod
    async def add_token_usage(*args, **kwargs) -> None:
        """Stub that does nothing."""
        pass

    # Add a way to store the text content
    _stored_text = ""
    
    @classmethod
    def store_text(cls, text: str):
        """Store text content for later retrieval."""
        cls._stored_text = text

async def initialize_db():
    """Minimal DB initialization that just returns our stub."""
    return MinimalDatabaseStub()

class DocumentType(Enum):
    """Enumeration of supported document types."""
    TECHNICAL = auto()
    SCIENTIFIC = auto()
    NARRATIVE = auto()
    BUSINESS = auto()
    ACADEMIC = auto()
    LEGAL = auto()      
    MEDICAL = auto()    
    INSTRUCTIONAL = auto() 
    ANALYTICAL = auto() 
    PROCEDURAL = auto() 
    GENERAL = auto()

    @classmethod
    def from_str(cls, value: str) -> 'DocumentType':
        """Convert string to DocumentType enum."""
        try:
            return cls[value.upper()]
        except KeyError:
            return cls.GENERAL

class NodeShape(Enum):
    """Enumeration of node shapes for the mindmap structure."""
    ROOT = '(())'        # Double circle for root node (📄)
    TOPIC = '(())'       # Double circle for main topics
    SUBTOPIC = '()'      # Single circle for subtopics
    DETAIL = '[]'        # Square brackets for details

    def apply(self, text: str) -> str:
        """Apply the shape to the text."""
        return {
            self.ROOT: f"(({text}))",
            self.TOPIC: f"(({text}))",
            self.SUBTOPIC: f"({text})",
            self.DETAIL: f"[{text}]"
        }[self]


class ContentItem:
    """Class to track content items with their context information."""
    def __init__(self, text: str, path: List[str], node_type: str, importance: str = None):
        self.text = text
        self.path = path
        self.path_str = ' → '.join(path)
        self.node_type = node_type
        self.importance = importance
        
    def __str__(self):
        return f"{self.text} ({self.node_type} at {self.path_str})"

@dataclass
class MindmapNode:
    """Represents a node in the mindmap."""
    name: str
    importance: str = 'medium'
    emoji: str = ""
    subtopics: List['MindmapNode'] = field(default_factory=list)
    details: List[Dict[str, str]] = field(default_factory=list)  # Keep details as dicts for now

@dataclass
class MindmapData:
    """Represents the entire mindmap."""
    central_theme: MindmapNode