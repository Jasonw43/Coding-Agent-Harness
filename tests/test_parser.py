"""Deterministic tests for parsing LLM output into actions."""

from cah.actions.parser import parse_action


def test_parse_json_action():
    text = 'Sure, here is the action:\n{"action": {"type": "write_file", "params": {"path": "a.txt", "content": "x"}}}'
    parsed = parse_action(text, available_tools=["write_file"])
    assert parsed.action is not None
    assert parsed.action.type == "write_file"
    assert parsed.action.params["path"] == "a.txt"
    assert parsed.done is False and parsed.error is None


def test_parse_plain_text_is_done():
    parsed = parse_action("I finished the task. Here is the summary.", available_tools=[])
    assert parsed.done is True and parsed.action is None
    assert parsed.answer == "I finished the task. Here is the summary."


def test_parse_code_block_without_action_is_error():
    text = 'Here is the code:\n```python\ndef add_big(a, b):\n    return a + b\n```'
    parsed = parse_action(text, available_tools=["write_file"])
    assert parsed.error is not None and "code" in parsed.error.lower()


def test_parse_explicit_done_object():
    text = '{"done": true, "answer": "all tests pass"}'
    parsed = parse_action(text, available_tools=[])
    assert parsed.done is True and parsed.answer == "all tests pass"


def test_parse_malformed_json_returns_error():
    parsed = parse_action('{"action": {"type": "write_file"', available_tools=["write_file"])
    assert parsed.error is not None and parsed.action is None


def test_parse_unknown_tool_rejected():
    text = '{"action": {"type": "no_such_tool", "params": {}}}'
    parsed = parse_action(text, available_tools=["write_file"])
    assert parsed.error is not None and "no_such_tool" in parsed.error


def test_parse_invoke_style_tool_call():
    text = (
        "I will create the file now.\n"
        '<dsml:invoke name="write_file">\n'
        '<dsml:parameter name="path">a.txt</dsml:parameter>\n'
        '<dsml:parameter name="content">hi</dsml:parameter>\n'
        "</dsml:invoke>"
    )
    parsed = parse_action(text, available_tools=["write_file"])
    assert parsed.action is not None
    assert parsed.action.type == "write_file"
    assert parsed.action.params == {"path": "a.txt", "content": "hi"}


def test_parse_invoke_style_unknown_tool():
    text = '<dsml:invoke name="no_such_tool"><dsml:parameter name="x">1</dsml:parameter></dsml:invoke>'
    parsed = parse_action(text, available_tools=["write_file"])
    assert parsed.error is not None and "no_such_tool" in parsed.error


def test_parse_multiple_actions_in_one_reply():
    text = (
        '{"action": {"type": "write_file", "params": {"path": "a.txt", "content": "1"}}}\n'
        '{"action": {"type": "write_file", "params": {"path": "b.txt", "content": "2"}}}\n'
        '{"action": {"type": "run_tests"}}'
    )
    parsed = parse_action(text, available_tools=["write_file", "run_tests"])
    assert parsed.error is None
    assert len(parsed.actions) == 3
    assert [a.type for a in parsed.actions] == ["write_file", "write_file", "run_tests"]
