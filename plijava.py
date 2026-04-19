"""
================================================================================
 plijava.py  -  PL/I to Java Transpiler                              v1.03
================================================================================
 A fork of the plithon PL/I-to-Python transpiler, retargeted to Java.
 Uses PLY (Python Lex-Yacc) for lexical analysis and LALR(1) parsing.

 Author  : maga1
 Created : 2024-11-05
 Updated : 2025-04-06
 Platform: Python 3.x + PLY + JDK (tested with Semeru JDK 26)
 IDE     : Python Spyder (debug prints active; set blockPrint() to suppress)

--------------------------------------------------------------------------------
 USAGE
--------------------------------------------------------------------------------
 1. Run the script.
 2. Select a .pli file in the file dialog that opens.
 3. The transpiler parses the PL/I source and generates a Java source file
    named after the PL/I main procedure (e.g. testret.java).
 4. The Java file is compiled with javac and executed automatically.
 5. Output is printed to the console.

 Configuration (hardcoded — update for your environment):
   JAVA_HOME : C:\\Program Files\\Semeru\\jdk-26.0.0.35-openj9
   SQL creds : c:/temp/creds.txt  (keys: dbsys, jdbc_path, port, host,
                                         user, password, database)

--------------------------------------------------------------------------------
 DEPENDENCIES
--------------------------------------------------------------------------------
   pip install ply python-docx
   JDK in JAVA_HOME (javac + java must be reachable)
   astyle.exe (optional — pretty-prints generated Java; skipped if absent)

--------------------------------------------------------------------------------
 SUPPORTED PL/I CONSTRUCTS
--------------------------------------------------------------------------------
  Program structure
    programname: proc options(main);
      ...statements...
    end programname;

  Declarations
    dcl var fixed bin(15|31);          scalar integer (int / long)
    dcl var char(n);                   scalar string
    dcl var(n) fixed bin(15|31);       1-D integer array
    dcl var(n,m) fixed bin(15|31);     2-D integer array
    dcl var(n) char(len);              1-D string array
    dcl 1 recname, 2 field type, ...;  record (generates inner class)

  Statements
    var = expression;                  assignment
    if cond then stmt else stmt;       conditional (with do;...end; blocks)
    select(expr); when(v) stmt; other stmt; end;   case/switch
    do while(cond); ...stmts... end;   while loop
    do var = start to end; ...end;     counted for loop
    put skip list(expr, ...);          console output  -> System.out.println
    get list(var, ...);                console input   -> scanner.nextInt/Line
    call subname(args);                subroutine call
    return(expr);                      function return

  Internal procedures
    name: proc(params) returns(type);  typed function
    name: proc(params);                void procedure
    name: proc() returns(type);        no-arg function
    name: proc();                      no-arg void procedure
    Parameter types are inferred from the dcl statements inside the proc.

  Built-in functions
    substr(var, start, len)            -> String.substring()
    index(var, 'char')                 -> String.indexOf() + 1
    decimal(var)                       -> String.valueOf()
    mod(var, n)                        -> var % n
    random() / random(n)               -> RndRuntime.random()
    expr || expr                       string concatenation -> Java +

  File I/O
    open file('name') input;           -> BufferedReader
    open file('name') output;          -> PrintWriter
    read file('name') into(var);       -> readLine()
    write file('name') from(var);      -> println()
    close file('name');                -> close()

  Database (exec sql)
    exec sql "SELECT col FROM tbl" into var;
    Supported: MySQL, Db2 LUW.  Credentials read from c:/temp/creds.txt.
    Result always fetched as first column of first row (String/int/long).

  Java helpers generated automatically
    DriverShim   — JDBC driver loader via URLClassLoader
    RndRuntime   — wrapper for java.util.Random

--------------------------------------------------------------------------------
 KNOWN BUGS / FAILING FEATURES
--------------------------------------------------------------------------------
  [PARSER]
  - declaration_list grammar is both left- and right-recursive, causing
    LALR(1) reduce/reduce conflicts. Declarations inside internal
    procedures may be mis-parsed in edge cases.
  - expression rule contains a bare '| ID' alternative that duplicates
    variable_access, leading to reduce/reduce conflicts.
  - t_FILENAME defined but FILENAME not in tokens tuple -> PLY LexError
    at startup.  (t_FILENAME is dead code; should be removed.)
  - VARYING in reserved dict but not in tokens tuple -> token error if
    'varying' appears in source.
  - EQUALS token (r'=') duplicates ASSIGN (r'='); EQUALS is unreachable.

  [CODE GENERATION]
  - SUBSTR with single argument generates .substring(n:) — Python slice
    syntax, not valid Java.  Fix: use .substring(n).
  - exec sql assignment generates a double semicolon:
      var = Integer.parseInt(result);;
  - p_block_comment_statement uses p[0] instead of p[1]; block comment
    text is lost in output.
  - put skip list() elements are joined with '+' only — no spaces added
    between numeric/string values in the output.
  - SQL result: only the first column of the first row is returned.
    Multi-column / multi-row queries are not supported.

  [LIMITATIONS]
  - Only integer array indexing supported (no expression indices).
  - do-from-to loop: no BY clause (step always 1).
  - No PL/I ON conditions (error / endfile handling).
  - No PICTURE variables.
  - No BASED or POINTER variables.
  - No ENTRY declarations.
  - get list() type detection relies on previously seen dcl output;
    may fail if dcl appears after get in the source.

--------------------------------------------------------------------------------
 VERSION HISTORY
--------------------------------------------------------------------------------
  v1.04  2026-04-19  Fix plijava_wrapper.py: removed hard-coded F:\plijava paths,
                     now resolves the wrapper's own directory at runtime so the
                     correct plijava.py is always used and javac errors reference
                     the real project path.
                     Fix file I/O: use separate in_<name>/out_<name> handles for
                     input (BufferedReader) and output (PrintWriter) so the same
                     file can be opened for output then input without a variable
                     redeclaration error.
  v1.03  2025-04-06  Internal procedures, DO FROM/TO, RANDOM, record dcl,
                     array/function-call disambiguation, RndRuntime class,
                     javac path fix, JDK path updated to Semeru JDK 26,
                     astyle call made optional.
  v1.02  2024-xx-xx  GitHub baseline (markons/plijava).
  v1.01  2024-11-05  Initial fork from plithon.
================================================================================
"""

# Now you can set up your PLY parser
import ply.lex as lex
import ply.yacc as yacc
import sys, os
from datetime import datetime

# Directory that contains the pre-compiled plijava runtime helpers:
#   DriverShim.class, RndRuntime.class, PliJavaRuntime.class
# Adjust this path if you move the javalib folder.
JAVALIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__))
                           if '__file__' in globals() else os.getcwd(),
                           'javalib')
import logging

# Configure logging. Set debug when PLIJAVA_DEBUG=1
log_level = logging.DEBUG if os.environ.get("PLIJAVA_DEBUG") in ("1", "true", "True") else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger("plijava")

level=1 #irrelevant, must be deleted

procedure_name = ""

# Getting the current date and time
dt = datetime.now()
# getting the timestamp
ts = datetime.timestamp(dt)
logger.info('start at: %s', dt)

# Feature usage flags (set by parser actions)
uses_sql = False
uses_random = False
uses_scanner = False
uses_fileio = False
uses_map = False
uses_urlclassloader = False
file_open_modes = {}  # fname -> 'input'|'output', tracks last open mode for close

# List of token names
tokens = (
    'ID', 'INDEXED_ID', 'NUMBER', 'CHAR_CONST', 'ASSIGN',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
    'LPAREN', 'RPAREN', 'LT', 'GT', 'LE', 'GE', 'EQ', 'NE',
    'COLON', 'SEMICOLON', 'COMMA',
    'PUT', 'SKIP', 'LIST', 'END', 'WHEN', 'OTHER', 'SELECT', 'DO', 'WHILE',
    'PROC', 'OPTIONS', 'MAIN', 'DCL', 'FIXED', 'BIN', 'CHAR',
    'IF', 'THEN', 'ELSE', 'BLOCK_COMMENT', 'SUBSTR', 'CONCAT','DECIMAL','MOD',
    'EXEC', 'SQL', 'INTO', 'STRING', 'INDEX', 'GET',
    'OPEN','CLOSE','READ','WRITE','FILE','FROM','MODE','INPUT','OUTPUT',
    'LEVEL_1','LEVEL_2', 'RECORD_BEGIN','RECORD_END','CALL', 'RANDOM', 'TO',
    'EQUALS', 'RETURNS', 'RETURN'
)

# Regular expression rules for tokens
t_PLUS = r'\+'
t_MINUS = r'-'
t_TIMES = r'\*'
t_DIVIDE = r'/'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_ASSIGN = r'='
t_LT = r'<'
t_GT = r'>'
t_LE = r'<='
t_GE = r'>='
t_EQ = r'=='
t_NE = r'<>'
t_COLON = r':'
t_SEMICOLON = r';'
t_COMMA = r','
t_CONCAT = r'\|\|'
t_EXEC = r'EXEC'
t_SQL = r'SQL'
t_INTO = r'INTO' 
t_RANDOM = r'random'
t_EQUALS = r'='
 

# Reserved keywords
reserved = {
    'proc': 'PROC',
    'options': 'OPTIONS',
    'main': 'MAIN',
    'dcl': 'DCL',
    'fixed': 'FIXED',
    'bin': 'BIN',
    'char': 'CHAR',
    'varying': 'VARYING',
    'if': 'IF',
    'then': 'THEN',
    'else': 'ELSE',
    'put': 'PUT',
    'get': 'GET',
    'skip': 'SKIP',
    'list': 'LIST',
    'end': 'END',
    'when': 'WHEN',
    'other': 'OTHER',
    'select': 'SELECT',
    'do': 'DO',
    'while': 'WHILE',  
    'substr': 'SUBSTR',  
    'index': 'INDEX',
    'mod': 'MOD',
    'into': 'INTO',
    'exec': 'EXEC',
    'sql': 'SQL',
    'open': 'OPEN',
    'close': 'CLOSE',
    'read': 'READ',
    'write': 'WRITE',
    'file': 'FILE',
    'input': 'INPUT',
    'output': 'OUTPUT',
    'from': 'FROM',
    'decimal': 'DECIMAL',  
    'call': 'CALL',
    'random': 'RANDOM',
    'to': 'TO',
    'returns': 'RETURNS',
    'return': 'RETURN',
}

JAVA_RESERVED = {
    'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
    'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
    'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
    'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
    'package', 'private', 'protected', 'public', 'return', 'short', 'static',
    'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
    'transient', 'try', 'void', 'volatile', 'while',
}

def safe_java_id(name):
    """Append underscore if name collides with a Java reserved word."""
    return name + '_' if name.lower() in JAVA_RESERVED else name

# Disable print
def blockPrint():
    sys.stdout = open(os.devnull, 'w')

# Restore print 
def enablePrint():
    sys.stdout = sys.__stdout__

# Disable print for production version
#blockPrint()

#  Identifiers (variables)
def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'   
    # print('in ID:', t, flush=True)
    t.type = reserved.get(t.value.lower(), 'ID')  # Check for reserved words     
    # print('end ID:', t.type, flush=True)
    return t

# Numbers
def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

# Character constants (strings in single quotes will be changed to apostrophes)
def t_CHAR_CONST(t):
    r"\'([^\\\n]|(\\.))*?\'"
    #print('in char_const:', t, flush=True)
    # Remove outer single quotes, replace inner single quotes with double quotes, and wrap the result in double quotes
    #t.value = '"' + t.value[1:-1].replace("'", '"') + '"'
    t.value = t.value.replace("'", '"')
    # print('end char_const:', t.value, flush=True)
    return t

# file name (strings in single quotes)
def t_FILENAME(t):
    r"\'([^\\\n]|(\\.))*?\'"
    logger.debug('in filename: %s', t)
    logger.debug('in filename: %s', t)
    return t





def build_imports_and_globals():
    """Return (imports, globals) strings based on which features are used."""
    imports = []
    globals_code = []

    if uses_fileio:
        imports.append('import java.io.FileNotFoundException;')
        imports.append('import java.io.IOException;')
        imports.append('import java.io.BufferedReader;')
        imports.append('import java.io.FileReader;')
        imports.append('import java.io.PrintWriter;')

    if uses_sql:
        imports.append('import java.sql.*;')
        imports.append('import java.net.MalformedURLException;')
        if not uses_fileio:
            imports.append('import java.io.IOException;')

    if uses_map or uses_sql:
        imports.append('import java.util.Map;')
        imports.append('import java.util.HashMap;')

    if uses_scanner:
        imports.append('import java.util.Scanner;')

    if uses_random:
        imports.append('import java.util.Random;')

    if uses_urlclassloader:
        imports.append('import java.net.URL;')
        imports.append('import java.net.URLClassLoader;')

    # Build globals only for features actually used
    if uses_sql:
        globals_code.append('String dbsys = "";')
        globals_code.append('String jdbc_path = "";')
        globals_code.append('String port = "";')
        globals_code.append('String host = "";')
        globals_code.append('String user = "";')
        globals_code.append('String password = "";')
        globals_code.append('String dbName = "";')
        globals_code.append('String sql_statement = "";')
        globals_code.append('String result = "";')
        globals_code.append('String filePath = "";')
        globals_code.append('Map<String, String> credentials;')

    if uses_scanner:
        globals_code.append('Scanner scanner = new Scanner(System.in);')

    if globals_code:
        globals_block = '\n                 // ---- generated runtime variables -------------------------\n                 ' + '\n                 '.join(globals_code) + '\n                 // ---- end generated variables ---------------------------------\n'
    else:
        globals_block = ''

    imports_str = '\n'.join(imports)
    return imports_str, globals_block

# RndRuntime and DriverShim are now in javalib/RndRuntime.java and
# javalib/DriverShim.java — compiled once, referenced via classpath.
# These variables are kept as empty strings so existing code that
# references them does not break.
random_class     = ''
drivershim_class = ''

# sql_methods and read_creds are now in javalib/PliJavaRuntime.java.
# Generated Java calls PliJavaRuntime.executeQuery() and
# PliJavaRuntime.parseCredentials() via classpath.
sql_methods = ''
read_creds  = ''
       
global_strings = '''
                 // ---- standard variables (always generated) -------------------------
                 // Database connection parameters (filled by PliJavaRuntime at runtime)
                 String dbsys      = "";   // database system: "db2" or "mysql"
                 String jdbc_path  = "";   // path to JDBC driver .jar
                 String port       = "";   // database port
                 String host       = "";   // database host name or IP
                 String user       = "";   // database user
                 String password   = "";   // database password
                 String dbName     = "";   // database / schema name
                 // General-purpose runtime variables
                 String filePath   = "";   // path to credentials file (c:/temp/creds.txt)
                 String result     = "";   // receives the SQL query result string
                 Map<String, String> credentials;          // parsed credential map
                 Scanner scanner = new Scanner(System.in); // console input (GET LIST)
                 String sql_statement = "";                // current SQL statement
                 // ---- end standard variables -----------------------------------------\n
                 '''        

# Ignored characters (spaces and tabs)
t_ignore = ' \t'

# Block comment
def t_BLOCK_COMMENT(t):
    r'/\*([^*]|\*+[^*/])*\*+/'
    #return t
    pass  # Block comments are ignored

# Newline rule
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Error handling rule
def t_error(t):
    logger.error("Illegal character '%s'", t.value[0])
    t.lexer.skip(1)
    
    
# Recognize string literals with single or double quotes
#t_CHAR_CONST = r"\'([^\\']|\\.)*\'"   # Single-quoted strings
t_STRING = r'\"([^\\"]|\\.)*\"'       # Double-quoted strings for SQL    
    
# Build the lexer
lexer = lex.lex()


def indent_block(code, level=1, is_function=False):
    """
    Creates a block of code with indentation based on the level and whether it's within a function.

    Args:
        code: The code string to be indented.
        level: The indentation level (defaults to 1).
        is_function: Whether the code is within a function definition (defaults to False).

    Returns:
        The indented code string.
    """
    indent = "  " * level    
    lines = code.splitlines()
    indented_lines = [] 
    for line in lines:
        indented_lines.append(indent + line)
    return "\n".join(indented_lines)

# Print parsing rules for trace
def print_tokens(input_text):
    lexer.input(input_text)
    while True:
        token = lexer.token()
        if not token:
            break
        logger.debug('token: %s', token)

# PL/I program: progname:proc options(main);<declares> <execs> end progname;
def p_program(p):
    '''program : procedure_header declaration_list statement_list END ID SEMICOLON external_proc_list
               | procedure_header declaration_list statement_list END ID SEMICOLON'''
    logger.debug('in program: p values: %s', p[:])

    global procedure_name
    procedure_name = p[5]

    # Process declarations
    declarations = "\n".join(p[2]) if p[2] else ""
    declarations = indent_block(declarations, 2)

    # Separate internal procedures from main procedure statements
    statements = []
    internal_procs = []
    for stmt in p[3]:
        if stmt.startswith("public static "):  # Check for internal procedures (void, int, long, String)
            internal_procs.append(stmt)
        else:
            statements.append(stmt)

    statements = "\n".join(statements) if statements else ""
    statements = indent_block(statements, 2)

    # Collect external procedures (defined after END mainprog;)
    external_procs = p[7] if len(p) == 8 else []

    # All feature flags are now set — resolve sentinels in the header
    imports_str, globals_block = build_imports_and_globals()
    throws_list = []
    if uses_fileio:
        throws_list += ['FileNotFoundException', 'IOException']
    if uses_sql:
        if 'IOException' not in throws_list:
            throws_list.append('IOException')
        throws_list.append('MalformedURLException')
    throws_clause = f" throws {', '.join(throws_list)}" if throws_list else ""
    header = p[1]
    header = header.replace('%%IMPORTS%%', imports_str + "\n" if imports_str else "")
    header = header.replace('%%SQLMETHODS%%', sql_methods + "\n" if sql_methods else "")
    header = header.replace('%%READCREDS%%', read_creds + "\n" if read_creds else "")
    header = header.replace('%%THROWS%%', throws_clause)
    header = header.replace('%%GLOBALS%%', globals_block + "\n" if globals_block else "")

    # Generate main procedure code
    main_code = f"{header}\n{declarations}\n{statements}\n}}"

    # Add all procedures (internal + external) to the output
    all_procs = internal_procs + (external_procs or [])
    internal_code = "\n".join(all_procs)

    # Final class structure: include helper classes only when used
    tail = ""
    if drivershim_class and (uses_sql or uses_urlclassloader):
        tail += drivershim_class + "\n"
    if random_class and uses_random:
        tail += random_class + "\n"

    # Final class
    p[0] = (
        f"{main_code}\n"
        f"{internal_code}\n"
        f"{tail}"
        f"}} //end class {procedure_name}\n"
    )

    logger.debug('end program:\n%s', p[0])


def p_external_proc_list(p):
    '''external_proc_list : external_proc_list proc_statement
                          | proc_statement'''
    logger.debug('in external_proc_list: p values: %s', p[:])
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

    
# Procedure header and its syntax
def p_procedure_header(p):
    '''procedure_header : ID COLON PROC OPTIONS LPAREN MAIN RPAREN SEMICOLON'''
    logger.debug('in procedure_header: p values: %s', p[:])
    # Use sentinels — features flags are not fully set yet (body not parsed).
    # p_program will replace these after full parsing.
    p[0] = f"%%IMPORTS%%public class {p[1]} {{ \n%%SQLMETHODS%%%%READCREDS%%public static void main(String[] args)%%THROWS%% {{%%GLOBALS%%"
    logger.debug('end procedure_header result: p values: %s', p[:])    
    
def p_proc_statement(p):
    '''proc_statement : proc_header declaration_list statement_list END SEMICOLON
                      | proc_header declaration_list statement_list END ID SEMICOLON'''
    logger.debug('in proc_statement: p values: %s', p[:])

    # p[1] is now a tuple (header_string, param_names_list)
    header_str, param_names = p[1]

    # Filter out declarations that redeclare parameters, and collect their types
    param_types = {}
    filtered_decls = []
    if p[2]:
        for decl in p[2]:
            is_param_decl = False
            for param in param_names:
                for java_type in ("String", "long", "int"):
                    if f"{java_type} {param} = " in decl:
                        is_param_decl = True
                        param_types[param] = java_type
                        logger.debug("Filtering out parameter redeclaration (%s): %s", java_type, decl)
                        break
                if is_param_decl:
                    break
            if not is_param_decl:
                filtered_decls.append(decl)

    declarations = "\n".join(filtered_decls) if filtered_decls else ""
    statements = "\n".join(p[3]) if p[3] else ""

    is_void = "void" in header_str and bool(param_names)

    if is_void:
        # Pass-by-reference: parameters become type[] arrays; body uses local copies
        ref_params = ", ".join(
            f"{param_types.get(param, 'long')}[] _{param}" for param in param_names
        )
        import re
        header_str = re.sub(r'\([^)]*\)', f'({ref_params})', header_str, count=1)
        logger.debug("Rebuilt void header with ref params: %s", header_str)

        # Local copies from ref arrays at procedure entry
        local_copies = "\n".join(
            f"{param_types.get(param, 'long')} {param} = _{param}[0];"
            for param in param_names
        )
        # Copy-back to ref arrays at procedure exit
        copy_back = "\n".join(
            f"_{param}[0] = {param};"
            for param in param_names
        )
        p[0] = f"{header_str}\n{local_copies}\n{declarations}\n{statements}\n{copy_back}\n}}\n"
    else:
        # Value-returning proc: rebuild header with correct param types from DCL
        if param_names:
            correct_params = ", ".join(
                f"{param_types.get(param, 'int')} {param}" for param in param_names
            )
            import re
            header_str = re.sub(r'\([^)]*\)', f'({correct_params})', header_str, count=1)
            logger.debug("Rebuilt header with correct param types: %s", header_str)
        p[0] = f"{header_str}\n{declarations}\n{statements}\n}}\n"

def p_proc_header(p):
    '''proc_header : ID COLON PROC LPAREN parameter_list RPAREN RETURNS LPAREN type_declaration RPAREN SEMICOLON
                   | ID COLON PROC LPAREN RPAREN RETURNS LPAREN type_declaration RPAREN SEMICOLON
                   | ID COLON PROC LPAREN parameter_list RPAREN SEMICOLON
                   | ID COLON PROC LPAREN RPAREN SEMICOLON'''
    logger.debug('in proc_header: p values: %s', p[:])

    param_names = []  # List of parameter names

    method_name = safe_java_id(p[1])
    if len(p) == 12:  # With parameters and RETURNS
        java_parameters = convert_to_java_parameters(p[5])
        java_return_type = pli_type_to_java(p[9])
        header_str = f"public static {java_return_type} {method_name}({java_parameters}) {{"
        # Extract parameter names from p[5]
        param_names = [param.strip() for param in p[5].split(',')]
    elif len(p) == 11:  # No parameters but with RETURNS
        java_return_type = pli_type_to_java(p[8])
        header_str = f"public static {java_return_type} {method_name}() {{"
    elif len(p) == 8:  # With parameters, no RETURNS
        java_parameters = convert_to_java_parameters(p[5])
        header_str = f"public static void {method_name}({java_parameters}) {{"
        # Extract parameter names from p[5]
        param_names = [param.strip() for param in p[5].split(',')]
    else:  # No parameters, no RETURNS
        header_str = f"public static void {method_name}() {{"

    # Return tuple of (header_string, param_names_list)
    p[0] = (header_str, param_names)
    logger.debug("proc_header returning: %s", p[0])

def pli_type_to_java(pli_type):
    """Converts a PL/I type declaration to a Java type."""
    logger.debug('in pli_type_to_java: %s', pli_type)
    if pli_type is None:
        return "int"
    pli_type_upper = pli_type.upper()
    if "CHAR" in pli_type_upper:
        return "String"
    elif "FIXED BIN" in pli_type_upper:
        # Extract the precision from FIXED BIN(n)
        import re
        match = re.search(r'\((\d+)\)', pli_type)
        if match:
            precision = int(match.group(1))
            if precision > 15:
                return "long"
        return "int"
    return "int"  # Default to int
        
def convert_to_java_parameters(pl1_params):
    """
    Converts a PL/I parameter list into Java-style type declarations.
    Example:
    Input: "x, y"
    Output: "int x, int y"
    """
    logger.debug('in convert_to_java_parameters: %s', pl1_params)
    if not pl1_params:
        return ""  # No parameters

    # Assume all parameters are integers for simplicity; modify if needed
    java_params = [f"int {param.strip()}" for param in pl1_params.split(',')]
    return ", ".join(java_params)
        
   
def p_parameter_list(p):
    '''parameter_list : parameter_list COMMA expression
                      | expression'''
    logger.debug('in parameter_list: p values: %s', p[:])                                    
    if len(p) == 4:  # Multiple parameters
        p[0] = f"{p[1]}, {p[3]}"
    else:  # Single parameter
        p[0] = p[1]                
        
def p_parameter(p):
    '''parameter : ID
                 | ID type_declaration'''
    logger.debug('in parameter: p values: %s', p[:])                
    if len(p) == 2:
        p[0] = f"int {p[1]}"  # Default to int
    else:
        p[0] = f"{p[2]} {p[1]}"
        
        
def p_variable_access(p):
    """
    variable_access : ID LPAREN NUMBER COMMA NUMBER RPAREN
                   | ID LPAREN ID COMMA ID RPAREN
                   | ID LPAREN ID COMMA NUMBER RPAREN
                   | ID LPAREN NUMBER RPAREN
                   | ID LPAREN ID RPAREN
                   | ID
    """

    #| ID LPAREN NUMBER COMMA NUMBER RPAREN ASSIGN expression
    logger.debug('in variable_access p values: %s', p[:])
    logger.debug('len(p) %d', len(p))

    # Check if this is an array access or a function call
    is_array = p[1] in declared_arrays
    logger.debug('is_array check: %s in declared_arrays = %s', p[1], is_array)

    if len(p) == 7:  # Two-dimensional access
        if is_array:
            p[0] = f"{p[1]}[{p[3]}][{p[5]}]"
        else:
            p[0] = f"{safe_java_id(p[1])}({p[3]}, {p[5]})"
    elif len(p) == 5:  # One-dimensional access
        if is_array:
            p[0] = f"{p[1]}[{p[3]}]"
        else:
            p[0] = f"{safe_java_id(p[1])}({p[3]})"
    else:
        p[0] = p[1]
    logger.debug('end variable_access: %s', p[0])      
 
all_dcls = ""

#Define an accumulator variable (outside any rule)
all_decls = []

# Track declared arrays to distinguish array access from function calls
declared_arrays = set()

# Track declared variable types for pass-by-reference support at call sites
declared_var_types = {}

def p_declaration_list(p):
    """
    declaration_list : declaration SEMICOLON declaration_list
                     | declaration_list declaration SEMICOLON
                     | declaration SEMICOLON
                     | empty
    """
    logger.debug('in declaration_list: p values: %s', p[:])   
    global all_dcls
    if len(p) == 2:  # empty
        p[0] = []
    elif len(p) == 3:  # Single declaration
        p[0] = [p[1]]
    elif len(p) == 4:  # Appending to list or prepending to list
        if p[1] == p.slice[1].type:  # If p[1] is a list (declaration_list)
            p[0] = p[1] + [p[2]]
        else:
            p[0] = [p[1]] + p[3]  # p[1] is a single declaration, p[3] is the list
            
    all_dcls = ', '.join(p[0])
    logger.debug('all_dcls: %s', all_dcls)

    logger.debug('end all_dcls, p[0]: %s', p[0])
    
def p_declaration(p):
    '''declaration : DCL id_list type_declaration
                   | DCL id_list array_spec type_declaration
                   | DCL NUMBER ID COMMA record_field_list'''
    
    logger.debug('in declaration: p values: %s', p[:])
    logger.debug('len(p): %d', len(p))
    logger.debug('p[1]: %s', p[1]) 
    logger.debug('p[2]: %s', p[2]) 
    logger.debug('p[3]: %s', p[3]) 
    # print("p[4]:", p[4], flush=True) 
 
    if len(p) == 6:  # Record declaration
       record_name = p[3]
       record_fields = p[5]
       decls = [f"class {record_name} {{"]
       for field in record_fields:
           level, field_name, field_type = field
           logger.debug('field_name, field_type: %s %s', field_name, field_type)
           l = variable_length(field_type)
           logger.debug('field_length: %s', l)
           if "CHAR" in field_type:
               #decls.append(f"    public String {field_name};\n")
               decls.append(f"byte[] {field_name} = new byte[{l}];")
           elif "FIXED BIN" in field_type:
               if l <= 15:
                   decls.append(f"    public int {field_name};")  
               else:    
                   decls.append(f"    public long {field_name};")   
       decls.append("}")
       p[0] = "\n".join(decls)     
    else:
       # Handle other types of declarations
       type_str = (p[3] if len(p) == 4 else p[4]) or "FIXED BIN"  # Default to FIXED BIN if type_str is None
       decls = []
       for var in p[2]:  # id_list
           if len(p) == 5:  # Array declaration
               array_spec = p[3]
               # Register this variable as an array
               declared_arrays.add(var)
               logger.debug('Registered array: %s', var)
               if "CHAR" in type_str:
                   if isinstance(array_spec, int):  # One-dimensional CHAR array
                       decls.append(f"String[] {var} = new String[{array_spec + 1}];")
                       decls.append(f"{var}[0] = \" \";")  # Initialize first element with space for String
                   elif isinstance(array_spec, tuple):  # Two-dimensional CHAR array
                       decls.append(f"String[][] {var} = new String[{array_spec[0] + 1}][{array_spec[1] + 1}];")
                       decls.append(f"{var}[0][0] = \" \";")  # Initialize first element with space for String
               else:  # Assuming FIXED BIN for other types
                   if isinstance(array_spec, int):  # One-dimensional int array
                       decls.append(f"int[] {var} = new int[{array_spec + 1}];")
                       decls.append(f"{var}[0] = 0;")  # Initialize first element to 0 for int
                   elif isinstance(array_spec, tuple):  # Two-dimensional int array
                       decls.append(f"int[][] {var} = new int[{array_spec[0] + 1}][{array_spec[1] + 1}];")
                       decls.append(f"{var}[0][0] = 0;")  # Initialize first element to 0 for int
           else:  # Scalar declaration
               if "CHAR" in type_str:
                   decls.append(f'String {var} = "";')
               elif "FIXED BIN" in type_str.upper():
                   # Check precision to determine int vs long
                   precision = variable_length(type_str)
                   if precision is not None and precision > 15:
                       decls.append(f"long {var} = 0;")
                   else:
                       decls.append(f"int {var} = 0;")
               else:
                   decls.append(f"int {var} = 0;")

       p[0] = "\n".join(decls)

       # Track variable types for pass-by-reference call-site generation
       if len(p) != 5:  # Not an array declaration
           for var in p[2]:
               if "CHAR" in type_str:
                   declared_var_types[var] = "String"
               elif "FIXED BIN" in type_str.upper():
                   precision = variable_length(type_str)
                   if precision is not None and precision > 15:
                       declared_var_types[var] = "long"
                   else:
                       declared_var_types[var] = "int"
               else:
                   declared_var_types[var] = "int"

def p_record_field_list(p):
    '''record_field_list : record_field
                         | record_field_list COMMA record_field'''
    logger.debug('in record_field_list: p values: %s', p[:])
    if len(p) == 2:  # Single record field
        p[0] = [p[1]]
    else:  # Add another field to the list
        p[0] = p[1] + [p[3]]
    logger.debug('end record_field_list: %s', p[0])   
    
    
def p_record_field(p):
    '''record_field : NUMBER ID type_declaration
                    | NUMBER ID type_declaration LPAREN NUMBER RPAREN'''
    logger.debug('in record_field: p values: %s', p[:])
    if len(p) == 6:  # For CHAR(n), FIXED BIN(n), etc.
        p[0] = (p[1], p[2], f"{p[3]}({p[5]})")
    else:
        p[0] = (p[1], p[2], p[3])
    logger.debug('end record_field: %s', p[0])    
    
def p_id_list(p):
    '''id_list : ID
               | INDEXED_ID
               | id_list COMMA ID
               | id_list COMMA ID array_spec'''
    logger.debug('in id_list: p values: %s', p[:])             
    if len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 4:  # ID or array spec list (comma separated)
        p[0] = p[1] + [p[3]]
    elif len(p) == 5:  # Handle array spec as part of id_list
        p[0] = p[1] + [f"{p[3]}({p[4]})"]

    
def p_array_spec(p):
    '''array_spec : LPAREN NUMBER RPAREN
                 | LPAREN NUMBER COMMA NUMBER RPAREN'''
    logger.debug('in array_spec: p values: %s', p[:])               
    if len(p) == 4:
        p[0] = (p[2])  # One-dimensional array
    elif len(p) == 6:
        p[0] = (p[2], p[4])  # Two-dimensional array
    
def p_type_declaration(p):
    '''type_declaration : FIXED BIN LPAREN NUMBER RPAREN
                        | CHAR LPAREN NUMBER RPAREN'''
    logger.debug('in type_declaration: p values: %s', p[:])                    
    if len(p) == 6:  # FIXED BIN(n)
        p[0] = f"{p[1]} {p[2]}({p[4]})"
    elif p[1].lower() == 'char':  # CHAR(n)
        p[0] = f"CHAR({p[3]})"    

# returns numeric value between parentheses        
def variable_length(pl1_type):   
    match = re.search(r'\(([\d]+)\)', pl1_type)
    if match:
       return int(match.group(1))
    else:
       return None         

def p_statement_list(p):
    '''statement_list : statement_list statement  
                      | statement     
                      | empty'''
    logger.debug('in statement_list: p values: %s (len: %d)', p[:], len(p))
    
    if len(p) == 3:  # Recursive case: multiple statements
        if isinstance(p[1], list):
            p[0] = p[1] + ([p[2]] if p[2] else [])
        else:
            p[0] = [p[1]] + ([p[2]] if p[2] else [])
    else:
        p[0] = [p[1]] if p[1] else []
    
    logger.debug('end statement_list: %s', p[0])

def p_empty(p):
    'empty :'
    p[0] = None  # Use None to signify an empty production
    

def p_statement(p):
    '''statement : assignment_statement
                 | declaration
                 | if_statement
                 | select_statement
                 | do_while_statement
                 | do_from_to_statement
                 | do_end_block
                 | put_statement
                 | get_list_statement
                 | block_comment_statement
                 | open_file
                 | read_file
                 | write_file
                 | close_file
                 | proc_statement
                 | call_statement
                 | sql_statement
                 | return_statement'''

    logger.debug('in statement: p values: %s', p[:])
    p[0] = p[1]
    logger.debug('end statement: %s', p[0])

def p_return_statement(p):
    '''return_statement : RETURN LPAREN expression RPAREN SEMICOLON'''
    logger.debug('in return_statement: p values: %s', p[:])
    p[0] = f"return {p[3]};"
    logger.debug('end return_statement: %s', p[0])
    
def p_call_statement(p):
    '''call_statement : CALL ID LPAREN parameter_list RPAREN SEMICOLON
                      | CALL ID LPAREN RPAREN SEMICOLON'''
    logger.debug('in call_statement: p values: %s', p[:])
    if len(p) == 6:  # Without parameters
        p[0] = f"{safe_java_id(p[2])}();"
        return

    proc_name = safe_java_id(p[2])
    args = [a.strip() for a in p[4].split(',')]

    # Pass-by-reference: wrap each argument in a type[] array, copy back after call
    import re as _re
    _simple_id = _re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

    lines = []
    ref_args = []
    copy_backs = []
    for i, arg in enumerate(args):
        ref_name = f"_ref{i}"
        if _simple_id.match(arg):
            var_type = declared_var_types.get(arg, 'long')
            if var_type == 'String':
                lines.append(f'String[] {ref_name} = new String[]{{{arg}}};')
            else:
                lines.append(f'{var_type}[] {ref_name} = new {var_type}[]{{{arg}}};')
            ref_args.append(ref_name)
            copy_backs.append(f'{arg} = {ref_name}[0];')
        else:
            # Expression argument — pass a temporary array; no copy-back possible
            lines.append(f'long[] {ref_name} = new long[]{{(long)({arg})}};')
            ref_args.append(ref_name)

    ref_args_str = ', '.join(ref_args)
    lines.append(f'{proc_name}({ref_args_str});')
    lines.extend(copy_backs)
    p[0] = '\n'.join(lines)
    logger.debug('end call_statement: %s', p[0])
        
    
def p_block_comment_statement(p):
    '''block_comment_statement : BLOCK_COMMENT'''
    logger.debug('in block_comment_statement: p values: %s', p[:])
    p[0] = "//" + p[0]

def p_assignment_statement(p):
    '''assignment_statement : variable_access ASSIGN expression SEMICOLON'''
    logger.debug('in assignment: p values: %s', p[:])
    logger.debug('in assignment,length: %d', len(p))
    p[0] = f"{p[1]} = {p[3]};"
    logger.debug('end assignment: %s', p[0])

def p_expression(p):
    '''expression : expression PLUS expression
                  | expression MINUS expression
                  | expression TIMES expression
                  | expression DIVIDE expression
                  | LPAREN expression RPAREN
                  | ID
                  | NUMBER
                  | CHAR_CONST
                  | SUBSTR
                  | MOD
                  | INDEX
                  | DECIMAL
                  | variable_access'''
    logger.debug('in expression: p values: %s', p[:])
    logger.debug('in expression,length: %d', len(p))   
          
    if len(p) == 2:
        # This handles single ID or NUMBER tokens
        p[0] = p[1]
    elif len(p) == 4 and p[1] == '(':
        # This handles expressions in parentheses
        p[0] = f"({p[2]})"
    else:
        # This handles binary operations like PLUS, MINUS, etc.
        p[0] = f"({p[1]} {p[2]} {p[3]})"
    logger.debug('end expression: %s', p[0])    
        
def p_expression_function_call(p):
    '''expression : ID LPAREN parameter_list RPAREN
                  | ID LPAREN RPAREN'''
    logger.debug('in expression_function_call: p values: %s', p[:])
    fn = safe_java_id(p[1])
    if len(p) == 5:  # Function call with arguments
        p[0] = f"{fn}({p[3]})"
    else:  # Function call without arguments
        p[0] = f"{fn}()"
    logger.debug('end expression_function_call: %s', p[0])

def p_expression_substr(p):
    '''expression : SUBSTR LPAREN ID COMMA NUMBER COMMA NUMBER RPAREN
                  | SUBSTR LPAREN ID COMMA NUMBER RPAREN'''

    logger.debug('in substr: p values: %s', p[:])              
    if len(p) == 9:  # SUBSTR with start and length
        start = p[5] - 1  # PL/I starts at 1, Python starts at 0
        length = p[7]
        p[0] = f"{p[3]}.substring({start},{start + length})"
    elif len(p) == 7:  # SUBSTR with only start
        start = p[5] - 1
        # In Java substring(start) returns substring from start to end
        p[0] = f"{p[3]}.substring({start})"
    logger.debug('end substr: %s', p[0])    
    
def p_expression_mod(p):
    '''expression : MOD LPAREN ID COMMA NUMBER RPAREN'''
    logger.debug('in mod: p values: %s', p[:])              
    p[0] = f"{p[3]}%{p[5]}"
    logger.debug('end substr: %s', p[0])  

def p_expression_random(p):
    '''expression : RANDOM LPAREN RPAREN
                  | RANDOM LPAREN expression RPAREN
                  | RANDOM LPAREN expression COMMA expression RPAREN'''
    logger.debug('in random: p values: %s', p[:])              
    global uses_random
    uses_random = True
    if len(p) == 4:  # RANDOM()
        p[0] = "RndRuntime.random(100)"
    elif len(p) == 5:  # RANDOM(bound)
        p[0] = f"RndRuntime.random({p[3]})"
    elif len(p) == 7:  # RANDOM(lower, upper)
        p[0] = f"RndRuntime.random({p[3]}, 0)"      
        
def p_expression_index(p):
    '''expression : INDEX LPAREN ID COMMA CHAR_CONST RPAREN'''    
    logger.debug('in index: p values: %s', p[:]) 
                 
    p[0] = f"{p[3]}.indexOf({p[5]}) + 1"   
    logger.debug('end index: %s', p[0])  
    
def p_expression_decimal(p):
    '''expression : DECIMAL LPAREN ID RPAREN''' 
    logger.debug('in decimal: p values: %s', p[:])              
    
    # Convert the ID to a string using Java's String.valueOf() function
    p[0] = f"String.valueOf({p[3]})"
    
    logger.debug('end decimal: %s', p[0])
        
def p_if_statement(p):
    '''if_statement : IF relational_expression THEN statement ELSE statement   
                    | IF relational_expression THEN statement ELSE do_end_block
                    | IF relational_expression THEN do_end_block ELSE statement  
                    | IF relational_expression THEN do_end_block ELSE do_end_block'''
    
    logger.debug('in if_statement: p values: %s', p[:])  
    logger.debug('len: %d', len(p))                
    
    # Check if p[4] (then block) is a list, otherwise wrap it in a list
    then_block = p[4] if isinstance(p[4], list) else [p[4]]
    
    # Check if p[6] (else block) is a list, otherwise wrap it in a list
    else_block = p[6] if isinstance(p[6], list) else [p[6]]
    
    then_code = "\n".join(then_block)
    else_code = "\n".join(else_block)
      
    p[0] = f"if {p[2]}\n{indent_block(then_code, level=1)}\nelse\n{indent_block(else_code, level=1)}"
    # p[0] = f"if {p[2]}:\n{then_code}\nelse:\n{else_code}"
        

def p_do_end_block(p):
    '''do_end_block : DO SEMICOLON statement_list END SEMICOLON'''
    logger.debug('in do_end: p values: %s', p[:]) 
    p[0] = ["{"] + p[3] + ["}"]
    logger.debug('end do_end: %s', p[0])

# Relational expressions to handle comparisons
def p_relational_expression(p):
    '''relational_expression : expression EQ expression
                             | expression NE expression
                             | expression LT expression
                             | expression LE expression
                             | expression GT expression
                             | expression GE expression
                             | expression ASSIGN expression'''
    logger.debug('in relational_expression: p values: %s', p[:])                           
    if p[2] == '=':
        p[0] = f"({p[1]} == {p[3]})"
    else:
        p[0] = f"({p[1]} {p[2]} {p[3]})"
    logger.debug('end relational_expression: %s', p[0]) 

def p_expression_concat(p):
    '''expression : expression CONCAT expression'''
    p[0] = f"{p[1]} + {p[3]}"

# PUT statement rule: translates 'put skip list' to Python's print function
def p_put_statement(p): 
    '''put_statement : PUT SKIP LIST LPAREN element_list RPAREN SEMICOLON'''
   
    logger.debug('in put_statement: p values: %s', p[:])
    #elements = "+ ".join(map(str, p[5]))
    elements = "+ ".join(map(lambda x: x.replace("'", '"'), map(str, p[5])))
    logger.debug('end put_statement: %s', elements)

    p[0] = f"System.out.println({elements});"
    
def p_get_list_statement(p):
    '''get_list_statement : GET LIST LPAREN id_list RPAREN SEMICOLON'''
    global uses_scanner
    uses_scanner = True
    var_names = p[4]  # List of variable names (assumed to be a list of strings)

    # Improved Java code generation with type handling and error checking
    java_code = ""
    for var_name in var_names:
        logger.debug('var_name: %s', var_name)
        # Assuming you have a way to determine the type of var_name
        var_type = get_variable_type(var_name, all_dcls)  # Pass the variable name and all declarations

        java_code += f"System.out.print(\"Enter {var_name}: \");\n"
        
        logger.debug('var_type: %s', var_type)

        # Use appropriate input methods based on variable type
        if var_type == "int":
            java_code += f"{var_name} = scanner.nextInt();\nscanner.nextLine();\n"
        elif var_type == "float":
            java_code += f"{var_name} = scanner.nextDouble();\n"
        elif var_type == "String":
            java_code += f"{var_name} = scanner.nextLine();\n"
        else:
            # Handle unknown types gracefully
            logger.warning("Unknown type '%s' for variable '%s'. Assuming String.", var_type, var_name)
            java_code += f"{var_name} = scanner.nextLine();\n"

    p[0] = java_code
  

import re

def get_variable_type(variable_name, declarations):
    logger.debug('declarations: %s', declarations)
    logger.debug('variable_name: %s', variable_name)
    # Regular expression to match variable declarations
    pattern = r"(int|String|long)\s+(\w+)\s*="
    # Find all matches in the declarations
    matches = re.findall(pattern, declarations)
    # Create a dictionary to store variable types
    variable_types = {name: vtype for vtype, name in matches}
    logger.debug('variable_types: %s', variable_types)
    # Return the type of the requested variable
    return variable_types.get(variable_name, "Variable not found")


    
# List of variable names (e.g., var1, var2, var3)
def p_id_list_multiple(p):
    '''id_list : ID COMMA id_list'''
    logger.debug('in ID_list: p values: %s', p[:]) 
    p[0] = [p[1]] + p[3]  # Combine current ID with rest of the list


def p_element_list(p):
    '''element_list : element
                    | element_list COMMA element'''
    logger.debug('in element_list: p values: %s', p[:])
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]
    logger.debug('end element_list: %s', p[0])

def p_element(p):
    '''element : ID
               | ID LPAREN NUMBER RPAREN
               | ID LPAREN NUMBER COMMA NUMBER RPAREN
               | NUMBER
               | CHAR_CONST
               '''
    logger.debug('in element: p values: %s', p[:])
    if len(p) == 5:
        p[0] = p[1] + "[" + str(p[3]) + "]"
    elif len(p) == 7:
        p[0] = p[1] + "[" + str(p[3]) + "]" + "[" + str(p[5]) + "]"
    else:
        p[0] = p[1]
    logger.debug('end element: %s', p[0])


def p_select_statement(p):
    '''select_statement : SELECT LPAREN expression RPAREN SEMICOLON when_list other_statement END SEMICOLON'''
    logger.debug('in select_statement: p values: %s', p[:])

    # Start building the if-elif-else structure
    select_var = p[3]
    when_cases = p[6]  # when_list provides a list of tuples (condition, code block)

    logger.debug('when_cases: %s', when_cases)

    # Create the initial if statement
    python_code = f"if ({select_var} == {when_cases[0][0]})\n{indent_block(when_cases[0][1], level=1)}"    

    # Add elif statements for the rest of the cases
    for condition, code in when_cases[1:]:
        python_code += f"\nelse if ({select_var} == {condition})\n{indent_block(code, level=1)}"        

    # Handle the 'other' block if present
    if p[7]:  # Use p[7] for the other block
        other_block = indent_block(p[7], level=1)       
        python_code += f"\nelse\n{other_block}"

    # Add the 'end' statement
    python_code += "\n //end-select"

    p[0] = "//select-start \n" + python_code
    logger.debug('end select_statement: %s', p[0])


def p_select_end(p):
    '''select_end : END SEMICOLON'''
    logger.debug('in select_end: p values: %s', p[:])
    p[0] = "end select"

def p_when_list(p):
    '''when_list : when_list WHEN LPAREN expression RPAREN statement  
                 | when_list WHEN LPAREN expression RPAREN do_end_block
                 | WHEN LPAREN expression RPAREN statement  
                 | WHEN LPAREN expression RPAREN do_end_block
                 | empty'''    
    logger.debug('in when_list: p values: %s', p[:])
    logger.debug('len(p): %d', len(p))

    # Add 'when' clauses as tuples of (condition, flattened statement)
    if len(p) == 7:  # This is for "when_list WHEN ( expression ) statement" format
        # Flatten the statement if necessary
        statement_block = "\n".join(p[6]) if isinstance(p[6], list) else p[6]
        if isinstance(p[1], list):  # Continuing the existing list
            p[0] = p[1] + [(p[4], statement_block)]
        else:  # First entry in the list
            p[0] = [(p[4], statement_block)]
    else:  # This is for "WHEN ( expression ) statement" format (without preceding when_list)
        statement_block = "\n".join(p[5]) if isinstance(p[5], list) else p[5]
        p[0] = [(p[3], statement_block)]

    logger.debug('end when_list: %s', p[0])

def p_other_statement(p):
    '''other_statement : OTHER statement  
                       | OTHER do_end_block
                       | empty'''
    logger.debug('in other_statement: p values: %s', p[:])

    if len(p) > 1 and p[2]:  # If there is an 'other' clause
        if isinstance(p[2], list):  # Flatten if it's a list
            p[0] = "\n".join(p[2])
        else:
            p[0] = p[2]
    else:
        p[0] = ""

    logger.debug('end other_statement: %s', p[0])


def p_do_while_statement(p):
    '''do_while_statement : DO WHILE LPAREN relational_expression RPAREN SEMICOLON statement do_end
                          | DO WHILE LPAREN relational_expression RPAREN SEMICOLON statement_list do_end'''                       
    logger.debug('in do_while_statement: p values: %s', p[:]) 

    # Get the relational expression (condition) and the loop body
    loop_condition = p[4]  # This holds the relational expression
    stmt = ''
    if isinstance(p[7], list):        
        loop_body = "\n".join([stmt for stmt in p[7]])        
        logger.debug('stmt in do_while_statement: %s', loop_body)
    else:
        loop_body = p[7]
        logger.debug('p[7] is no list: %s', p[7])
    loop_body = indent_block(loop_body, level + 1)    
    
    # Translate to Python's 'while' construct    
    loop_body = loop_body + "\n" + "} //end simulated" 
    p[0] = f"while {loop_condition} {{\n{loop_body}"
        
    logger.debug('end do_while_statement: %s', p[0])
    

def p_do_from_to_statement(p):
    '''do_from_to_statement : DO ID ASSIGN expression TO expression SEMICOLON statement do_end
                            | DO ID ASSIGN expression TO expression SEMICOLON statement_list do_end'''
                            
    
    logger.debug('in do_from_to_statement: p values: %s', p[:])

    loop_variable = p[2]  # Variable der Schleife
    start_expr = p[4]     # Startwert
    end_expr = p[6]       # Endwert
    
    # Loop body verarbeiten
    if isinstance(p[8], list):
        loop_body = "\n".join(p[8])
    else:
        loop_body = p[8]

    loop_body = indent_block(loop_body, level + 1)

    # In eine Java-ähnliche for-Schleife übersetzen
    loop_body += "\n} // end simulated"
    p[0] = f"for ({loop_variable} = {start_expr}; {loop_variable} <= {end_expr}; {loop_variable}++) {{\n{loop_body}"

    print('end do_from_to_statement:', p[0], flush=True)
    
    
def p_do_end(p):
    '''do_end : END SEMICOLON'''
    print('in do_end_statement:', f"p[:] values: {p[:]}", flush=True) 
    p[0] = "} //end simulated"
    print('end do_end_statement:', p[0], flush=True)
    # p[0] = None
    
def p_open_file(p):
    '''open_file : OPEN FILE LPAREN CHAR_CONST RPAREN INPUT SEMICOLON
                 | OPEN FILE LPAREN CHAR_CONST RPAREN OUTPUT SEMICOLON'''   
    # '''open_file : OPEN FILE LPAREN CHAR_CONST RPAREN MODE SEMICOLON'''
    print('in open_file:', f"p[:] values: {p[:]} (len: {len(p)})", flush=True)
    global uses_fileio
    uses_fileio = True

    global file_open_modes
    mode = p[6].lower()
    fname = p[4].replace('"', "")
    file_open_modes[fname] = mode

    if mode == "input":
        p[0] = (f"java.io.FileReader fileReader_{fname} = new java.io.FileReader(\"{fname}.txt\");\n"
                f"java.io.BufferedReader in_{fname} = new java.io.BufferedReader(fileReader_{fname});")
    elif mode == "output":
        p[0] = (f"java.io.FileWriter fileWriter_{fname} = new java.io.FileWriter(\"{fname}.txt\");\n"
                f"java.io.PrintWriter out_{fname} = new java.io.PrintWriter(fileWriter_{fname});")
    else:
        print(f"Unsupported file mode: {mode}")
        p[0] = ""

def p_read_file(p):
    '''read_file : READ FILE LPAREN CHAR_CONST RPAREN INTO LPAREN ID RPAREN SEMICOLON'''
    print('in read:', f"p[:] values: {p[:]}", flush=True)
    global uses_fileio
    uses_fileio = True
    fname = p[4].replace('"', "")
    var_name = p[8]
    p[0] = f"{var_name} = in_{fname}.readLine();"

def p_write_file(p):
    '''write_file : WRITE FILE LPAREN CHAR_CONST RPAREN FROM LPAREN ID RPAREN SEMICOLON'''
    print('in write:', f"p[:] values: {p[:]}", flush=True)
    global uses_fileio
    uses_fileio = True
    fname = p[4].replace('"', "")
    var_name = p[8]
    p[0] = f"out_{fname}.println({var_name});"

def p_close_file(p):
    '''close_file : CLOSE FILE LPAREN CHAR_CONST RPAREN SEMICOLON'''
    print('in close:', f"p[:] values: {p[:]}", flush=True)
    global uses_fileio
    uses_fileio = True
    fname = p[4].replace('"', "")
    mode = file_open_modes.get(fname, 'input')
    handle = f"out_{fname}" if mode == "output" else f"in_{fname}"
    p[0] = f"{handle}.close();"
           

#Some global variables for database access    
host = '' 
user = ''
password = '' 
db_name = '' 

def read_parameters_from_file(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            parameter_list = file.read().strip()
        return parameter_list
    else:
        print(f"***Error: File '{filename}' not found. SQL error!")
        return None

#SQL code here:
    

def p_sql_statement(p):
    'sql_statement : EXEC SQL STRING INTO ID SEMICOLON'
    # print('in sql_statement:', f"p[:] values: {p[:]}", flush=True)
        
    global uses_sql, uses_map, uses_urlclassloader
    uses_sql = True
    uses_map = True
    uses_urlclassloader = True

    sql_query = p[3].strip('"')
    pl1_var = p[5]
    var_type = get_variable_type(pl1_var, all_dcls) 
    print('var_type:', pl1_var, var_type, flush=True)
    add_to_result = ""
    if var_type == "int":
       add_to_result = "Integer.parseInt(result);"
    elif var_type == "long":
        add_to_result = "Long.parseLong(result);"
    else:
        add_to_result = "result;" # only int, long, String types are supported

    # For numeric types wrap the parse in an error guard so a DB error string
    # (starts with "E:") does not cause a NumberFormatException at runtime.
    if var_type in ("int", "long"):
        assign_stmt = f'if (!result.startsWith("E:")) {{ {pl1_var} = {add_to_result} }} else {{ System.err.println("SQL Error: " + result); }}'
    else:
        assign_stmt = f'{pl1_var} = {add_to_result}'

    # Read SQL credentials from a text file. Generated Java will read an env-var
    # `PLIJAVA_CREDS_FILE` if set; otherwise falls back to c:/temp/creds.txt
    p[0] = f'''
        filePath = System.getenv("PLIJAVA_CREDS_FILE") != null ? System.getenv("PLIJAVA_CREDS_FILE") : "c:/temp/creds.txt"; // Path to the credentials file
        sql_statement =  "{sql_query}"; // SQL statement to be executed
        credentials = PliJavaRuntime.parseCredentials(filePath);
        dbsys = credentials.get("dbsys");
        jdbc_path = credentials.get("jdbc_path");
        port = credentials.get("port");
        host = credentials.get("host");
        user = credentials.get("user");
        password = credentials.get("password");
        dbName = credentials.get("database");

        dbsys = dbsys.replace('\"', ' ').trim();
        jdbc_path = jdbc_path.replace('\"', ' ').trim();
        port = port.replace('\"', ' ').trim();
        host = host.replace('\"', ' ').trim();
        user = user.replace('\"', ' ').trim();
        password = password.replace('\"', ' ').trim();
        dbName = dbName.replace('\"', ' ').trim();
        result = PliJavaRuntime.executeQuery(dbsys, jdbc_path, port, sql_statement, host, dbName, user, password);
        {assign_stmt}
                     '''
#{pl1_var}  = ((Number) result1).longValue();               
def p_pl1_var(p):
    '''pl1_var : ID'''
    print('in pl1_var:', f"p[:] values: {p[:]}", flush=True)
    p[0] = p[1]  # PL/I variable is an identifier (ID)


# Error handling
def p_error(p):
    if p:
        print(f"Syntax error at token '{p.value}'", flush=True)
    else:
        print("Syntax error at EOF", flush=True)
        
        
parser = yacc.yacc(debug=True, write_tables=True, outputdir='.')

# =============================================================================
# After building the parser, print the state tables (option)
# =============================================================================
def print_lr_state_table(parser):
    """Prints the LR parsing state table."""
    # Check if the parser has the required attributes
    if not hasattr(parser, 'action') or not hasattr(parser, 'goto'):
        print("The parser does not have 'action' or 'goto' attributes.")
        return

    print("State | Action")
    print("-" * 20)

    # Accessing and printing the LR action table
    for state, actions in parser.action.items():
        print(f"State {state}:")
        for token, action in actions.items():
            print(f"  On token {token}: {action}")

    # Accessing and printing the LR goto table
    print("\nGoto Table:")
    for state, gotos in parser.goto.items():
        print(f"State {state}:")
        for nonterminal, next_state in gotos.items():
            print(f"  On non-terminal {nonterminal}: Go to state {next_state}")

# Example call after parser is created
# print_lr_state_table(parser)

# =============================================================================
# Call the TK interface to select the input PL/1 code
# =============================================================================
pl1_code = ""

import tkinter as tk
from tkinter import filedialog

# Global variable to store the selected file path
selected_file_path = None

# Allow non-interactive runs by reading `PLIJAVA_INPUT_FILE` env var
env_input = os.environ.get("PLIJAVA_INPUT_FILE")
if env_input:
    if os.path.exists(env_input):
        selected_file_path = env_input
    else:
        logger.warning("PLIJAVA_INPUT_FILE is set but file does not exist: %s", env_input)

def select_file():
    """Opens a file dialog for the user to select a PL/I file if not already selected."""
    global selected_file_path

    # Check if file has already been selected, avoid re-opening the file dialog
    if selected_file_path is None:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        selected_file_path = filedialog.askopenfilename(
            title="Select PL/I Input File",
            filetypes=[("PL/I Files", "*.pli"), ("All Files", "*.*")]
        )
        if selected_file_path:
            print(f"Selected file: {selected_file_path}")
        else:
            print("No file selected.")
    
    return selected_file_path

def read_pli_from_file(file_path):
    """Reads PL/I code from the specified file."""
    if not file_path:
        raise ValueError("No file path provided")
    
    with open(file_path, 'r') as file:
        pl1_input = file.read()
    return pl1_input

def pli_to_python(pl1_input):
    """Placeholder for the PL/I to Python transpiler logic."""
    # Your transpiler code logic goes here
    # Return some dummy Python code for this example
    return "# Transpiled Python code goes here"

def execute_transpiler():
    """Executes the PL/I transpiler by selecting the file via file dialog."""
    file_path = select_file()  # This will open the dialog only once
    if not file_path:
        print("No file selected.")
        return None
    
    # Read the PL/I input from the selected file
    pl1_code = read_pli_from_file(file_path)
    # Print or return the PL/I input code
    print("Input PL/I Code:\n")    
    print(pl1_code)
    return pl1_code

pl1_code = execute_transpiler() 

# =============================================================================
# Call the (yacc) parser with or without trace
# =============================================================================
result = parser.parse(pl1_code)
#result = parser.parse(pl1_code, debug=True)

 
def execute_transpiler(java_code, class_name):
    import os 
    import subprocess
    import time
    from pathlib import Path
    import shutil
    
    # Step 0: Resolve JAVA_HOME (use environment if set, fall back to PATH discovery)
    java_home = os.environ.get("JAVA_HOME") or os.environ.get("JDK_HOME")
    if not java_home:
        javac_path = shutil.which("javac")
        if javac_path:
            # assume JDK bin sits in .../bin/javac
            java_home = os.path.dirname(os.path.dirname(javac_path))
        else:
            # fallback to previous hardcoded path (kept for compatibility)
            java_home = r"C:\Program Files\Semeru\jdk-26.0.0.35-openj9"
    os.environ["JAVA_HOME"] = java_home
    process = subprocess.run(["where", "java"], capture_output=True, text=True)
    print("Where is Java:" + process.stdout)
    
    # Step 1: Write Java code to a file named after the class
    java_filename = f"{class_name}.java"     
    print('java_filename:', java_filename, flush=True)
    with open(java_filename, "w") as file:
        file.write(java_code)
        
    print("===Formatted JAVA code:==========================")
    try:
        subprocess.run(["astyle.exe", java_filename], check=False)
    except FileNotFoundError:
        print("Note: astyle.exe not found, skipping code formatting")

    with open(java_filename, "r", encoding="utf-8") as file:
       for line in file:
          print(line, end="")  # Print the line and suppress newline
     
    # Step 2: Compile the Java code
    # get the current working directory
    current_working_directory = Path.cwd()
    # print output to the console
    #print('***workdir:', current_working_directory, flush=True)
   
    # Insert the directory path in here
    path = current_working_directory
     
    # Extracting all the contents in the directory corresponding to path
    l_files = os.listdir(path)     
    # Iterating over all the files
    for file in l_files:             
        file_path = f'{path}\\{file}'
        #print(file)     
    #print(f'Current working directory: {path}')    
    file_with_path = os.path.join(path, java_filename)
    #print('***fullname:', file_with_path, flush=True)
    
    # prefer javac from resolved JAVA_HOME, otherwise use system path
    javac_path = os.path.join(java_home, "bin", "javac") if java_home else shutil.which("javac")
    if not os.path.exists(javac_path):
        javac_path = shutil.which("javac")
    classpath = f'.{os.pathsep}{JAVALIB_DIR}'
    if uses_sql:
        db2jar = os.path.join(JAVALIB_DIR, 'db2jcc4.jar')
        classpath = f'{classpath}{os.pathsep}{db2jar}'
        drivershim_class = os.path.join(JAVALIB_DIR, 'DriverShim.class')
        drivershim_src = os.path.join(JAVALIB_DIR, 'DriverShim.java')
        if not os.path.exists(drivershim_class):
            subprocess.run([javac_path, '-cp', classpath, '-d', JAVALIB_DIR, drivershim_src], check=True)
    compile_process = subprocess.run([javac_path, '-cp', classpath, file_with_path], capture_output=True, text=True)
    if compile_process.returncode != 0:
        print("Compilation failed:", compile_process.stderr)
        return
    print('*** after_java_filename:', java_filename, flush=True)

    # Step 3: Execute the Java class
    java_exe = os.path.join(java_home, "bin", "java") if java_home else shutil.which("java")
    if not os.path.exists(java_exe):
        java_exe = shutil.which("java") or "java"
    run_process = subprocess.run([java_exe, '-cp', classpath, class_name], capture_output=True, text=True)
    
    print('*** classname:', class_name, flush=True)
                      
    if run_process.returncode != 0:
        print("\nExecution failed:", run_process.stderr)
    else:
        print("\n")
        print("\n===Execution result:==========================\n", run_process.stdout)
     
    
    #print("Output:", run_process.stdout)
    #print("Error:", run_process.stderr)
    
    print("\n")

    # Optional: Clean up the generated files
    # os.remove(java_filename)
    # class_file = f"{class_name}.class"
    # if os.path.exists(class_file):
    #     os.remove(class_file)

# If you need all tokens...
print("Tokens:") 
print_tokens(pl1_code)

# =============================================================================
# Print the input PL/I, the generated Python code, as well the execution result
# if possible
# =============================================================================
enablePrint()
if result:
    print("===PL/I input:================================")
    print(pl1_code)
    #print("===Java version:============================")
    #print(result)
    print("===Execution outputs:==========================")
    print('procedure_name:', procedure_name, flush=True)
    execute_transpiler(result, procedure_name)    
    print("==============================================")
else:
    print("Parsing failed.")