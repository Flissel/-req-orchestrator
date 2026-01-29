#!/usr/bin/env python3
"""Quick demo of interactive enhancement with auto-answer."""

import asyncio
import websockets
import json

async def test_one():
    req_text = 'The system must display the count of open ports for each port'
    ws_url = 'ws://localhost:8087/enhance/ws/test-demo-session'
    
    print('Connecting to WebSocket...')
    async with websockets.connect(ws_url, open_timeout=30) as ws:
        # Start enhancement
        await ws.send(json.dumps({
            'type': 'enhancement_start',
            'requirement_text': req_text
        }))
        print('Enhancement started!')
        print(f'Original: {req_text}\n')
        
        while True:
            try:
                data = json.loads(await asyncio.wait_for(ws.recv(), 60))
            except asyncio.TimeoutError:
                print('Timeout waiting for response')
                break
            
            msg_type = data.get('type')
            message = data.get('message', '')
            
            if msg_type == 'connected':
                print(f'✓ {message}')
            elif msg_type == 'progress':
                print(f'⏳ {message}')
            elif msg_type == 'purpose':
                print(f'🎯 {message}')
            elif msg_type == 'evaluation':
                print(f'📊 {message}')
            elif msg_type == 'rewritten':
                print(f'✏️  {message}')
            elif msg_type == 'clarification_request':
                question = data.get('data', {}).get('question', message)
                gap = data.get('data', {}).get('gap_being_addressed', '')
                
                print(f'\n❓ QUESTION: {question}')
                if gap:
                    print(f'   Gap: {gap}')
                
                # Auto-answer
                answer = 'Display on the main dashboard as a table, update every 5 seconds'
                print(f'   Auto-answer: {answer}')
                
                await ws.send(json.dumps({
                    'type': 'clarification_response',
                    'answer': answer
                }))
                print('✓ Answer sent!\n')
                
            elif msg_type == 'complete':
                result = data.get('data', data.get('result', {}))
                print('\n' + '='*60)
                print('🎉 ENHANCEMENT COMPLETE!')
                print('='*60)
                print(f'\n📝 Original:  {result.get("original_text", req_text)}')
                print(f'✨ Enhanced:  {result.get("enhanced_text", "N/A")}')
                print(f'\n📊 Score:     {result.get("final_score", 0):.0%}')
                print(f'🔄 Iterations: {result.get("iterations_used", "N/A")}')
                print(f'❓ Questions:  {result.get("questions_asked", "N/A")}')
                print(f'🎯 Purpose:   {result.get("purpose_identified", "N/A")}')
                break
                
            elif msg_type == 'error':
                print(f'\n❌ ERROR: {message}')
                break

if __name__ == '__main__':
    asyncio.run(test_one())