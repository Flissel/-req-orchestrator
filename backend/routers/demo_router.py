"""
Demo-Router für Test-Requirements
"""
from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(tags=["demo"])

# Sample requirements for testing the validation UI
DEMO_REQUIREMENTS = [
    {
        "id": "REQ-001",
        "requirementText": "Das System muss eine Antwortzeit von maximal 200ms für alle API-Endpunkte einhalten."
    },
    {
        "id": "REQ-002", 
        "requirementText": "Der Benutzer soll sich mit E-Mail und Passwort anmelden können."
    },
    {
        "id": "REQ-003",
        "requirementText": "Die Anwendung muss HTTPS für alle Verbindungen nutzen."
    },
    {
        "id": "REQ-004",
        "requirementText": "Es sollen maximal 1000 gleichzeitige Benutzer unterstützt werden."
    },
    {
        "id": "REQ-005",
        "requirementText": "Das System sollte irgendwie besser sein als die Konkurrenz."
    },
    {
        "id": "REQ-006",
        "requirementText": "Alle Daten müssen verschlüsselt gespeichert werden und der Zugriff muss protokolliert werden."
    },
    {
        "id": "REQ-007",
        "requirementText": "Der Export von Berichten als PDF sollte möglich sein."
    },
    {
        "id": "REQ-008",
        "requirementText": "Die Benutzeroberfläche muss responsiv sein und auf allen gängigen Bildschirmgrößen (Desktop, Tablet, Mobile) gut dargestellt werden."
    },
    {
        "id": "REQ-009",
        "requirementText": "The system must provide multi-language support for German and English."
    },
    {
        "id": "REQ-010",
        "requirementText": "Fehlermeldungen sollen klar und verständlich sein."
    }
]


@router.get("/api/v1/demo/requirements")
async def get_demo_requirements() -> Dict[str, Any]:
    """
    Returns a list of demo requirements for testing the validation UI.
    """
    return {"items": DEMO_REQUIREMENTS}


@router.get("/api/v1/demo/requirements/count")
async def get_demo_requirements_count() -> Dict[str, int]:
    """
    Returns the count of demo requirements.
    """
    return {"count": len(DEMO_REQUIREMENTS)}