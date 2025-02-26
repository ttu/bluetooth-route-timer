# Bluetooth Route Timer

Prototype application for tracking the time taken to complete a route using Bluetooth Low Energy sensors.

## Requirements

- asdf, Python, uv
- Two or more Bluetooth sensors

## Setup

1. Install asdf:

```bash
# e.g. on macOS
brew install asdf
```

Install Python and UV:

```bash
asdf install
```

This might require for the plugins to be added first. If so, add them with as instructed by the asdf install.

Create and activate virtual environment with UV:

```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows

uv pip install -e .
```

Run the application:

```bash
python bluetooth_route_timer/main.py
```

## Development

Run linter:

```bash
ruff check .
```

## License

MIT
