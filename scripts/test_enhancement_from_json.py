#!/usr/bin/env python3
"""
Test script to demonstrate interactive question-asking enhancement
for requirements loaded from the slim.json file.
"""

import asyncio
import websockets
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Backend URL
WS_URL = "ws://localhost:8087/enhance/ws"

# WebSocket Settings
WS_TIMEOUT = 30  # Handshake timeout
WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20


def load_requirements_from_json(json_path: str) -> list:
    """Load requirements from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('features', [])


def find_worst_requirements(requirements: list, limit: int = 5) -> list:
    """Find requirements with lowest scores (candidates for enhancement)."""
    scored = []
    for req in requirements:
        score = req.get('overall_score', 0)
        text = req.get('description') or req.get('name', '')
        if text:
            scored.append({
                'id': req.get('id'),
                'text': text,
                'score': score,
                'verdict': req.get('verdict'),
                'failed_criteria': [
                    e['criterion'] for e in req.get('evaluation', [])
                    if not e.get('passed', True)
                ]
            })
    
    # Sort by score (lowest first)
    scored.sort(key=lambda x: x['score'])
    return scored[:limit]


async def interactive_enhancement(requirement: dict):
    """Run interactive enhancement with question-asking via WebSocket."""
    
    session_id = f"test-{requirement['id'].replace('-', '')}"
    ws_url = f"{WS_URL}/{session_id}"
    
    print("\n" + "="*70)
    print(f"🔧 INTERACTIVE ENHANCEMENT FOR: {requirement['id']}")
    print("="*70)
    print(f"\n📝 Original Text: {requirement['text']}")
    print(f"📊 Current Score: {requirement['score']:.0%}")
    print(f"❌ Failed Criteria: {', '.join(requirement['failed_criteria'])}")
    print("\n" + "-"*70)
    
    try:
        async with websockets.connect(
            ws_url,
            open_timeout=WS_TIMEOUT,
            ping_interval=WS_PING_INTERVAL,
            ping_timeout=WS_PING_TIMEOUT
        ) as ws:
            # Start enhancement
            start_msg = {
                "type": "enhancement_start",
                "requirement_text": requirement['text'],
                "requirement_id": requirement['id']
            }
            await ws.send(json.dumps(start_msg))
            print(f"\n🚀 Enhancement gestartet...")
            
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=120)
                    data = json.loads(response)
                    
                    msg_type = data.get('type')
                    message = data.get('message', '')
                    
                    if msg_type == 'progress':
                        print(f"⏳ {message}")
                    
                    elif msg_type == 'clarification_request':
                        # Question is in data.question (single question), not questions array
                        question_data = data.get('data', {})
                        question = question_data.get('question', '') or data.get('message', '')
                        gap = question_data.get('gap_being_addressed', '')
                        examples = question_data.get('example_answers', [])
                        
                        print(f"\n❓ CLARIFICATION QUESTION:")
                        print("-"*50)
                        print(f"\n   {question}")
                        if gap:
                            print(f"\n   Gap: {gap}")
                        if examples:
                            print(f"   Examples: {', '.join(examples[:2])}")
                        
                        print("\n" + "-"*50)
                        print("📝 Bitte beantworte die Frage (oder 'auto' für automatische Antwort):")
                        
                        # Get user input
                        user_input = input("\n> ").strip()
                        
                        if user_input.lower() == 'auto':
                            # Let the system auto-answer
                            response_msg = {
                                "type": "clarification_response",
                                "answer": "[AUTO] System soll dies für Monitoring-Zwecke tun, mit Standard-Werten"
                            }
                        else:
                            response_msg = {
                                "type": "clarification_response",
                                "answer": user_input
                            }
                        
                        await ws.send(json.dumps(response_msg))
                        print(f"\n✅ Antwort gesendet!")
                    
                    elif msg_type == 'rewritten':
                        new_text = data.get('rewritten_text', '')
                        new_score = data.get('score', 0)
                        print(f"\n✏️  REWRITTEN:")
                        print(f"   Text: {new_text}")
                        print(f"   Score: {new_score:.0%}")
                    
                    elif msg_type == 'complete':
                        result = data.get('data', data.get('result', data))
                        print(f"\n" + "="*70)
                        print("🎉 ENHANCEMENT COMPLETE!")
                        print("="*70)
                        print(f"\n📝 Original:  {result.get('original_text', requirement['text'])}")
                        print(f"✨ Enhanced:  {result.get('enhanced_text', 'N/A')}")
                        print(f"\n📊 Score: {requirement['score']:.0%} → {result.get('final_score', 0):.0%}")
                        print(f"🔄 Iterations: {result.get('iterations_used', 'N/A')}")
                        print(f"❓ Questions: {result.get('questions_asked', 'N/A')}")
                        print(f"🎯 Purpose: {result.get('purpose_identified', 'N/A')}")
                        break
                    
                    elif msg_type == 'error':
                        print(f"\n❌ Error: {message}")
                        break
                        
                except asyncio.TimeoutError:
                    print("⏰ Timeout - keine Antwort vom Server")
                    break
                    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 Connection closed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    # Load requirements from JSON
    json_path = Path(__file__).parent.parent / "debug" / "requirements_20251127_001112.slim.json"
    
    print("="*70)
    print("📂 LOADING REQUIREMENTS FROM JSON")
    print("="*70)
    print(f"   File: {json_path}")
    
    requirements = load_requirements_from_json(str(json_path))
    print(f"   Total: {len(requirements)} requirements")
    
    # Find worst requirements
    worst = find_worst_requirements(requirements, limit=10)
    
    print("\n" + "="*70)
    print("🔍 TOP 10 REQUIREMENTS MIT NIEDRIGSTEM SCORE (Enhancement-Kandidaten)")
    print("="*70)
    
    for i, req in enumerate(worst, 1):
        print(f"\n   {i}. [{req['id']}] Score: {req['score']:.0%} - {req['verdict']}")
        print(f"      Text: {req['text'][:80]}...")
        print(f"      Failed: {', '.join(req['failed_criteria'][:3])}...")
    
    # Ask user which one to enhance
    print("\n" + "-"*70)
    print("Welches Requirement möchtest du interaktiv verbessern?")
    print("Gib die Nummer ein (1-10), oder 'q' zum Beenden:")
    
    while True:
        choice = input("\n> ").strip()
        
        if choice.lower() == 'q':
            print("Beendet.")
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(worst):
                await interactive_enhancement(worst[idx])
            else:
                print(f"Bitte eine Nummer zwischen 1 und {len(worst)} eingeben.")
        except ValueError:
            print("Ungültige Eingabe. Bitte eine Nummer eingeben.")

if __name__ == "__main__":
    asyncio.run(main())