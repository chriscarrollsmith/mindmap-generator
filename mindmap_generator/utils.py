import os
import json
import zlib
import base64
from typing import Tuple
from datetime import datetime
import aiofiles
import hashlib
from .mindmap_generator import MindMapGenerator
from .models import MinimalDatabaseStub, initialize_db
from .config import Config, get_logger

logger = get_logger()

def generate_mermaid_html(mermaid_code):
    # Remove leading/trailing triple backticks if present
    mermaid_code = mermaid_code.strip()
    if mermaid_code.startswith('```') and mermaid_code.endswith('```'):
        mermaid_code = mermaid_code[3:-3].strip()
    # Create the data object to be encoded
    data = {
        "code": mermaid_code,
        "mermaid": {"theme": "default"}
    }
    json_string = json.dumps(data)
    compressed_data = zlib.compress(json_string.encode('utf-8'), level=9)
    base64_string = base64.urlsafe_b64encode(compressed_data).decode('utf-8').rstrip('=')
    edit_url = f'https://mermaid.live/edit#pako:{base64_string}'
    # Now generate the HTML template
    html_template = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Mermaid Mindmap</title>
  <!-- Tailwind CSS -->
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
  <!-- Mermaid JS -->
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.min.js"></script>
  <style>
    body {{
      margin: 0;
      padding: 0;
    }}
    #mermaid {{
      width: 100%;
      height: calc(100vh - 64px); /* Adjust height considering header */
      overflow: auto;
    }}
  </style>
</head>
<body class="bg-gray-100">
  <div class="flex items-center justify-between p-4 bg-white shadow">
    <h1 class="text-xl font-bold">Mermaid Mindmap</h1>
    <a href="{edit_url}" target="_blank" id="editButton" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">Edit in Mermaid Live Editor</a>
  </div>
  <div id="mermaid" class="p-4">
    <pre class="mermaid">
{mermaid_code}
    </pre>
  </div>
  <script>
    mermaid.initialize({{
      startOnLoad: true,
      securityLevel: 'loose',
      theme: 'default',
      mindmap: {{
        useMaxWidth: true
      }},
      themeConfig: {{
        controlBar: true
      }}
    }});
  </script>
</body>
</html>'''
    return html_template

async def generate_document_mindmap(document_id: str, request_id: str) -> Tuple[str, str]:
    """Generate both Mermaid mindmap and Markdown outline for a document.
    
    Args:
        document_id (str): The ID of the document to process
        request_id (str): Unique identifier for request tracking
        
    Returns:
        Tuple[str, str]: (mindmap_file_path, markdown_file_path)
    """
    try:
        generator = MindMapGenerator()
        db = await initialize_db()
        document = await db.get_document_by_id(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}", extra={"request_id": request_id})
            return "", ""

        # Define file paths for both formats
        mindmap_file_path = f"generated_mindmaps/{document['sanitized_filename']}_mermaid_mindmap__{Config.API_PROVIDER.lower()}.txt"
        mindmap_html_file_path = f"generated_mindmaps/{document['sanitized_filename']}_mindmap__{Config.API_PROVIDER.lower()}.html"
        markdown_file_path = f"generated_mindmaps/{document['sanitized_filename']}_mindmap_outline__{Config.API_PROVIDER.lower()}.md"
        
        # Check if both files already exist
        if os.path.exists(mindmap_file_path) and os.path.exists(markdown_file_path):
            logger.info(f"Both mindmap and markdown already exist for document {document_id}. Reusing existing files.", extra={"request_id": request_id})
            return mindmap_file_path, markdown_file_path

        optimized_text = await db.get_optimized_text(document_id, request_id)
        if not optimized_text:
            logger.error(f"Optimized text not found for document: {document_id}", extra={"request_id": request_id})
            return "", ""

        # Generate mindmap
        mermaid_syntax = await generator.generate_mindmap(optimized_text, request_id)
        
        # Convert to HTML
        mermaid_html = generate_mermaid_html(mermaid_syntax)
        
        # Convert to markdown
        markdown_outline = generator._convert_mindmap_to_markdown(mermaid_syntax)

        # Save all 3 formats
        os.makedirs(os.path.dirname(mindmap_file_path), exist_ok=True)
        
        async with aiofiles.open(mindmap_file_path, 'w', encoding='utf-8') as f:
            await f.write(mermaid_syntax)
            
        async with aiofiles.open(mindmap_html_file_path, 'w', encoding='utf-8') as f:
            await f.write(mermaid_html)
            
        async with aiofiles.open(markdown_file_path, 'w', encoding='utf-8') as f:
            await f.write(markdown_outline)

        logger.info(f"Mindmap and associated html/markdown generated successfully for document {document_id}", extra={"request_id": request_id})
        return mindmap_file_path, mindmap_html_file_path, markdown_file_path
        
    except Exception as e:
        logger.error(f"Error generating mindmap and associated html/markdown for document {document_id}: {str(e)}", extra={"request_id": request_id})
        return "", ""

async def process_text_file(filepath: str):
    """Process a single text file and generate mindmap outputs."""
    logger = get_logger()
    try:
        # Read the input file
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Store content in our stub database
        MinimalDatabaseStub.store_text(content)
        # Generate a unique document ID based on content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = os.path.splitext(os.path.basename(filepath))[0]
        document_id = f"{base_filename}_{content_hash}_{timestamp}"
        # Initialize the mindmap generator
        generator = MindMapGenerator()
        # Generate the mindmap
        mindmap = await generator.generate_mindmap(content, request_id=document_id)
        # Generate HTML
        html = generate_mermaid_html(mindmap)
        # Generate markdown outline
        markdown_outline = generator._convert_mindmap_to_markdown(mindmap)
        # Create output directory if it doesn't exist
        os.makedirs("mindmap_outputs", exist_ok=True)
        # Save outputs with simple names based on input file
        output_files = {
            f"mindmap_outputs/{base_filename}_mindmap__{Config.API_PROVIDER.lower()}.txt": mindmap,
            f"mindmap_outputs/{base_filename}_mindmap__{Config.API_PROVIDER.lower()}.html": html,
            f"mindmap_outputs/{base_filename}_mindmap_outline__{Config.API_PROVIDER.lower()}.md": markdown_outline
        }
        # Save all outputs
        for filename, content in output_files.items():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
                logger.info(f"Saved {filename}")
        
        logger.info("Mindmap generation completed successfully!")
        return output_files
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise
    
