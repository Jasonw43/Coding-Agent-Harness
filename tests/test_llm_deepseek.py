"""Deterministic test for DeepSeekLLM using a mocked HTTP transport."""

import httpx

from cah.llm.deepseek import DeepSeekLLM, LLMError


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
    assert resp.text == "hello from deepseek" and resp.done is False


def test_deepseek_complete_parses_tool_calls():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "write_file",
                                        "arguments": '{"path": "a.txt", "content": "hi"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    llm = DeepSeekLLM(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
    )
    resp = llm.complete(
        context=[{"role": "user", "content": "write a file"}],
        available_actions=["write_file"],
    )
    assert resp.actions is not None and len(resp.actions) == 1
    assert resp.actions[0].type == "write_file"
    assert resp.actions[0].params == {"path": "a.txt", "content": "hi"}


def test_deepseek_retries_transient_errors():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    llm = DeepSeekLLM(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
        max_attempts=3,
        retry_delay_s=0,
    )
    resp = llm.complete(context=[], available_actions=[])
    assert attempts["n"] == 3 and resp.text == "ok"


def test_deepseek_gives_up_after_max_attempts():
    def handler(request):
        raise httpx.ConnectError("still down", request=request)

    llm = DeepSeekLLM(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
        max_attempts=2,
        retry_delay_s=0,
    )
    try:
        llm.complete(context=[], available_actions=[])
        assert False, "should raise LLMError"
    except LLMError:
        pass
