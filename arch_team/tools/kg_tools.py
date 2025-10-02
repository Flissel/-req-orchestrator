"""
Knowledge Graph Tools for KGAgent

Provides tools for building, querying, and managing knowledge graphs.
"""

import requests
import os
from typing import List, Dict, Any, Optional
from autogen_core.tools import FunctionTool

API_BASE = os.environ.get("ARCH_TEAM_API_BASE", "http://localhost:8000")


def build_knowledge_graph(
    items: List[Dict[str, Any]],
    use_llm: bool = True,
    persist: str = "qdrant",
    llm_fallback: bool = True,
    persist_async: bool = True
) -> Dict[str, Any]:
    """
    Build knowledge graph from requirement items.

    Complete pipeline that extracts entities, builds graph structure, and persists to vector store.

    Args:
        items: List of requirement DTOs with req_id, text, source, etc.
        use_llm: Use LLM for entity extraction (default: True)
        persist: Where to persist - 'qdrant', 'json', or 'none' (default: 'qdrant')
        llm_fallback: Use rule-based extraction if LLM fails (default: True)
        persist_async: Persist asynchronously (default: True)

    Returns:
        {
            "success": bool,
            "nodes": List[NodeDTO],
            "edges": List[EdgeDTO],
            "stats": {
                "node_count": int,
                "edge_count": int,
                "requirements_linked": int,
                "entity_types": Dict[str, int]
            }
        }

    Example:
        result = build_knowledge_graph(
            items=[{"req_id": "REQ-001", "text": "System must..."}],
            use_llm=True,
            persist="qdrant"
        )
        # Returns: {"success": True, "nodes": [...], "edges": [...], "stats": {...}}
    """
    if not items:
        return {
            "success": False,
            "error": "No items provided",
            "nodes": [],
            "edges": [],
            "stats": {"node_count": 0, "edge_count": 0}
        }

    try:
        response = requests.post(
            f"{API_BASE}/api/kg/build",
            json={
                "items": items,
                "options": {
                    "use_llm": use_llm,
                    "persist": persist,
                    "llm_fallback": llm_fallback,
                    "persist_async": persist_async
                }
            },
            timeout=180  # 3 minutes for large graphs
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}",
            "nodes": [],
            "edges": [],
            "stats": {"node_count": 0, "edge_count": 0}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "nodes": [],
            "edges": [],
            "stats": {"node_count": 0, "edge_count": 0}
        }


def add_kg_nodes(
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Add nodes to knowledge graph.

    Manually add nodes with custom properties.

    Args:
        nodes: List of node objects with structure:
            {
                "id": str,
                "label": str,
                "type": str,
                "properties": Dict[str, Any]
            }

    Returns:
        {"success": bool, "count": int, "node_ids": List[str]}

    Example:
        result = add_kg_nodes([
            {
                "id": "custom_node_1",
                "label": "Authentication Module",
                "type": "Component",
                "properties": {"priority": "high"}
            }
        ])
        # Returns: {"success": True, "count": 1, "node_ids": ["custom_node_1"]}
    """
    if not nodes:
        return {"success": False, "error": "No nodes provided", "count": 0, "node_ids": []}

    try:
        response = requests.post(
            f"{API_BASE}/api/kg/nodes",
            json={"nodes": nodes},
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}",
            "count": 0,
            "node_ids": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "count": 0,
            "node_ids": []
        }


def add_kg_edges(
    edges: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Add edges to knowledge graph.

    Manually add relationships between nodes.

    Args:
        edges: List of edge objects with structure:
            {
                "source": str,      # node ID
                "target": str,      # node ID
                "relation": str,    # edge type
                "properties": Dict[str, Any]
            }

    Returns:
        {"success": bool, "count": int, "edge_ids": List[str]}

    Example:
        result = add_kg_edges([
            {
                "source": "node_1",
                "target": "node_2",
                "relation": "depends_on",
                "properties": {"weight": 0.9}
            }
        ])
        # Returns: {"success": True, "count": 1, "edge_ids": ["edge_1"]}
    """
    if not edges:
        return {"success": False, "error": "No edges provided", "count": 0, "edge_ids": []}

    try:
        response = requests.post(
            f"{API_BASE}/api/kg/edges",
            json={"edges": edges},
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}",
            "count": 0,
            "edge_ids": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "count": 0,
            "edge_ids": []
        }


def search_semantic(
    query_text: str,
    top_k: int = 10,
    min_score: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Semantic search in knowledge graph.

    Find nodes semantically similar to query text using vector embeddings.

    Args:
        query_text: Search query (natural language)
        top_k: Number of results to return (default: 10)
        min_score: Minimum similarity score 0-1 (default: 0.7)

    Returns:
        List of matching nodes with scores:
        [
            {
                "node_id": str,
                "label": str,
                "type": str,
                "score": float,
                "properties": Dict
            },
            ...
        ]

    Example:
        results = search_semantic(
            query_text="authentication requirements",
            top_k=5
        )
        # Returns: [
        #   {"node_id": "node_1", "label": "OAuth 2.0", "score": 0.95, ...},
        #   {"node_id": "node_2", "label": "User Login", "score": 0.88, ...}
        # ]
    """
    if not query_text or not query_text.strip():
        return []

    try:
        response = requests.post(
            f"{API_BASE}/api/kg/search/semantic",
            json={
                "query": query_text,
                "top_k": top_k,
                "min_score": min_score
            },
            timeout=30
        )
        response.raise_for_status()

        result = response.json()
        return result.get("results", [])

    except requests.exceptions.RequestException as e:
        return [{
            "node_id": "ERROR",
            "label": f"Search failed: {str(e)}",
            "score": 0.0,
            "type": "error"
        }]
    except Exception as e:
        return [{
            "node_id": "ERROR",
            "label": f"Unexpected error: {str(e)}",
            "score": 0.0,
            "type": "error"
        }]


def query_kg_by_type(
    entity_type: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Query knowledge graph by entity type.

    Get all nodes of a specific type (e.g., "Actor", "Component", "Feature").

    Args:
        entity_type: Type of entities to retrieve
        limit: Maximum number of results (default: 50)

    Returns:
        List of nodes matching the type

    Example:
        actors = query_kg_by_type("Actor", limit=10)
        # Returns: [
        #   {"node_id": "node_1", "label": "User", "type": "Actor", ...},
        #   {"node_id": "node_2", "label": "Admin", "type": "Actor", ...}
        # ]
    """
    if not entity_type or not entity_type.strip():
        return []

    try:
        response = requests.get(
            f"{API_BASE}/api/kg/query/by-type",
            params={
                "type": entity_type,
                "limit": limit
            },
            timeout=30
        )
        response.raise_for_status()

        result = response.json()
        return result.get("nodes", [])

    except requests.exceptions.RequestException as e:
        return [{
            "node_id": "ERROR",
            "label": f"Query failed: {str(e)}",
            "type": "error"
        }]
    except Exception as e:
        return [{
            "node_id": "ERROR",
            "label": f"Unexpected error: {str(e)}",
            "type": "error"
        }]


def export_kg_graph(
    format: str = "cytoscape"
) -> Dict[str, Any]:
    """
    Export knowledge graph in specified format.

    Retrieve complete graph for visualization or external processing.

    Args:
        format: Export format - 'cytoscape', 'graphml', 'json' (default: 'cytoscape')

    Returns:
        {
            "success": bool,
            "format": str,
            "data": Dict  # Format-specific graph data
        }

    Example:
        graph = export_kg_graph(format="cytoscape")
        # Returns: {
        #   "success": True,
        #   "format": "cytoscape",
        #   "data": {"elements": {"nodes": [...], "edges": [...]}}
        # }
    """
    try:
        response = requests.get(
            f"{API_BASE}/api/kg/export",
            params={"format": format},
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Export failed: {str(e)}",
            "format": format,
            "data": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "format": format,
            "data": {}
        }


# Export as FunctionTools for AutoGen agents
kg_tools = [
    FunctionTool(
        build_knowledge_graph,
        description="Build complete knowledge graph from requirements using LLM entity extraction. Returns nodes, edges, and statistics. Can persist to Qdrant vector store."
    ),
    FunctionTool(
        add_kg_nodes,
        description="Manually add nodes to knowledge graph with custom properties. Useful for adding domain-specific entities."
    ),
    FunctionTool(
        add_kg_edges,
        description="Manually add relationships between nodes in knowledge graph. Define custom edge types and properties."
    ),
    FunctionTool(
        search_semantic,
        description="Semantic search in knowledge graph using vector embeddings. Find nodes similar to query text."
    ),
    FunctionTool(
        query_kg_by_type,
        description="Query knowledge graph by entity type (Actor, Component, Feature, etc.). Get all nodes of a specific type."
    ),
    FunctionTool(
        export_kg_graph,
        description="Export complete knowledge graph in specified format (cytoscape, graphml, json) for visualization or processing."
    )
]


# For testing
if __name__ == "__main__":
    print("KG Tools Module")
    print("===============")
    print(f"API Base: {API_BASE}")
    print(f"\nAvailable tools: {len(kg_tools)}")
    for tool in kg_tools:
        print(f"  - {tool._func.__name__}")
