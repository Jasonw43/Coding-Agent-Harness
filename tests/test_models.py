from cah.models import Action, ToolResult, GuardrailDecision, Feedback, LLMResponse, RunResult


def test_action_fields():
    a = Action(id="a1", type="shell", params={"command": "pwd"}, run_id="r1")
    assert a.type == "shell" and a.params["command"] == "pwd"


def test_guardrail_decision_defaults():
    d = GuardrailDecision(verdict="SAFE")
    assert d.reason == "" and d.risk_level == "low"


def test_run_result_status_default():
    r = RunResult(run_id="r1", status="running", steps=0, actions_log=[], final_output="")
    assert r.status == "running"


def test_feedback_and_llm_response():
    fb = Feedback(ok=False, failures=["FAILED test_x"], summary="1 failed")
    resp = LLMResponse(text="t", action=None, done=True)
    assert not fb.ok and resp.done
