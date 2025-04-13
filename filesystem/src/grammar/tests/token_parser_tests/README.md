# Token Parser Integration Tests

This directory contains integration tests for the token_parser module. The tests verify that the token parsers correctly parse code in different languages and produce the expected abstract syntax tree (AST) represented as `CodeElement` objects.

## Test Structure

Each language has its own test file:

- `test_python_token_parser.py` - Tests for the Python token parser
- `test_javascript_token_parser.py` - Tests for the JavaScript token parser
- `test_typescript_token_parser.py` - Tests for the TypeScript token parser
- `test_c_token_parser.py` - Tests for the C token parser
- `test_cpp_token_parser.py` - Tests for the C++ token parser
- `test_rust_token_parser.py` - Tests for the Rust token parser
- `test_html_token_parser.py` - Tests for the HTML token parser
- `test_css_token_parser.py` - Tests for the CSS token parser

## Test Data

The tests use source code files from the `tests/test_data/<language>` directories. Each source file should have a corresponding `.expected.json` file with the same base name that contains the expected parsing result.

For example:
- `tests/test_data/py/test_python_parser_1.py` - Source code file
- `tests/test_data/py/test_python_parser_1.expected.json` - Expected result

## Creating Test Cases

To create a new test case:

1. Add a source code file to the appropriate language directory under `tests/test_data/<language>/`.
2. Use the `generate_expected_json.py` script to generate the expected output:

   ```bash
   python -m tests.token_parser_tests.generate_expected_json \
       tests/test_data/py/your_test_file.py --language python
   ```

   This will create `tests/test_data/py/your_test_file.expected.json`.

3. Review and adjust the generated JSON if needed.
4. The tests will automatically discover and run tests for files that have matching `.expected.json` files.

## Running the Tests

To run all token parser tests:

```bash
python -m tests.token_parser_tests.run_all_tests
```

To run tests for a specific language:

```bash
python -m tests.token_parser_tests.test_python_token_parser
python -m tests.token_parser_tests.test_javascript_token_parser
# etc.
```

## Expected JSON Format

The expected JSON file should match the format of serialized `CodeElement` objects. Each element should have at least the following properties:

```json
{
  "name": "hello_world",
  "element_type": "function",
  "start_line": 1,
  "end_line": 3,
  "children": []
}
```

Additional properties will be included based on the element type and language-specific features.
