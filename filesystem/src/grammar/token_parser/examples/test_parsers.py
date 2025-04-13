#!/usr/bin/env python3
"""
Test script for the grammar parser system.

This script demonstrates using parsers for all supported languages,
showing how the parser factory can be used to choose a parser based on
the language of the input code.
"""

import sys
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_code(code: str, language: str) -> None:
    """
    Parse code using the appropriate parser.

    Args:
        code: Source code to parse
        language: Programming language of the code
    """
    print(f"\n=== Parsing {language.upper()} Code ===\n")

    # Get the appropriate parser from the factory
    parser = ParserFactory.create_parser(language)
    if not parser:
        print(f"{language} parser is not available")
        return

    # Parse the code
    ast = parser.parse(code)

    # Print basic info about the AST
    print(f"AST Type: {ast.get('type')}")
    print(f"Body Length: {len(ast.get('body', []))}")
    print(f"Children: {len(ast.get('children', []))}")

    # Print the symbol table
    print("\nSymbol Table:")
    symbols_by_scope = parser.symbol_table.get_symbols_by_scope()

    for scope, symbols in symbols_by_scope.items():
        print(f"\nScope: {scope}")
        for symbol in symbols:
            print(
                f"  {symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}"
            )


def main() -> None:
    """Test the parsers with sample code examples."""
    # Print available parsers
    supported_languages = ParserFactory.get_supported_languages()
    print(f"Supported languages: {', '.join(supported_languages)}")

    # Sample Python code
    python_code = """
def greeting(name: str) -> str:
    return f"Hello, {name}!"

class User:
    def __init__(self, name: str):
        self.name = name
    
    def greet(self):
        return greeting(self.name)

# Create user and greet
user = User("World")
message = user.greet()
print(message)
"""

    # Sample JavaScript code
    javascript_code = """
function greeting(name) {
    return `Hello, ${name}!`;
}

class User {
    constructor(name) {
        this.name = name;
    }
    
    greet() {
        return greeting(this.name);
    }
}

// Create user and greet
const user = new User("World");
const message = user.greet();
console.log(message);
"""

    # Sample TypeScript code
    typescript_code = """
function greeting(name: string): string {
    return `Hello, ${name}!`;
}

interface UserInterface {
    name: string;
    greet(): string;
}

class User implements UserInterface {
    name: string;
    
    constructor(name: string) {
        this.name = name;
    }
    
    greet(): string {
        return greeting(this.name);
    }
}

// Create user and greet
const user: User = new User("World");
const message: string = user.greet();
console.log(message);
"""

    # Sample TSX/React code
    tsx_code = """
import React, { useState } from 'react';

interface GreetingProps {
    initialName: string;
}

function Greeting({ initialName }: GreetingProps) {
    const [name, setName] = useState(initialName);
    
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setName(e.target.value);
    };
    
    return (
        <div className="greeting">
            <h1>Hello, {name}!</h1>
            <input 
                type="text" 
                value={name} 
                onChange={handleChange} 
                placeholder="Enter your name" 
            />
        </div>
    );
}

export default Greeting;
"""

    # Sample HTML code
    html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Greeting Page</title>
    <style>
        .greeting {
            font-family: Arial, sans-serif;
            color: #333;
            text-align: center;
            margin-top: 50px;
        }
        input {
            padding: 8px 12px;
            margin-top: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="greeting">
        <h1>Hello, <span id="name">World</span>!</h1>
        <input type="text" id="nameInput" placeholder="Enter your name">
    </div>
    
    <script>
        const nameInput = document.getElementById('nameInput');
        const nameSpan = document.getElementById('name');
        
        nameInput.addEventListener('input', function() {
            nameSpan.textContent = this.value || 'World';
        });
    </script>
</body>
</html>
"""

    # Sample CSS code
    css_code = """
/* Variables */
:root {
    --primary-color: #3498db;
    --secondary-color: #2ecc71;
    --text-color: #333;
    --background-color: #f9f9f9;
}

/* Reset */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    color: var(--text-color);
    background-color: var(--background-color);
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* Header styles */
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    background-color: var(--primary-color);
    color: white;
}

/* Media query for mobile */
@media (max-width: 768px) {
    .header {
        flex-direction: column;
        padding: 1rem;
    }
}
"""

    # Sample C code
    c_code = """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_NAME_LENGTH 100

// Greeting function
void greet(const char* name) {
    printf("Hello, %s!\n", name);
}

// Structure for user
typedef struct {
    char name[MAX_NAME_LENGTH];
} User;

// Initialize user
User* create_user(const char* name) {
    User* user = malloc(sizeof(User));
    if (user == NULL) {
        return NULL;
    }
    
    strncpy(user->name, name, MAX_NAME_LENGTH - 1);
    user->name[MAX_NAME_LENGTH - 1] = '\0';
    
    return user;
}

int main() {
    User* user = create_user("World");
    if (user != NULL) {
        greet(user->name);
        free(user);
    }
    
    return 0;
}
"""

    # Sample C++ code
    cpp_code = """
#include <iostream>
#include <string>
#include <memory>

// Greeting function
std::string greeting(const std::string& name) {
    return "Hello, " + name + "!";
}

// User class
class User {
private:
    std::string name;
    
public:
    // Constructor
    User(const std::string& userName) : name(userName) {}
    
    // Getter
    const std::string& getName() const {
        return name;
    }
    
    // Greeting method
    std::string greet() const {
        return greeting(name);
    }
};

int main() {
    // Create user and greet
    auto user = std::make_unique<User>("World");
    std::string message = user->greet();
    std::cout << message << std::endl;
    
    return 0;
}
"""

    # Sample Rust code
    rust_code = """
// Greeting function
fn greeting(name: &str) -> String {
    format!("Hello, {}!", name)
}

// User struct with implementation
struct User {
    name: String,
}

impl User {
    // Constructor
    fn new(name: &str) -> Self {
        User {
            name: String::from(name),
        }
    }
    
    // Greeting method
    fn greet(&self) -> String {
        greeting(&self.name)
    }
}

// Main function
fn main() {
    // Create user and greet
    let user = User::new("World");
    let message = user.greet();
    println!("{}", message);
}
"""

    # Generic Brace Block example
    generic_brace_code = """
main {
    print("Hello, World!");
    
    if (condition) {
        print("Condition is true");
    } else {
        print("Condition is false");
    }
    
    loop {
        if (done) {
            break;
        }
    }
}
"""

    # Generic Indentation Block example
    generic_indent_code = """
def main:
    print "Hello, World!"
    
    if condition:
        print "Condition is true"
    else:
        print "Condition is false"
    
    while not done:
        check_condition
        if done:
            break
"""

    # Generic Keyword Pattern example
    generic_keyword_code = """
begin program
    print "Hello, World!"
    
    if condition then
        print "Condition is true"
    else
        print "Condition is false"
    endif
    
    while not done do
        check_condition
        if done then
            break
        endif
    endwhile
end program
"""

    # Parse each language
    parse_code(python_code, "python")
    parse_code(javascript_code, "javascript")
    parse_code(typescript_code, "typescript")
    parse_code(tsx_code, "tsx")
    parse_code(html_code, "html")
    parse_code(css_code, "css")
    parse_code(c_code, "c")
    parse_code(cpp_code, "cpp")
    parse_code(rust_code, "rust")
    parse_code(generic_brace_code, "brace")
    parse_code(generic_indent_code, "indentation")
    parse_code(generic_keyword_code, "keyword_pattern")


if __name__ == "__main__":
    main()
