"""
RAG Tools for RAGAgent

Provides tools for semantic search, duplicate detection, and relationship discovery.
"""

import requests
import os
from typing import List, Dict, Any, Optional
from autogen_core.tools import FunctionTool

API_BASE = os.environ.get("ARCH_TEAM_API_BASE", "http://localhost:8000")


def find_duplicates(
    requirements: List[Dict[str, Any]],
    similarity_threshold: float = 0.90,
    method: str = "embedding"
) -> Dict[str, Any]:
    """
    Find semantic duplicate requirements.

    Uses vector embeddings to identify requirements that are semantically similar,
    which likely represent duplicates.

    Args:
        requirements: List of requirement objects with text field
        similarity_threshold: Minimum similarity score (0-1) to consider as duplicate (default: 0.90)
        method: Detection method - 'embedding' or 'fuzzy' (default: 'embedding')

    Returns:
        {
            "success": bool,
            "duplicate_groups": [
                {
                    "group_id": str,
                    "requirements": [
                        {"req_id": str, "text": str, "similarity": float},
                        ...
                    ],
                    "avg_similarity": float
                },
                ...
            ],
            "stats": {
                "total_requirements": int,
                "unique_requirements": int,
                "duplicate_groups": int,
                "total_duplicates": int
            }
        }

    Example:
        result = find_duplicates(
            requirements=[
                {"req_id": "REQ-001", "text": "System must authenticate users"},
                {"req_id": "REQ-005", "text": "User authentication is required"}
            ],
            similarity_threshold=0.90
        )
        # Returns: {
        #   "duplicate_groups": [
        #     {
        #       "group_id": "dup_1",
        #       "requirements": [
        #         {"req_id": "REQ-001", "text": "...", "similarity": 1.0},
        #         {"req_id": "REQ-005", "text": "...", "similarity": 0.94}
        #       ]
        #     }
        #   ]
        # }
    """
    if not requirements:
        return {
            "success": False,
            "error": "No requirements provided",
            "duplicate_groups": [],
            "stats": {"total_requirements": 0, "unique_requirements": 0}
        }

    try:
        response = requests.post(
            f"{API_BASE}/api/rag/duplicates",
            json={
                "requirements": requirements,
                "similarity_threshold": similarity_threshold,
                "method": method
            },
            timeout=120
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}",
            "duplicate_groups": [],
            "stats": {"total_requirements": len(requirements), "unique_requirements": len(requirements)}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "duplicate_groups": [],
            "stats": {"total_requirements": len(requirements), "unique_requirements": len(requirements)}
        }


def semantic_search_requirements(
    query_text: str,
    requirements: Optional[List[Dict[str, Any]]] = None,
    top_k: int = 10,
    min_score: float = 0.7,
    use_qdrant: bool = True
) -> List[Dict[str, Any]]:
    """
    Semantic search for requirements similar to query.

    Find requirements that are semantically similar to a given query text.
    Can search in provided list or in Qdrant vector store.

    Args:
        query_text: Natural language search query
        requirements: Optional list to search in (if None, searches Qdrant)
        top_k: Number of results to return (default: 10)
        min_score: Minimum similarity score (default: 0.7)
        use_qdrant: Search in Qdrant if requirements not provided (default: True)

    Returns:
        List of matching requirements:
        [
            {
                "req_id": str,
                "text": str,
                "score": float,
                "source": str,
                "metadata": Dict
            },
            ...
        ]

    Example:
        results = semantic_search_requirements(
            query_text="authentication and security",
            top_k=5
        )
        # Returns: [
        #   {"req_id": "REQ-001", "text": "System must authenticate users", "score": 0.92, ...},
        #   {"req_id": "REQ-008", "text": "Security protocols required", "score": 0.85, ...}
        # ]
    """
    if not query_text or not query_text.strip():
        return []

    try:
        response = requests.post(
            f"{API_BASE}/api/rag/search",
            json={
                "query": query_text,
                "requirements": requirements,
                "top_k": top_k,
                "min_score": min_score,
                "use_qdrant": use_qdrant
            },
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        return result.get("results", [])

    except requests.exceptions.RequestException as e:
        return [{
            "req_id": "ERROR",
            "text": f"Search failed: {str(e)}",
            "score": 0.0,
            "metadata": {"error": True}
        }]
    except Exception as e:
        return [{
            "req_id": "ERROR",
            "text": f"Unexpected error: {str(e)}",
            "score": 0.0,
            "metadata": {"error": True}
        }]


def get_related_requirements(
    requirement_id: str,
    requirements: List[Dict[str, Any]],
    top_k: int = 5,
    relationship_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Find requirements related to a specific requirement.

    Discover relationships like dependencies, conflicts, or semantic similarity.

    Args:
        requirement_id: ID of the requirement to find relations for
        requirements: List of all requirements to search in
        top_k: Number of related requirements to return (default: 5)
        relationship_types: Types to find - ['depends', 'conflicts', 'similar', 'implements']
                           If None, finds all types (default: None)

    Returns:
        List of related requirements:
        [
            {
                "req_id": str,
                "text": str,
                "relationship_type": str,  # 'depends', 'conflicts', 'similar', 'implements'
                "score": float,
                "explanation": str
            },
            ...
        ]

    Example:
        related = get_related_requirements(
            requirement_id="REQ-001",
            requirements=[...],
            top_k=5,
            relationship_types=["depends", "similar"]
        )
        # Returns: [
        #   {
        #     "req_id": "REQ-003",
        #     "text": "System must validate OAuth tokens",
        #     "relationship_type": "depends",
        #     "score": 0.88,
        #     "explanation": "REQ-001 authentication depends on token validation"
        #   }
        # ]
    """
    if not requirement_id or not requirements:
        return []

    try:
        response = requests.post(
            f"{API_BASE}/api/rag/related",
            json={
                "requirement_id": requirement_id,
                "requirements": requirements,
                "top_k": top_k,
                "relationship_types": relationship_types or ["depends", "conflicts", "similar", "implements"]
            },
            timeout=90
        )
        response.raise_for_status()

        result = response.json()
        return result.get("related", [])

    except requests.exceptions.RequestException as e:
        return [{
            "req_id": "ERROR",
            "text": f"Failed to find related requirements: {str(e)}",
            "relationship_type": "error",
            "score": 0.0
        }]
    except Exception as e:
        return [{
            "req_id": "ERROR",
            "text": f"Unexpected error: {str(e)}",
            "relationship_type": "error",
            "score": 0.0
        }]


def analyze_requirement_coverage(
    requirements: List[Dict[str, Any]],
    categories: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Analyze requirement coverage across different categories.

    Identify gaps in requirements coverage by analyzing distribution across
    functional areas, priorities, or custom categories.

    Args:
        requirements: List of requirements to analyze
        categories: Categories to analyze - ['functional', 'non-functional', 'security', 'performance']
                   If None, uses default categories (default: None)

    Returns:
        {
            "success": bool,
            "coverage": {
                "functional": {
                    "count": int,
                    "percentage": float,
                    "subcategories": Dict[str, int]
                },
                "non-functional": {...},
                ...
            },
            "gaps": [
                {
                    "category": str,
                    "severity": str,  # 'critical', 'medium', 'low'
                    "description": str,
                    "recommendation": str
                }
            ],
            "stats": {
                "total_requirements": int,
                "categorized": int,
                "uncategorized": int
            }
        }

    Example:
        analysis = analyze_requirement_coverage(
            requirements=[...],
            categories=["functional", "security", "performance"]
        )
        # Returns: {
        #   "coverage": {
        #     "functional": {"count": 15, "percentage": 60.0},
        #     "security": {"count": 5, "percentage": 20.0},
        #     "performance": {"count": 3, "percentage": 12.0}
        #   },
        #   "gaps": [
        #     {
        #       "category": "performance",
        #       "severity": "medium",
        #       "description": "Only 12% coverage in performance requirements"
        #     }
        #   ]
        # }
    """
    if not requirements:
        return {
            "success": False,
            "error": "No requirements provided",
            "coverage": {},
            "gaps": [],
            "stats": {"total_requirements": 0}
        }

    try:
        response = requests.post(
            f"{API_BASE}/api/rag/coverage",
            json={
                "requirements": requirements,
                "categories": categories or ["functional", "non-functional", "security", "performance", "usability"]
            },
            timeout=90
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Coverage analysis failed: {str(e)}",
            "coverage": {},
            "gaps": [],
            "stats": {"total_requirements": len(requirements)}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "coverage": {},
            "gaps": [],
            "stats": {"total_requirements": len(requirements)}
        }


# Export as FunctionTools for AutoGen agents
rag_tools = [
    FunctionTool(
        find_duplicates,
        description="Find semantic duplicate requirements using vector embeddings. Groups duplicates by similarity threshold. Returns duplicate groups with similarity scores."
    ),
    FunctionTool(
        semantic_search_requirements,
        description="Semantic search for requirements similar to query text. Can search in provided list or Qdrant vector store. Returns ranked results with similarity scores."
    ),
    FunctionTool(
        get_related_requirements,
        description="Find requirements related to a specific requirement. Discovers dependencies, conflicts, and semantic similarities. Returns related requirements with relationship types."
    ),
    FunctionTool(
        analyze_requirement_coverage,
        description="Analyze requirement coverage across categories (functional, security, performance, etc.). Identifies gaps and provides recommendations. Returns coverage statistics and gap analysis."
    )
]


# For testing
if __name__ == "__main__":
    print("RAG Tools Module")
    print("================")
    print(f"API Base: {API_BASE}")
    print(f"\nAvailable tools: {len(rag_tools)}")
    for tool in rag_tools:
        print(f"  - {tool._func.__name__}")
