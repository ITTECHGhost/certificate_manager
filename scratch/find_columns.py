import os

def check_file(filepath, out_f):
    keywords = ["admission_year", "graduation_year", "postgraduation_no", "postgraduation_number"]
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            for kw in keywords:
                if kw in line:
                    out_f.write(f"{filepath}:{idx} [{kw}]: {line.strip()}\n")

def main():
    exclude_dirs = {".git", ".vscode", "__pycache__", "venv", ".gemini", "scratch"}
    with open("scratch/search_results.txt", "w", encoding="utf-8") as out_f:
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file.endswith(".py"):
                    check_file(os.path.join(root, file), out_f)

if __name__ == "__main__":
    main()
