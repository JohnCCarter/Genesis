import importlib.util
import json
import os
import sys


def load_module_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main():
    # __file__ == <project>/scripts/mcp/_introspect.py
    project_root = os.path.dirname(
        os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
    )
    target = os.path.join(project_root, "scripts", "mcp", "genesis_mcp.py")
    mod = load_module_from_path("genesis_mcp_mod", target)
    app = getattr(mod, "app", None)
    info = {
        "import_ok": app is not None,
        "app_type": type(app).__name__ if app is not None else None,
        "has_run": hasattr(app, "run") if app is not None else None,
        "has_run_stdio": hasattr(app, "run_stdio") if app is not None else None,
        "tools_attr": hasattr(app, "tools") if app is not None else None,
        "tools": None,
        "dir_runish": (
            [n for n in dir(app) if n.startswith("run")] if app is not None else None
        ),
    }
    if app is not None:
        tools = getattr(app, "tools", None)
        if tools is not None:
            try:
                info["tools"] = [
                    (
                        getattr(t, "name", None)
                        or (t.get("name") if isinstance(t, dict) else None)
                    )
                    for t in tools
                ]
            except Exception as e:
                info["tools"] = f"ERR:{type(e).__name__}:{e}"
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
