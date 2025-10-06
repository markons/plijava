# plijava
Conversion of PL/I code into similar Java code
It is a fork of my ***plithon*** PL/I to Python project      

***Important:*** this work is primarily the intermediate result of a learning process. 
It is not intended to be the full realisation of the work shown in the title. 
It contains errors which I am trying to correct. It is not complete, but will be expanded.
## Installation
### Components needed
- Python 3.x  
- mySql Java JDBC driver (for the in V1.01 installed MySql interface)
  or IBM's JDBC driver (for the Db2 Community Edition). 
- "astyle" open source Java formatter for a beautified Java output
### How to run
- Tested only under Windows 11
- Simply copy the plithon.py in your (Windows, see also above) directory
- Call the program like this (sample): C:\apps\plithon>python plijava.py
- Select your PL/I input file in the explorer window
- If you want to include SQL statements, store your credentials in the file "c:/temp/creds.txt". 
  I'll make the location of this file later selectable.
  Content of this file is one record (here as sample):
  ***host="localhost", user="root", password="admin", database="sakila"***   
## Following features are installed in version 1.00:
-  dcl variable-name <fixed bin(15|31) | char(length)>;
-  variable = `<arithmetic-expression>` | `<string-expression>`;
-  operators in arithmetic_expression: + - * / ( )
-  operators in string-expression: builtins: substr index decimal
-  if relational-expression then statement else statement;
-  select(expression) when(value) statement; other statement; end; 
-  put skip list(variable | constant);
-  one-dimensional arrays are now supported (only integer indexing is possible)
-  record i/o simple version (open close read write) works
-  do-while loop
## Following features are to be installed in version 1.01:
-  exec sql "select  sql-select-field" into variable; - only MySQL connection, sample db sakila (sorry, actual are my credentials _hardcoded_)
-  get list(variable-list); - read variables from console per prompt
