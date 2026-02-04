import os
import subprocess
import sys


def run(cmd: str) -> None:
    print(f"> {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    version_file = os.path.join(".git", "version.txt")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            line = f.readline().strip()
            n = int(line) + 1 if line.isdigit() else 1
    else:
        n = 1

    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(str(n))

    run("git add .")
    run(f'git commit -m "v{n}"')
    run("git push origin master")


if __name__ == "__main__":
    main()
