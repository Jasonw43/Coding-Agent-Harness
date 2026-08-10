"""Deterministic tests for the CLI entrypoint."""

from cah.cli import build_parser, main


def test_parser_commands():
    p = build_parser()
    cases = {
        "run": ["run", "task"],
        "approve": ["approve", "a1", "--token", "t"],
        "reject": ["reject", "a1", "--token", "t"],
        "status": ["status"],
        "key": ["key", "status"],
        "config": ["config", "show"],
        "demo": ["demo"],
    }
    for cmd, argv in cases.items():
        args = p.parse_args(argv)
        assert args.command == cmd


def test_mock_run_smoke(tmp_path, capsys):
    code = main(["run", "--mock", "--workspace", str(tmp_path), "hello task"])
    out = capsys.readouterr().out
    assert code == 0 and "done" in out.lower()
