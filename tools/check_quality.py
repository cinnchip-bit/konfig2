"""Check Python line length, function span, complexity and comparisons."""
import ast
from pathlib import Path

MAX_LINE_LENGTH = 80
MAX_FUNCTION_LINES = 40
MAX_COMPLEXITY = 10


def complexity(function):
    """Count branches conservatively, including nested function bodies."""
    score = 1
    branches = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
                ast.ExceptHandler)
    for node in ast.walk(function):
        if isinstance(node, branches):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += 1 + len(node.ifs)
        elif isinstance(node, ast.Match):
            score += len(node.cases)
    return score


def check_function(path, node):
    span = node.end_lineno - node.lineno + 1
    score = complexity(node)
    assert span <= MAX_FUNCTION_LINES, (path, node.name, 'lines', span)
    assert score <= MAX_COMPLEXITY, (path, node.name, 'complexity', score)
    return span, score


def numeric_literal(node):
    if isinstance(node, ast.UnaryOp):
        node = node.operand
    return (isinstance(node, ast.Constant)
            and type(node.value) in (int, float, complex))


def check_file(path):
    source = path.read_text(encoding='utf-8')
    for number, line in enumerate(source.splitlines(), start=1):
        assert len(line) <= MAX_LINE_LENGTH, (path, number, len(line))
    spans, scores = [0], [0]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            span, score = check_function(path, node)
            spans.append(span)
            scores.append(score)
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            assert not any(map(numeric_literal, operands)), (
                path, node.lineno, 'numeric literal in comparison',
            )
    return max(spans), max(scores)


def main():
    root = Path(__file__).resolve().parents[1]
    results = []
    for folder in ('src', 'tests', 'tools'):
        for path in sorted((root / folder).rglob('*.py')):
            span, score = check_file(path)
            results.append((span, score))
            print(f'{path.relative_to(root)}: lines={span}, complexity={score}')
    print(f'Passed: {len(results)} files; line limit={MAX_LINE_LENGTH}')


if __name__ == '__main__':
    main()
