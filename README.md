# plijava — v2.00

PLIJAVA is a lightweight PL/I → Java transpiler and runner. It uses PLY (Python Lex-Yacc) to parse a useful subset of PL/I, emits Java source, optionally formats and compiles the generated code with `javac`, and can execute the resulting class. The project is a proof-of-concept and learning tool rather than a full PL/I implementation.

This repository includes:
- `plijava.py` — main transpiler (lexer, parser, code generator, and runner)
- `plijava_wrapper.py` — non-interactive wrapper (used by the test runner)
- `pl1code/` — example PL/I programs used as tests
- `javalib/` — precompiled Java runtime helpers (`DriverShim`, `PliJavaRuntime`, `RndRuntime`)
- `run_tests.py` — test runner; produces a Word report in `c:/temp/`
- `show_side_by_side.py` — GUI side-by-side PL/I → Java viewer
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

## Implemented PL/I features

The following PL/I constructs are implemented (as observed in `plijava.py`) and translated into Java by the transpiler:

- Program structure: `name: proc options(main); ... end name;`
- Declarations: `dcl var fixed bin(n)` (int/long), `dcl var char(n)`, 1-D and 2-D arrays, and simple record (level) declarations
- Assignments: `var = expression;`
- Conditionals: `if <relational> then <stmt> else <stmt>;` (supports `do; ... end;` blocks)
- Selection: `select(expr); when(value) stmt; other stmt; end;` (translates to Java `if/else if/else` style)
- Loops: `do while(cond); ... end;` and counted loops `do i = start to end; ... end;`
- Blocked `do ... end` groups (treated as braced blocks in generated Java)
- Console I/O: `put skip list(...)` → `System.out.println(...)`; `get list(var, ...)` → `Scanner` reads with type handling
- Function/procedure support: `name: proc(params) returns(type);` and `name: proc(params);` — parameter type inference from `dcl`; pass-by-reference emulated via single-element arrays
- Calls: `call subname(args);` — call-site transformation wraps arguments for reference semantics as needed
- Returns: `return(expr);` for returning values from functions
- Built-ins: `substr`, `index`, `decimal`, `mod`, `random`, string concatenation (`||`) — mapped to Java `substring`, `indexOf+1`, `String.valueOf`, `%`, `RndRuntime`, and `+` respectively
- **v2.00 built-ins** (Claude Code): `length`, `trim`, `lowercase`, `uppercase`, `repeat`, `reverse`, `abs`, `sqrt`, `ceil`, `floor`, `round`, `trunc`, `sign`, `max`, `min`, `date`, `time` — dispatched to the equivalent Java expression via a built-in table
- **v2.00 control flow** (Claude Code): `leave` → `break`, `iterate` → `continue`, `stop` → `System.exit(0)`, `do ... by <step>` (positive or negative literal step)
- **v2.00 declarations** (Claude Code): `dcl ... init(value)` initializer; `bit(n)` type mapped to Java `boolean` (init `'1'` → `true`)
- **v2.00 ON ENDFILE handler** (Claude Code): `on endfile('fname') stmt;` registers a handler; subsequent `read file('fname') into(var);` is wrapped in a null-check that runs the handler on EOF
- File I/O: `open file('name') input|output;`, `read file('name') into(var);`, `write file('name') from(var);`, `close file('name');` — mapped to Java I/O (`BufferedReader`, `PrintWriter`)
- SQL: `exec sql "..." into var;` — runtime uses `PliJavaRuntime` to parse credentials and execute a JDBC query, assigning the first-column result
- Runtime helpers: integration with `javalib` classes (`DriverShim`, `PliJavaRuntime`, `RndRuntime`) for JDBC/random utilities

Refer to `plijava.py` top comments and parser rules for more details and edge-cases.

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

- Non-interactive via wrapper (used by the test runner):

```powershell
python plijava_wrapper.py tests/test01_basic.pli
```

- Run the full test suite and produce a Word report:

```powershell
python run_tests.py
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
- No support for PICTURE, BASED/POINTER, or ENTRY declarations
- ON conditions: only `ENDFILE` is implemented (v2.00); `ERROR`, `KEY`, `UNDEFINEDFILE` etc. are not supported
- Every `if-then` requires an explicit `else` branch (use `else x = x;` as a no-op when needed)
- No unary minus on literals — write `0 - 7` instead of `-7`
- `put list(...)` elements must be variables, numbers or string literals — assign function-call results to a variable first
- `write file('f') from(...)` requires an ID; assign string literals to a variable first

See the top-of-file comments in `plijava.py` for a fuller list of known issues and version notes.

## Changelog

| Version | Date | Summary |
|---------|------|---------|
| v2.00 | 2026-04-22 | **Claude Code release.** Adds `LEAVE` / `ITERATE` / `STOP`, `BY` clause on `DO FROM/TO`, `INIT(value)` on `DCL`, `BIT(n)` → Java `boolean`, `ON ENDFILE` handlers, and 17 new built-in functions (`length`, `trim`, `lowercase`, `uppercase`, `repeat`, `reverse`, `abs`, `sqrt`, `ceil`, `floor`, `round`, `trunc`, `sign`, `max`, `min`, `date`, `time`). 10 new tests (test20–test29); full suite passes 29/29. |
| v1.04 | 2026-04-19 | Fix wrapper path (was hard-coded to `F:\plijava`); fix file I/O variable naming (`in_`/`out_` per handle type) so a file can be opened for output then re-opened for input without a Java redeclaration error |
| v1.03 | 2025-04-06 | Internal procedures, DO FROM/TO, RANDOM, record dcl, array/function-call disambiguation, RndRuntime, optional astyle |
| v1.02 | 2024 | GitHub baseline |
| v1.01 | 2024-11-05 | Initial fork from plithon |

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

## Side-by-side viewer

A simple GUI tool is included to compare the original PL/I source and the generated Java code visually:

- `show_side_by_side.py` — run it with `--pli` and `--java` paths, or open files from the GUI.

Example:

```powershell
python show_side_by_side.py --pli pl1code/simple.pli --java MyProgram.java
```

## License

Provided as-is for educational and experimental use.

---

v2.00 — 2026-04-22 (Claude Code)
