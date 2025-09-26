import requests
import json

def test_fastapi_system():
    base_url = "http://127.0.0.1:8001"
    
    print("=== FastAPI Requirements System - Live Test ===")
    
    # 1. Health Check
    print("\n1. Health Check...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ Server läuft seit: {health_data['uptime']}")
            print(f"✓ Verarbeitete Requests: {health_data['processed']}")
        else:
            print("✗ Health Check fehlgeschlagen")
            return
    except Exception as e:
        print(f"✗ Verbindungsfehler: {e}")
        return
    
    # 2. System Status
    print("\n2. System Status...")
    try:
        response = requests.get(f"{base_url}/api/v1/system/status")
        if response.status_code == 200:
            status = response.json()
            print(f"✓ Active Workers: {status['activeWorkers']}")
            print(f"✓ Total Processed: {status['totalProcessedToday']}")
            print(f"✓ Mode: {status['mode']}")
        else:
            print("✗ System Status fehlgeschlagen")
    except Exception as e:
        print(f"✗ System Status Fehler: {e}")
    
    # 3. Requirements Evaluation Test
    print("\n3. Requirements Evaluation...")
    test_requirement = {
        "requirementText": "Das System soll eine REST API bereitstellen, die innerhalb von 200ms antwortet.",
        "context": {
            "language": "de",
            "area": "api",
            "priority": "high"
        }
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/requirements/evaluate", json=test_requirement)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Request ID: {result['requestId']}")
            print(f"✓ Score: {result['score']:.2f} ({result['score']*100:.1f}%)")
            print(f"✓ Verdict: {result['verdict']}")
            print(f"✓ Latency: {result['latencyMs']}ms")
            print(f"✓ Model: {result['model']}")
            
            print("\nDetails:")
            for key, value in result['details'].items():
                print(f"  - {key}: {value:.2f} ({value*100:.1f}%)")
            
            if result.get('suggestions'):
                print("\nSuggestions:")
                for i, suggestion in enumerate(result['suggestions'], 1):
                    print(f"  {i}. {suggestion}")
            
            print(f"\n✓ Requirements Evaluation erfolgreich!")
        else:
            print(f"✗ Evaluation fehlgeschlagen: {response.text}")
    except Exception as e:
        print(f"✗ Evaluation Fehler: {e}")
    
    # 4. Weitere Test-Requirements
    print("\n4. Weitere Test-Requirements...")
    
    test_cases = [
        {
            "text": "Die Anwendung muss SSL/TLS verwenden.",
            "context": {"area": "security", "priority": "high"}
        },
        {
            "text": "Kurz",
            "context": {"area": "test", "priority": "low"}
        },
        {
            "text": "Das System soll eine umfassende REST API bereitstellen, die alle CRUD-Operationen unterstützt, innerhalb von 100ms antwortet, SSL/TLS-Verschlüsselung verwendet, Authentifizierung und Autorisierung implementiert, und vollständig dokumentiert ist.",
            "context": {"area": "api", "priority": "high"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            test_req = {
                "requirementText": test_case["text"],
                "context": test_case["context"]
            }
            response = requests.post(f"{base_url}/api/v1/requirements/evaluate", json=test_req)
            
            if response.status_code == 200:
                result = response.json()
                print(f"Test {i}: Score {result['score']:.2f} - {result['verdict']} ({result['latencyMs']}ms)")
            else:
                print(f"Test {i}: Fehlgeschlagen")
                
        except Exception as e:
            print(f"Test {i}: Fehler - {e}")
    
    print("\n=== Live Test abgeschlossen ===")
    print(f"Frontend URL: {base_url}/frontend")
    print(f"API Docs: {base_url}/docs")

if __name__ == "__main__":
    test_fastapi_system()
