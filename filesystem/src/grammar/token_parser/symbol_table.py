"""
Symbol table for the grammar parser system.

This module provides the SymbolTable class that maintains language-specific
symbol tables during parsing.
"""

from typing import Dict, Any, Optional, List, Set, Union
from dataclasses import dataclass, field


@dataclass
class Symbol:
    """
    Represents a symbol in the symbol table.
    
    A symbol can be a variable, function, class, etc.
    """
    name: str
    symbol_type: str
    position: int
    line: int
    column: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self):
        return f"Symbol({self.symbol_type}, '{self.name}', line {self.line})"


@dataclass
class Scope:
    """
    Represents a scope in the symbol table.
    
    A scope is a region of code where symbols are defined and can be referenced.
    """
    scope_type: str
    parent: Optional['Scope'] = None
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    children: List['Scope'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_symbol(self, symbol: Symbol) -> None:
        """
        Add a symbol to this scope.
        
        Args:
            symbol: Symbol to add
        """
        self.symbols[symbol.name] = symbol
    
    def get_symbol(self, name: str) -> Optional[Symbol]:
        """
        Get a symbol by name from this scope.
        
        Args:
            name: Name of the symbol to get
        
        Returns:
            The symbol, or None if not found in this scope
        """
        return self.symbols.get(name)
    
    def add_child_scope(self, scope: 'Scope') -> None:
        """
        Add a child scope to this scope.
        
        Args:
            scope: Scope to add as a child
        """
        self.children.append(scope)
        scope.parent = self


class SymbolTable:
    """
    Maintains a table of symbols organized by scope.
    
    The symbol table is used during parsing to track symbols and their scopes.
    """
    
    def __init__(self):
        """Initialize the symbol table."""
        self.global_scope = Scope("global")
        self.current_scope = self.global_scope
        self.scope_stack: List[Scope] = []
    
    def enter_scope(self, scope_type: str) -> Scope:
        """
        Enter a new scope.
        
        Args:
            scope_type: Type of the new scope
        
        Returns:
            The new scope
        """
        # Push current scope onto stack
        self.scope_stack.append(self.current_scope)
        
        # Create new scope with current scope as parent
        new_scope = Scope(scope_type, self.current_scope)
        self.current_scope.add_child_scope(new_scope)
        self.current_scope = new_scope
        
        return new_scope
    
    def exit_scope(self) -> Scope:
        """
        Exit the current scope and return to the parent scope.
        
        Returns:
            The scope that was exited
        """
        exited_scope = self.current_scope
        
        if self.scope_stack:
            self.current_scope = self.scope_stack.pop()
        else:
            # If we try to exit the global scope, just stay there
            self.current_scope = self.global_scope
        
        return exited_scope
    
    def add_symbol(
        self,
        name: str,
        symbol_type: str,
        position: int,
        line: int,
        column: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Symbol:
        """
        Add a symbol to the current scope.
        
        Args:
            name: Name of the symbol
            symbol_type: Type of the symbol
            position: Character position in the source code
            line: Line number (1-based)
            column: Column number (1-based)
            metadata: Additional information about the symbol
        
        Returns:
            The created symbol
        """
        symbol = Symbol(name, symbol_type, position, line, column, metadata or {})
        self.current_scope.add_symbol(symbol)
        return symbol
    
    def lookup_symbol(self, name: str, local_only: bool = False) -> Optional[Symbol]:
        """
        Look up a symbol by name.
        
        Args:
            name: Name of the symbol to look up
            local_only: If True, only search the current scope
        
        Returns:
            The symbol if found, otherwise None
        """
        # Check current scope
        symbol = self.current_scope.get_symbol(name)
        if symbol or local_only:
            return symbol
        
        # Check parent scopes
        scope = self.current_scope.parent
        while scope:
            symbol = scope.get_symbol(name)
            if symbol:
                return symbol
            scope = scope.parent
        
        return None
    
    def get_all_symbols(self) -> List[Symbol]:
        """
        Get all symbols from all scopes as a flat list.
        
        Returns:
            List of all symbols
        """
        symbols = []
        
        def collect_symbols(scope: Scope) -> None:
            symbols.extend(scope.symbols.values())
            for child in scope.children:
                collect_symbols(child)
        
        collect_symbols(self.global_scope)
        return symbols
    
    def get_symbols_by_scope(self) -> Dict[str, List[Symbol]]:
        """
        Get all symbols organized by scope.
        
        Returns:
            Dictionary mapping scope identifiers to lists of symbols
        """
        result: Dict[str, List[Symbol]] = {}
        
        def collect_symbols_by_scope(scope: Scope, path: str = "") -> None:
            scope_path = f"{path}/{scope.scope_type}" if path else scope.scope_type
            result[scope_path] = list(scope.symbols.values())
            
            for i, child in enumerate(scope.children):
                child_path = f"{scope_path}/{i}"
                collect_symbols_by_scope(child, child_path)
        
        collect_symbols_by_scope(self.global_scope)
        return result 