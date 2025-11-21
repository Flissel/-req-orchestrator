# -*- coding: utf-8 -*-
import types


def test_lx_extract_json(monkeypatch):
    # Import v2 module and app
    import backend.api_v2_part2 as api_v2_part2
    from backend import app

    # Fake LangExtract module with minimal extract implementation
    class _FakeLX:
        @staticmethod
        def extract(text_or_documents, prompt_description, examples, model_id, api_key):
            # Return a dict structure compatible with _normalize_lx_result
            return {
                "extractions": [
                    {
                        "extraction_class": "requirement",
                        "extraction_text": "Antwortzeit 200ms",
                        "char_interval": {"start_pos": 0, "end_pos": 15},
                        "attributes": {},
                    }
                ]
            }

    # Monkeypatch module variable used by the endpoint
    monkeypatch.setattr(api_v2_part2, "lx", _FakeLX, raising=False)

    client = app.test_client()

    # Minimal JSON invocation (no files)
    payload = {
        "text": "| R1 | Das System MUSS Antwortzeit p95 <= 200ms liefern | {} |"
    }
    resp = client.post("/api/v1/lx/extract", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert isinstance(data, dict)
    assert isinstance(data.get("lxPreview"), list)
    assert any((e or {}).get("extraction_class") == "requirement" for e in data.get("lxPreview", []))

    # After extract, latest mine should succeed (best-effort)
    mine = client.get("/api/v1/lx/mine?latest=1")
    assert mine.status_code == 200, mine.get_data(as_text=True)
    mined = mine.get_json() or {}
    assert isinstance(mined.get("items"), list)




