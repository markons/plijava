# plijava

PLIJAVA is a lightweight PL/I → Java transpiler and runner. It uses PLY (Python Lex-Yacc) to parse a useful subset of PL/I, emits Java source, optionally formats and compiles the generated code with `javac`, and can execute the resulting class. The project is a proof-of-concept and learning tool rather than a full PL/I implementation.

This repository includes:
- `plijava.py` — main transpiler (lexer, parser, code generator, and runner)
- `pl1code/` — example PL/I programs used as tests
- `javalib/` — precompiled Java runtime helpers (`DriverShim`, `PliJavaRuntime`, `RndRuntime`)
- `run.py` — small wrapper for non-interactive runs
- `requirements.txt` — Python dependencies
- `tests/` — pytest-based tests and example inputs

**Quick summary**
- Language: Python 3.x with PLY
- Target: Java (requires JDK)
- Primary intent: education / experimentation

## Features

- Parse PL/I `proc` programs and many common declarations (`dcl`, arrays, records)
- Translate statements: assignments, arithmetic, `if`, `do` loops (`while` and from..to), `select/when`, `put skip list` (console output), `get list` (console input)
- One- and two-dimensional arrays (integer indexing only)
- Basic record (level) declaration support (generates simple Java fields/arrays)
- `exec sql "..." into var;` — executes a SQL statement via `PliJavaRuntime` and assigns the first-row first-column result to a variable (supports MySQL and Db2 via JDBC)
- Generates Java helper usage for random numbers (`RndRuntime`) and JDBC driver loading (`DriverShim`) via the `javalib` classpath
- Optional formatting of generated Java with `astyle.exe` (skipped if not installed)

## Requirements

- Python 3.8+
- `ply` (install via `pip install -r requirements.txt`)
- A Java Development Kit (JDK) — `javac` and `java` should be on `PATH` or `JAVA_HOME` set
- JDBC driver(s) for database access when using `exec sql` (MySQL / Db2)
- Optional: `astyle.exe` for Java formatting

## How it works (high level)

1. `plijava.py` builds a PLY lexer and LALR(1) parser that walks PL/I source and emits Java source strings.
2. The script writes the Java source to `<ClassName>.java`, optionally formats it with `astyle.exe`, then compiles with `javac` using a classpath that includes the `javalib` helpers.
3. If compilation succeeds the produced class is executed with `java` and the program output is printed.

## Running the transpiler

- Interactive (file dialog):

```powershell
python plijava.py
```

- Non-interactive (useful for scripts / CI): set `PLIJAVA_INPUT_FILE` or use `run.py`:

```powershell
python run.py --input pl1code/simple.pli
```

## Environment variables

- `PLIJAVA_INPUT_FILE` — path to PL/I file to transpile (skips file dialog)
- `PLIJAVA_CREDS_FILE` — path to credentials file for SQL operations (falls back to `c:/temp/creds.txt`)
- `PLIJAVA_DEBUG` — set to `1` or `true` to enable debug logging
- `JAVA_HOME` / `JDK_HOME` — used to resolve `javac`/`java` if not on `PATH`

## Credentials file format (for `exec sql`)

The runtime will read credentials via `PliJavaRuntime.parseCredentials()` from the file at `PLIJAVA_CREDS_FILE` or `c:/temp/creds.txt` by default. The expected format is a single comma-separated record, for example:

```
host="localhost", user="root", password="secret", database="sakila", dbsys="mysql", jdbc_path="C:/path/to/mysql-connector.jar", port="3306"
```

## Known limitations and bugs

This project is a work-in-progress. Selected limitations recorded in `plijava.py` include:

- Grammar conflicts (reduce/reduce) in some declaration/expression rules — may mis-parse edge cases
- Some token/regex issues in the lexer (dead/duplicate token definitions)
- `substr`/string handling edge cases in generated Java (single-argument `substr` fixed to `substring(start)`)
- SQL support returns only the first column of the first row; multi-row/multi-column queries are not supported
- `get list()` type inference relies on prior declarations and may fail if `dcl` appears later
- No support for PL/I ON conditions, PICTURE, BASED/POINTER, ENTRY declarations, or BY in DO FROM/TO

See the top-of-file comments in `plijava.py` for a fuller list of known issues and version notes.

## Tests

Run the test suite with:

```powershell
pytest -q
```

Tests exercise parsing and, when `javac` is available, attempt to compile generated Java code.

## Development notes

- The Java helper classes reside in `javalib/` and must be available on the classpath when compiling/executing generated code.
- `plijava.py` uses `tkinter` for the interactive file picker; non-interactive runs should set `PLIJAVA_INPUT_FILE`.
- Logging is controlled through `PLIJAVA_DEBUG` — set to `1` to enable detailed debug output.

## License

Provided as-is for educational and experimental use.

---

File generated/updated from `plijava.py` on update.
