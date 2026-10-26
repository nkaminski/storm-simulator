"""test_cli.py - Simple tests for CLI argument parsing."""

from storm_sim.cli import parse_args


def test_cli_defaults():
    args = parse_args([])
    assert args.intensity == 0.5
    assert args.pixels == 4
    assert args.e131_host == "127.0.0.1"
    assert args.channel_map is None
    assert args.passthrough is None
    assert args.passthrough_universe is None
    assert args.ui is False
    assert args.small_speakers is False


def test_cli_custom_flags():
    args = parse_args([
        "-i", "0.9",
        "--pixels", "8",
        "--e131-host", "192.168.1.50",
        "--channel-map", "0:1,1:5,2:10,3:15",
        "--passthrough", "0.0.0.0:5568",
        "--passthrough-universe", "1",
        "--small-speakers",
    ])
    assert args.intensity == 0.9
    assert args.pixels == 8
    assert args.e131_host == "192.168.1.50"
    assert args.channel_map == "0:1,1:5,2:10,3:15"
    assert args.passthrough == "0.0.0.0:5568"
    assert args.passthrough_universe == 1
    assert args.small_speakers is True
