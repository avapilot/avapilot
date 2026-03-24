# Contributing to AvaPilot

## Register a service

The easiest way to contribute: register an Avalanche protocol.

```bash
avapilot register "Protocol Name" 0xContractAddress \
  --category DeFi \
  --description "What it does"
```

Then add it to `avapilot/registry/seed.py` and open a PR.

## Run tests

```bash
python tests/test_read_only.py       # 56 tests, zero gas
python tests/test_lazy_discovery.py  # 28 tests, lazy discovery
python tests/test_fuji.py            # 18 tests, Fuji testnet (costs gas)
```

## Code style

- Python 3.10+
- Type hints on public functions  
- Docstrings on all tools
- `stderr` for logs (stdout is MCP protocol)

## License

MIT
