"""Deterministic test for DeepSeekLLM using a mocked HTTP transport."""

import httpx

from cah.llm.deepseek import DeepSeekLLM


def _transport():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "hello from deepseek"}}]
            },
        )

    return httpx.MockTransport(handler)


def test_deepseek_complete_returns_text():
    llm = DeepSeekLLM(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        transport=_transport(),
    )
    resp = llm.complete(
        context=[{"role": "user", "content": "hi"}], available_actions=[]
    )
    assert resp.text == "hello from deepseek" and resp.done
