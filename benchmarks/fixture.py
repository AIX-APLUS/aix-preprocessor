"""Build the fixed Sprint 0 Git history. Requires Git and Python 3.8+."""

import argparse
import os
from pathlib import Path
import subprocess


def clean_java(left, right):
    # Distant edits allow Git to merge both fields without a text conflict.
    return (
        "class Clean {\n"
        f"    int left = {left};\n"
        "\n    int sum() {\n        return left + right;\n    }\n\n"
        f"    int right = {right};\n"
        "}\n"
    )


def conflict_java(value):
    return f"class Conflict {{\n    int value = {value};\n}}\n"


def fixture_stream():
    """Construct actual two-parent commits with explicit parents, trees and dates."""
    stream = []
    mark = 0

    def data(value):
        # fast-import counts bytes. The complete stream uses ASCII and LF.
        stream.extend([f"data {len(value.encode('ascii'))}\n", value, "\n"])

    def commit(branch, day, author, message, files, *parents):
        nonlocal mark
        mark += 1
        timestamp = 1577836800 + day * 86400  # 2020-01-01 UTC + day
        identity = f"{author} <{author.lower()}@example.test> {timestamp} +0000"
        stream.extend([
            f"commit refs/heads/{branch}\nmark :{mark}\n",
            f"author {identity}\ncommitter {identity}\n",
        ])
        data(message + "\n")
        if parents:
            stream.append(f"from :{parents[0]}\n")
        for parent in parents[1:]:
            stream.append(f"merge :{parent}\n")
        for name, contents in files.items():
            stream.append(f"M 100644 inline {name}\n")
            data(contents)
        stream.append("\n")
        return mark

    root = commit("main", 0, "Alice", "old root", {
        "Clean.java": clean_java(0, 0),
        "Conflict.java": conflict_java(0),
        "OneSide.java": "class OneSide {}\n",
        "README.txt": "original\n",
    })
    edit = commit("main", 98, "Alice", "edit left and value", {
        "Clean.java": clean_java(1, 0), "Conflict.java": conflict_java(1),
    }, root)
    edit = commit("main", 100, "Bob", "edit right", {"Clean.java": clean_java(1, 2)}, edit)
    base = commit("main", 102, "Bob", "establish merge base", {"README.txt": "base\n"}, edit)

    # Each fork edits four shared paths. Only two were Java files at the base.
    # OneSide.java changes on the left alone, so it must also be absent.
    for branch, day in [("main", 103), ("side", 106)]:
        left = commit(branch, day, "Alice", f"{branch} left", {
            "Clean.java": clean_java(day, 2),
            "Conflict.java": conflict_java(3),
            "OneSide.java": "class OneSide { int left; }\n",
            "Added.java": "class Added { int left; }\n",
            "README.txt": "left\n",
        }, base)
        right = commit(f"{branch}-right", day + 1, "Bob", f"{branch} right", {
            "Clean.java": clean_java(1, day),
            "Conflict.java": conflict_java(4),
            "Added.java": "class Added { int right; }\n",
            "README.txt": "right\n",
        }, base)
        merged = commit(branch, day + 2, "Bob", f"resolve {branch}", {
            "Clean.java": clean_java(day, day),
            "Conflict.java": conflict_java(5),
            "Added.java": "class Added { int both; }\n",
            "README.txt": "resolved\n",
        }, left, right)
        if branch == "main":
            stream.append(f"reset refs/tags/alias-main\nfrom :{merged}\n\n")
    stream.append("done\n")
    return "".join(stream).encode("ascii")


def create_fixture(path):
    """Create a clean, full repository at a new path. Existing paths are refused."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    env = {key: val for key, val in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1")

    def git(*args, input_bytes=None):
        subprocess.run(["git", *args], cwd=path, env=env, input=input_bytes, check=True)

    git("init", "--quiet", "--initial-branch=main", "--object-format=sha1", "--template=")
    git("config", "core.autocrlf", "false")
    git("fast-import", "--quiet", "--done", input_bytes=fixture_stream())
    git("reset", "--quiet", "--hard", "HEAD")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="new repository directory")
    create_fixture(parser.parse_args().path)
