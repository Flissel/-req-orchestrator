#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick test for parallel validation with mock API."""
import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_parallel():
    from arch_team.agents.validation_delegator import ValidationDelegatorAgent
    from arch_team.agents.validation_worker import ValidationWorkerAgent
    
    print('Creating delegator with 5 workers...')
    
    # Create mock requirements
    requirements = [
        {'req_id': f'REQ-{i}', 'title': f'Test requirement {i}', 'tag': 'functional'}
        for i in range(20)
    ]
    
    print(f'Testing with {len(requirements)} requirements...')
    
    # Monkey-patch the API call to simulate latency
    def mock_api_call(self, task):
        time.sleep(0.3)  # Simulate 300ms API call
        return {'score': 0.85, 'verdict': 'pass', 'evaluation': []}
    
    ValidationWorkerAgent._call_validation_api = mock_api_call
    
    delegator = ValidationDelegatorAgent(max_concurrent=5)
    
    start = time.time()
    result = await delegator.validate_batch(requirements)
    elapsed = time.time() - start
    
    sequential_estimate = len(requirements) * 0.3
    
    print('')
    print('===== RESULTS =====')
    print(f'Requirements: {len(requirements)}')
    print(f'Workers: 5')
    print('')
    print(f'Sequential estimate: {sequential_estimate:.1f}s')
    print(f'Parallel actual: {elapsed:.1f}s')
    print(f'Speedup: {sequential_estimate/elapsed:.1f}x')
    print('')
    print(f'Passed: {result.passed_count}')
    print(f'Failed: {result.failed_count}')


if __name__ == "__main__":
    asyncio.run(test_parallel())