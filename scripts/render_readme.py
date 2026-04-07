#!/usr/bin/env python3

import os
import tempfile
import shutil

TPL_PATH    = os.getenv("TPL_PATH", "README.md.tpl")
README_PATH = os.getenv("README_PATH", "README.md")


def main():
    with open(TPL_PATH, "r", encoding="utf-8") as f:
        tpl_content = f.read()

    # atomic write
    dir_name = os.path.dirname(README_PATH) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_name, encoding="utf-8") as tmp:
        tmp.write(tpl_content)
        temp_name = tmp.name

    shutil.move(temp_name, README_PATH)

    print("[render] README updated atomically")


if __name__ == "__main__":
    main()