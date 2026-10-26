"""test_cli.py - Simple tests for CLI argument parsing."""

from storm_sim.cli import parse_args


def test_cli_defaults():
    args = parse_args([])
    assert args.intensity == 0.5
    assert args.pixels == 512
    assert args.multicast is False
    assert args.e131_host is None
    assert args.ui is False


def test_cli_custom_flags():
    args = parse_args(["-i", "0.9", "--pixels", "1024", "--e131-host", "192.168.1.50"])
    assert args.intensity == 0.9
    assert args.pixels == 1024
    assert args.e131_host == "192.168.1.50"
