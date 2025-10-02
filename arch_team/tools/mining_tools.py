"""
Mining Tools for ChunkMiner Agent

Provides tools for document processing, chunking, and requirements extraction.
"""

import requests
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from autogen_core.tools import FunctionTool

API_BASE = os.environ.get("ARCH_TEAM_API_BASE", "http://localhost:8000")


def upload_and_mine_documents(
    files: List[str],
    model: str = "gpt-4o-mini",
    neighbor_refs: bool = True,
    chunk_size: int = 800,
    chunk_overlap: int = 200
) -> Dict[str, Any]:
    """
    Upload documents and extract requirements.

    Complete pipeline that handles file upload, chunking, and requirements extraction.

    Args:
        files: List of file paths to process
        model: LLM model to use for extraction (default: gpt-4o-mini)
        neighbor_refs: Include references to neighboring chunks (default: True)
        chunk_size: Maximum tokens per chunk (default: 800)
        chunk_overlap: Token overlap between chunks (default: 200)

    Returns:
        {
            "success": bool,
            "items": List[RequirementDTO],
            "count": int,
            "chunks_processed": int
        }

    Example:
        result = upload_and_mine_documents(
            files=["requirements.docx", "features.md"],
            chunk_size=800
        )
        # Returns: {"success": True, "items": [...], "count": 25}
    """
    if not files:
        return {"success": False, "error": "No files provided", "items": [], "count": 0}

    file_handles = []
    form_files = []

    try:
        # Open all files
        for file_path in files:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "items": [],
                    "count": 0
                }

            fh = open(file_path, 'rb')
            file_handles.append(fh)
            form_files.append(('files', (Path(file_path).name, fh, 'application/octet-stream')))

        # Build form data
        data = {
            "model": model,
            "neighbor_refs": "1" if neighbor_refs else "0",
            "chunk_size": str(chunk_size),
            "chunk_overlap": str(chunk_overlap)
        }

        # Call backend API
        response = requests.post(
            f"{API_BASE}/api/mining/upload",
            files=form_files,
            data=data,
            timeout=180  # 3 minutes for large documents
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}",
            "items": [],
            "count": 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "items": [],
            "count": 0
        }
    finally:
        # Clean up file handles
        for fh in file_handles:
            fh.close()


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Chunk text into smaller pieces.

    Useful for manual text chunking before requirements extraction.

    Args:
        text: Text to chunk
        chunk_size: Maximum tokens per chunk (default: 800)
        chunk_overlap: Token overlap between chunks (default: 200)

    Returns:
        List of text chunks

    Example:
        chunks = chunk_text(
            text="Long document text...",
            chunk_size=500
        )
        # Returns: ["chunk 1...", "chunk 2...", ...]
    """
    if not text or not text.strip():
        return []

    try:
        response = requests.post(
            f"{API_BASE}/api/mining/chunk",
            json={
                "text": text,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            },
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        return result.get("chunks", [])

    except requests.exceptions.RequestException as e:
        # Return error as single chunk for agent to handle
        return [f"ERROR: Chunking failed - {str(e)}"]
    except Exception as e:
        return [f"ERROR: Unexpected error during chunking - {str(e)}"]


def extract_requirements(
    text: str,
    model: str = "gpt-4o-mini"
) -> List[Dict[str, Any]]:
    """
    Extract requirements from text.

    Uses LLM to identify and extract requirements from unstructured text.

    Args:
        text: Text containing requirements (can be a chunk or full document)
        model: LLM model to use (default: gpt-4o-mini)

    Returns:
        List of requirement items

    Example:
        reqs = extract_requirements(
            text="System must authenticate users. API should be fast."
        )
        # Returns: [
        #   {"req_id": "REQ-1", "text": "System must authenticate users", ...},
        #   {"req_id": "REQ-2", "text": "API should be fast", ...}
        # ]
    """
    if not text or not text.strip():
        return []

    try:
        response = requests.post(
            f"{API_BASE}/api/mining/extract",
            json={
                "text": text,
                "model": model
            },
            timeout=90
        )
        response.raise_for_status()

        result = response.json()
        return result.get("items", [])

    except requests.exceptions.RequestException as e:
        # Return empty list with error info
        return [{
            "req_id": "ERROR",
            "text": f"Extraction failed: {str(e)}",
            "confidence": 0.0,
            "metadata": {"error": True}
        }]
    except Exception as e:
        return [{
            "req_id": "ERROR",
            "text": f"Unexpected error: {str(e)}",
            "confidence": 0.0,
            "metadata": {"error": True}
        }]


# Export as FunctionTools for AutoGen agents
mining_tools = [
    FunctionTool(
        upload_and_mine_documents,
        description="Upload documents and extract requirements using LLM. Returns list of RequirementDTO objects with IDs, text, source, and metadata."
    ),
    FunctionTool(
        chunk_text,
        description="Split text into smaller chunks with configurable size and overlap. Returns list of text chunks."
    ),
    FunctionTool(
        extract_requirements,
        description="Extract requirements from text using LLM. Returns list of requirement items with IDs and confidence scores."
    )
]


# For testing
if __name__ == "__main__":
    print("Mining Tools Module")
    print("===================")
    print(f"API Base: {API_BASE}")
    print(f"\nAvailable tools: {len(mining_tools)}")
    for tool in mining_tools:
        print(f"  - {tool._func.__name__}")
