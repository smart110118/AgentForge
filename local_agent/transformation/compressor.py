"""Compressor Engine: compresses tool output and extracts AST code skeletons."""

from __future__ import annotations

import ast
import re
from typing import Any


class ASTSkeletonVisitor(ast.NodeTransformer):
    """Walks Python AST and replaces function/method bodies with docstring and ellipsis."""

    def __init__(self, preserve_names: set[str] | None = None) -> None:
        self.preserve_names = preserve_names or set()

    def _fold_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
        if node.name in self.preserve_names:
            return node.body

        docstring = ast.get_docstring(node)
        new_body: list[ast.stmt] = []
        if docstring:
            new_body.append(ast.Expr(value=ast.Constant(value=docstring)))
        new_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))
        return new_body

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._fold_body(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._fold_body(node)
        return node


class CompressorEngine:
    """Provides tiered compression:
    1. Truncating large tool/shell outputs.
    2. Extracting AST structural skeleton of code while folding method implementations.
    """

    @staticmethod
    def truncate_output(text: str, head_lines: int = 15, tail_lines: int = 15, max_chars: int = 2000) -> str:
        """Keep initial and trailing lines of long outputs, folding the middle."""
        if len(text) <= max_chars and text.count("\n") <= (head_lines + tail_lines):
            return text

        lines = text.splitlines()
        if len(lines) <= (head_lines + tail_lines):
            # Line count is small but chars are large -> truncate middle chars
            half = max_chars // 2
            return f"{text[:half]}\n\n[... truncated {len(text) - max_chars} characters ...]\n\n{text[-half:]}"

        head = lines[:head_lines]
        tail = lines[-tail_lines:]
        dropped_count = len(lines) - head_lines - tail_lines
        folded = "\n".join(head) + f"\n\n[... omitted {dropped_count} lines of output ...]\n\n" + "\n".join(tail)
        return folded

    @staticmethod
    def extract_python_skeleton(source_code: str, preserve_functions: set[str] | None = None) -> str:
        """Parse Python source and return an unparsed AST skeleton with folded function bodies."""
        try:
            tree = ast.parse(source_code)
            transformer = ASTSkeletonVisitor(preserve_names=preserve_functions)
            transformer.visit(tree)
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except Exception:
            # Fallback to regex-based signature extraction if syntax error
            return CompressorEngine._regex_skeleton_fallback(source_code)

    @staticmethod
    def _regex_skeleton_fallback(source_code: str) -> str:
        lines = source_code.splitlines()
        skeleton_lines = []
        for line in lines:
            stripped = line.strip()
            if (
                stripped.startswith("def ")
                or stripped.startswith("class ")
                or stripped.startswith("async def ")
                or stripped.startswith("import ")
                or stripped.startswith("from ")
                or stripped.startswith("@")
            ):
                skeleton_lines.append(line)
        return "\n".join(skeleton_lines)
