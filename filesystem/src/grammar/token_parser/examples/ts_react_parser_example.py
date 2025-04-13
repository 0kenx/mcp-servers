#!/usr/bin/env python3
"""
Example demonstrating the usage of the TypeScript React parser.

This script shows how to use the TSReactParser to parse TypeScript React (TSX) code
and generate an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory
from grammar.token_parser.ast_utils import format_ast_for_output


def parse_tsx_code(code: str) -> None:
    """
    Parse TypeScript React code and print the AST.

    Args:
        code: TypeScript React source code to parse
    """
    # Get a TS-React parser from the factory
    parser = ParserFactory.create_parser("tsx")
    if not parser:
        print("TypeScript React parser is not available")
        return

    # Parse the code
    ast = parser.parse(code)

    # Format AST for output (removes circular references)
    serializable_ast = format_ast_for_output(ast)
    print(json.dumps(serializable_ast, indent=2, default=str))

    # Print the symbol table
    print("\nSymbol Table:")
    all_symbols = parser.symbol_table.get_symbols_by_scope()

    for scope, symbols in all_symbols.items():
        print(f"\nScope: {scope}")
        for symbol in symbols:
            metadata_str = ""
            if symbol.metadata:
                if (
                    "attributes" in symbol.metadata
                    and symbol.symbol_type == "jsx_element"
                ):
                    metadata_str = f", Attributes: {symbol.metadata['attributes']}"

            print(
                f"  {symbol.name} (Type: {symbol.symbol_type}, Line: {symbol.line}, Column: {symbol.column}{metadata_str})"
            )


def main() -> None:
    """Run the example with a sample TypeScript React code snippet."""
    # Sample TypeScript React code to parse
    sample_code = """
import React, { useState, useEffect, FC } from 'react';
import './App.css';

// Define types for our component props
interface UserProps {
  name: string;
  email: string;
  age?: number;
}

// Define a User component with TypeScript types
const User: FC<UserProps> = ({ name, email, age }) => {
  return (
    <div className="user-card">
      <h2>{name}</h2>
      <p>Email: {email}</p>
      {age && <p>Age: {age}</p>}
    </div>
  );
};

// Define types for our data
interface Post {
  id: number;
  title: string;
  body: string;
}

// Main App component
const App: FC = () => {
  // State with TypeScript type definitions
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Effect to fetch data
  useEffect(() => {
    const fetchPosts = async () => {
      try {
        const response = await fetch('https://jsonplaceholder.typicode.com/posts');
        if (!response.ok) {
          throw new Error('Failed to fetch');
        }
        const data: Post[] = await response.json();
        setPosts(data.slice(0, 5)); // Just get first 5 posts
        setLoading(false);
      } catch (err) {
        setError('Error fetching data');
        setLoading(false);
      }
    };
    
    fetchPosts();
  }, []);
  
  // Example of conditional rendering with TypeScript
  const renderContent = () => {
    if (loading) {
      return <div className="loading">Loading...</div>;
    }
    
    if (error) {
      return <div className="error">{error}</div>;
    }
    
    return (
      <div className="posts">
        <h2>Posts</h2>
        {posts.map((post) => (
          <div key={post.id} className="post">
            <h3>{post.title}</h3>
            <p>{post.body}</p>
          </div>
        ))}
      </div>
    );
  };
  
  return (
    <div className="app">
      <header className="app-header">
        <h1>TypeScript React Example</h1>
      </header>
      
      <main>
        <User 
          name="John Doe" 
          email="john@example.com" 
          age={32} 
        />
        
        <User 
          name="Jane Smith" 
          email="jane@example.com" 
        />
        
        {renderContent()}
      </main>
      
      <footer>
        <p>&copy; {new Date().getFullYear()} TypeScript React Demo</p>
      </footer>
    </div>
  );
};

export default App;
"""

    parse_tsx_code(sample_code)


if __name__ == "__main__":
    main()
