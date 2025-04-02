"""
Metadata extractor for code parsers.

This module provides utilities to extract metadata from code elements,
including docstrings, decorators, annotations, and other language-specific features.
"""

import re
from typing import Dict, List, Optional, Any, Tuple


class MetadataExtractor:
    """
    Base class for extracting metadata from code.
    Language-specific extractors should inherit from this class.
    """

    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract all metadata from code at the given line index.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary containing extracted metadata
        """
        return {}


class PythonMetadataExtractor(MetadataExtractor):
    """Metadata extractor for Python code."""
    
    def __init__(self):
        """Initialize Python metadata extractor patterns."""
        self.docstring_pattern = re.compile(r'^(\s*)(?:\'\'\'|""")')
        self.decorator_pattern = re.compile(r'^\s*@([a-zA-Z_][a-zA-Z0-9_\.]*)')
        self.type_annotation_pattern = re.compile(r':\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s\.]*)')
        self.return_type_pattern = re.compile(r'\)\s*->\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s\.]*)')
    
    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract Python-specific metadata from code.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary containing docstrings, decorators, type annotations, etc.
        """
        lines = code.splitlines()
        metadata = {}
        
        # Extract decorators by looking at preceding lines
        decorators = []
        current_idx = line_idx - 1
        while current_idx >= 0:
            line = lines[current_idx]
            decorator_match = self.decorator_pattern.match(line)
            if decorator_match:
                decorators.insert(0, decorator_match.group(1))
                current_idx -= 1
            else:
                break
        
        if decorators:
            metadata["decorators"] = decorators
        
        # Extract docstring
        if line_idx + 1 < len(lines):
            docstring = self._extract_docstring(lines, line_idx + 1)
            if docstring:
                metadata["docstring"] = docstring
                
        # Extract type annotations from the definition line
        if line_idx < len(lines):
            definition_line = lines[line_idx]
            
            # Extract parameter type annotations
            type_annotations = {}
            param_section = definition_line.split('(')[1].split(')')[0] if '(' in definition_line else ""
            if param_section:
                # Simple parsing for parameters
                params = param_section.split(',')
                for param in params:
                    if ':' in param:
                        param_name, annotation = param.split(':', 1)
                        param_name = param_name.strip()
                        annotation = annotation.strip()
                        if param_name and annotation:
                            type_annotations[param_name] = annotation
            
            if type_annotations:
                metadata["type_annotations"] = type_annotations
            
            # Extract return type
            return_match = self.return_type_pattern.search(definition_line)
            if return_match:
                metadata["return_type"] = return_match.group(1).strip()
        
        return metadata
        
    def _extract_docstring(self, lines: List[str], start_idx: int) -> Optional[str]:
        """
        Extract a docstring from the code.
        
        Args:
            lines: List of code lines
            start_idx: Index to start looking from
            
        Returns:
            Docstring if found, None otherwise
        """
        if start_idx >= len(lines):
            return None
            
        line = lines[start_idx]
        if not line.strip():
            # Skip blank lines
            if start_idx + 1 < len(lines):
                return self._extract_docstring(lines, start_idx + 1)
            return None
            
        docstring_match = self.docstring_pattern.match(line)
        if not docstring_match:
            return None
            
        # Determine the docstring delimiter (''' or """)
        delimiter = '"""' if '"""' in line else "'''"
        
        # Check if the docstring is a single line
        if line.count(delimiter) == 2:
            # Single-line docstring
            return line.strip()
            
        # Multi-line docstring, find the end
        docstring_lines = [line]
        for idx in range(start_idx + 1, len(lines)):
            docstring_lines.append(lines[idx])
            if delimiter in lines[idx]:
                break
                
        return "\n".join(docstring_lines)


class JavaScriptMetadataExtractor(MetadataExtractor):
    """Metadata extractor for JavaScript/TypeScript code."""
    
    def __init__(self):
        """Initialize JavaScript metadata extractor patterns."""
        self.jsdoc_pattern = re.compile(r'^\s*/\*\*')
        self.decorator_pattern = re.compile(r'^\s*@([a-zA-Z_][a-zA-Z0-9_\.]*)')
        self.type_annotation_pattern = re.compile(r':\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s\.]*)')
    
    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract JavaScript-specific metadata from code.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary containing JSDoc comments, decorators, type annotations, etc.
        """
        lines = code.splitlines()
        metadata = {}
        
        # Extract JSDoc
        jsdoc = self._extract_jsdoc(lines, line_idx - 1)
        if jsdoc:
            metadata["docstring"] = jsdoc
            
            # Extract special JSDoc tags
            tags = self._extract_jsdoc_tags(jsdoc)
            if tags:
                metadata["jsdoc_tags"] = tags
        
        # Extract TypeScript decorators (if any)
        decorators = []
        current_idx = line_idx - 1
        
        # Skip JSDoc if present
        if jsdoc:
            jsdoc_lines = jsdoc.count('\n') + 1
            current_idx = line_idx - jsdoc_lines - 1
            
        while current_idx >= 0:
            line = lines[current_idx]
            decorator_match = self.decorator_pattern.match(line)
            if decorator_match:
                decorators.insert(0, decorator_match.group(1))
                current_idx -= 1
            else:
                break
                
        if decorators:
            metadata["decorators"] = decorators
            
        # Extract TypeScript type annotations
        if line_idx < len(lines):
            definition_line = lines[line_idx]
            
            # Check for return type annotation
            if '):' in definition_line:
                return_type = definition_line.split('):')[1].split('{')[0].strip()
                if return_type:
                    metadata["return_type"] = return_type
                    
            # Extract parameter type annotations
            param_types = {}
            
            # Simple extraction of parameters with types
            if '(' in definition_line and ')' in definition_line:
                param_section = definition_line.split('(')[1].split(')')[0]
                params = param_section.split(',')
                
                for param in params:
                    if ':' in param:
                        param_name, param_type = param.split(':', 1)
                        param_name = param_name.strip()
                        param_type = param_type.strip()
                        if param_name and param_type:
                            param_types[param_name] = param_type
                            
            if param_types:
                metadata["parameter_types"] = param_types
                
        return metadata
    
    def _extract_jsdoc(self, lines: List[str], start_idx: int) -> Optional[str]:
        """
        Extract JSDoc comment block.
        
        Args:
            lines: List of code lines
            start_idx: Index to start looking from
            
        Returns:
            JSDoc string if found, None otherwise
        """
        if start_idx < 0 or start_idx >= len(lines):
            return None
            
        # Look for JSDoc opening /**
        line = lines[start_idx]
        if not self.jsdoc_pattern.match(line):
            return None
            
        # Collect lines until we find closing */
        jsdoc_lines = [line]
        for idx in range(start_idx + 1, len(lines)):
            jsdoc_lines.append(lines[idx])
            if '*/' in lines[idx]:
                break
                
        return "\n".join(jsdoc_lines)
    
    def _extract_jsdoc_tags(self, jsdoc: str) -> Dict[str, List[str]]:
        """
        Extract specialized JSDoc tags.
        
        Args:
            jsdoc: JSDoc comment string
            
        Returns:
            Dictionary mapping tag names to their values
        """
        tags = {}
        lines = jsdoc.splitlines()
        
        for line in lines:
            line = line.strip().lstrip('* ')
            if line.startswith('@'):
                parts = line[1:].split(' ', 1)
                tag_name = parts[0]
                tag_value = parts[1] if len(parts) > 1 else ""
                
                if tag_name in tags:
                    tags[tag_name].append(tag_value)
                else:
                    tags[tag_name] = [tag_value]
                    
        return tags


class CppMetadataExtractor(MetadataExtractor):
    """Metadata extractor for C/C++ code."""
    
    def __init__(self):
        """Initialize C/C++ metadata extractor patterns."""
        self.doxygen_pattern = re.compile(r'^\s*(?:///<|///|/\*\*|\*/)')
        self.attribute_pattern = re.compile(r'^\s*\[\[([^\]]+)\]\]')
    
    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract C/C++ specific metadata from code.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary containing docstrings, attributes, etc.
        """
        lines = code.splitlines()
        metadata = {}
        
        # Extract Doxygen comment
        doxygen_comment = self._extract_doxygen(lines, line_idx - 1)
        if doxygen_comment:
            metadata["docstring"] = doxygen_comment
            
        # Extract C++11 attributes
        attributes = []
        current_idx = line_idx - 1
        
        # Skip docstring lines if present
        if doxygen_comment:
            doxygen_lines = doxygen_comment.count('\n') + 1
            current_idx = line_idx - doxygen_lines - 1
            
        while current_idx >= 0:
            line = lines[current_idx]
            attr_match = self.attribute_pattern.match(line)
            if attr_match:
                attributes.insert(0, attr_match.group(1))
                current_idx -= 1
            else:
                break
                
        if attributes:
            metadata["attributes"] = attributes
            
        # Extract visibility modifiers
        if line_idx < len(lines):
            definition_line = lines[line_idx]
            
            # Check for visibility modifiers
            modifiers = []
            for modifier in ["public", "private", "protected", "static", "virtual", "explicit", "inline", "constexpr", "const"]:
                if re.search(r'\b' + modifier + r'\b', definition_line):
                    modifiers.append(modifier)
                    
            if modifiers:
                metadata["modifiers"] = modifiers
                
        return metadata
    
    def _extract_doxygen(self, lines: List[str], start_idx: int) -> Optional[str]:
        """
        Extract Doxygen comment block.
        
        Args:
            lines: List of code lines
            start_idx: Index to start looking from
            
        Returns:
            Doxygen string if found, None otherwise
        """
        if start_idx < 0 or start_idx >= len(lines):
            return None
            
        line = lines[start_idx]
        
        # Check for different Doxygen styles
        is_doxygen = False
        doxygen_end = None
        
        if line.strip().startswith('/**'):
            is_doxygen = True
            doxygen_end = '*/'
        elif line.strip().startswith('///'):
            is_doxygen = True
            doxygen_end = None  # Single-line style
            
        if not is_doxygen:
            return None
            
        # Collect lines
        doxygen_lines = [line]
        
        if doxygen_end:
            # Multi-line style
            for idx in range(start_idx + 1, len(lines)):
                doxygen_lines.append(lines[idx])
                if doxygen_end in lines[idx]:
                    break
        else:
            # Single-line style (///)
            current_idx = start_idx - 1
            while current_idx >= 0 and lines[current_idx].strip().startswith('///'):
                doxygen_lines.insert(0, lines[current_idx])
                current_idx -= 1
                
        return "\n".join(doxygen_lines)


# Factory method to get appropriate extractor
def get_metadata_extractor(language: str) -> MetadataExtractor:
    """
    Get a metadata extractor for the specified language.
    
    Args:
        language: Programming language name
        
    Returns:
        Appropriate MetadataExtractor instance
    """
    extractors = {
        'python': PythonMetadataExtractor,
        'javascript': JavaScriptMetadataExtractor,
        'typescript': JavaScriptMetadataExtractor,
        'c': CppMetadataExtractor,
        'cpp': CppMetadataExtractor,
        'rust': MetadataExtractor,  # Base extractor for now
    }
    
    extractor_class = extractors.get(language.lower(), MetadataExtractor)
    return extractor_class()
