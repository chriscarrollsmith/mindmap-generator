import os
import asyncio
import argparse
from mindmap_generator.utils import process_text_file
from mindmap_generator.config import get_logger

logger = get_logger()

async def main(input_file):
    try:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
            
        # Process the file
        logger.info(f"Generating mindmap for {input_file}")
        output_files = await process_text_file(input_file)
        
        # Print summary
        print("\nMindmap Generation Complete!")
        print("Generated files:")
        for filename in output_files:
            print(f"- {filename}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a mindmap from a text document')
    parser.add_argument('input_file', help='Path to the input document')
    args = parser.parse_args()
    
    asyncio.run(main(args.input_file))