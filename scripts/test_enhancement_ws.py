#!/usr/bin/env python3
"""Test script for WebSocket-based iterative enhancement flow."""

import asyncio
import json
import uuid
import websockets


async def test_enhancement_flow():
    """Test the full iterative enhancement flow via WebSocket."""
    
    session_id = str(uuid.uuid4())
    url = f"ws://localhost:8087/enhance/ws/{session_id}"
    
    # Test requirement - deliberately vague to trigger clarification
    test_requirement = """
    The system should filter results in real-time.
    """
    
    print(f"\n{'='*60}")
    print("Testing Iterative Enhancement WebSocket Flow")
    print(f"{'='*60}")
    print(f"Session ID: {session_id}")
    print(f"Requirement: {test_requirement.strip()}")
    print(f"{'='*60}\n")
    
    try:
        async with websockets.connect(url) as ws:
            # Wait for connection confirmation
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(response)
            print(f"📡 Connected: {data.get('message', data)}")
            
            # Start enhancement
            print("\n🚀 Starting enhancement...")
            await ws.send(json.dumps({
                "type": "enhancement_start",
                "requirement_text": test_requirement.strip()
            }))
            
            questions_asked = 0
            max_questions = 3  # Limit questions for test
            
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=120)
                    data = json.loads(response)
                    msg_type = data.get("type", "")
                    
                    if msg_type == "progress":
                        print(f"   🔄 Progress: {data.get('message', data.get('stage', ''))}")
                    
                    elif msg_type == "purpose":
                        print(f"   🎯 PURPOSE: {data.get('purpose', '')}")
                    
                    elif msg_type == "gaps":
                        gaps = data.get('gaps', [])
                        print(f"   🔍 GAPS: {', '.join(gaps) if gaps else 'None found'}")
                    
                    elif msg_type == "evaluation":
                        score = data.get('score', data.get('quality_score', 0))
                        iteration = data.get('iteration', '?')
                        print(f"   📊 EVALUATION: {score*100:.0f}% (Iteration {iteration})")
                    
                    elif msg_type == "rewritten":
                        text = data.get('text', data.get('rewritten_text', ''))[:100]
                        print(f"   📝 REWRITTEN: {text}...")
                    
                    elif msg_type == "clarification_request":
                        question = data.get('question', {})
                        q_text = question.get('question', str(question)) if isinstance(question, dict) else question
                        print(f"\n   ❓ QUESTION: {q_text}")
                        
                        questions_asked += 1
                        if questions_asked >= max_questions:
                            answer = "Keine weiteren Informationen verfügbar."
                            print(f"   ➡️ Auto-answer (limit reached): {answer}")
                        else:
                            # Simulate user answer
                            answer = f"Die Filterung soll innerhalb von 100ms erfolgen mit Auto-Complete nach 2 Zeichen."
                            print(f"   ➡️ Simulated answer: {answer}")
                        
                        # Send answer
                        await ws.send(json.dumps({
                            "type": "clarification_response",
                            "answer": answer
                        }))
                        print("   📤 Answer sent, waiting for next cycle...\n")
                    
                    elif msg_type == "complete":
                        # Result can be in data.result or data.data (from _send_ws_message)
                        result = data.get('result', data.get('data', data))
                        print(f"\n{'='*60}")
                        print("🎉 ENHANCEMENT COMPLETE!")
                        print(f"{'='*60}")
                        print(f"Original: {result.get('original_text', 'N/A')[:80]}...")
                        print(f"Enhanced: {result.get('enhanced_text', 'N/A')[:200]}...")
                        print(f"Final Score: {result.get('final_score', 0)*100:.0f}%")
                        print(f"Iterations: {result.get('iterations_used', 'N/A')}")
                        print(f"Questions Asked: {result.get('questions_asked', questions_asked)}")
                        print(f"Purpose: {result.get('purpose_identified', 'N/A')}")
                        print(f"Success: {result.get('success', 'N/A')}")
                        print(f"{'='*60}\n")
                        break
                    
                    elif msg_type == "error":
                        print(f"\n   ❌ ERROR: {data.get('message', data)}")
                        break
                    
                    else:
                        print(f"   📩 {msg_type}: {data}")
                        
                except asyncio.TimeoutError:
                    print("⏰ Timeout waiting for response")
                    break
                    
    except ConnectionRefusedError:
        print("❌ Could not connect to WebSocket server. Make sure backend is running.")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\nStarting WebSocket Enhancement Test...")
    asyncio.run(test_enhancement_flow())