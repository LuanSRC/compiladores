#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
from typing import List

# Importar dataclass ANTES de usá-la
try:
    from dataclasses import dataclass
except ImportError:
    # Compatibilidade mínima com Python 3.6 (não formata, só permite decorar)
    def dataclass(cls):
        return cls

# -----------------------------
# Especificação mínima da MineLang
# -----------------------------
KEYWORDS_MAP = {
    "OPERACAO": "def",
    "SE_RISCO": "if",
    "SENAO_OPERADOR": "else",
    "ENQUANTO_ESCANEANDO": "while",
    "ALERTAR_EQUIPE": "print",
    "MARCAR_AREA": "=",
    "INTENSIFICAR": "+",
    "DESATIVAR": "-",
    "AMPLIFICAR": "*",
    "DISTRIBUIR_RECURSOS": "/",
    "RETORNAR_STATUS": "return",
}

# Cabeçalhos de bloco em Python (devem terminar com ':')
HEADER_TOKENS = {"def", "if", "else", "while"}

# Palavras-chave que DEVEM vir seguidas de espaço
# (para evitar 'defnome' e 'returnx')
NEED_SPACE_AFTER = {"def", "return", "if", "while"}

# Operadores relacionais aceitos tal como em Python
RELATIONALS = {"==", "!=", ">", "<", ">=", "<="}
MULTI_CHAR_OPS = RELATIONALS | {"//", "**", "<<", ">>", "+=", "-=", "*=", "/=", "%="}

# -----------------------------
# Tipos e erros
# -----------------------------
class LexerError(Exception):
    pass

class ParseError(Exception):
    pass

@dataclass
class Token:
    kind: str   # IDENT, NUMBER, STRING, LBRACE, RBRACE, NEWLINE, OP, LPAREN, ...
    value: str
    line: int
    col: int

# -----------------------------
# Lexer: tokeniza sem tocar em strings/comentários
# -----------------------------
def lex(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    def peek(k=0):
        return source[i + k] if i + k < n else ""

    def advance():
        nonlocal i, col
        ch = source[i]
        i += 1
        col += 1
        return ch

    def emit(kind, value, l, c):
        tokens.append(Token(kind, value, l, c))

    while i < n:
        ch = peek()

        # Quebra de linha
        if ch == "\n":
            emit("NEWLINE", "\n", line, col)
            advance()
            line += 1
            col = 1
            continue

        # Espaços e tabs
        if ch in " \t\r":
            advance()
            continue

        # Comentário de linha: #
        if ch == "#":
            while i < n and peek() != "\n":
                advance()
            continue

        # Comentário de bloco: /* ... */
        if ch == "/" and peek(1) == "*":
            start_l, start_c = line, col
            advance(); advance()
            while True:
                if i >= n:
                    raise LexerError(f"Comentário de bloco não fechado iniciado em {start_l}:{start_c}")
                if peek() == "\n":
                    advance()
                    line += 1
                    col = 1
                    continue
                if peek() == "*" and peek(1) == "/":
                    advance(); advance()
                    break
                advance()
            continue

        # Strings: "..."
        if ch == '"':
            start_l, start_c = line, col
            buf = [advance()]  # abre aspas
            escaped = False
            while i < n:
                c = advance()
                buf.append(c)
                if c == "\n":
                    line += 1
                    col = 1
                if escaped:
                    escaped = False
                    continue
                if c == "\\":
                    escaped = True
                    continue
                if c == '"':
                    break
            else:
                raise LexerError(f'String não fechada iniciada em {start_l}:{start_c}')
            emit("STRING", "".join(buf), start_l, start_c)
            continue

        # Identificadores e palavras
        if ch.isalpha() or ch == "_":
            start_l, start_c = line, col
            buf = [advance()]
            while i < n and (peek().isalnum() or peek() == "_"):
                buf.append(advance())
            ident = "".join(buf)

            # ------------------------------------------------------
            # VALIDAÇÃO LÉXICA DAS PALAVRAS-CHAVE MINELANG
            # ------------------------------------------------------
            # Regra (decisão de design):
            # - Se o identificador estiver TODO em maiúsculas (ex.: OPERACAO, SE_RISCO)
            # - E NÃO estiver em KEYWORDS_MAP
            # => Consideramos que o operador tentou usar um comando MineLang
            #    e escreveu errado -> erro léxico.
            #
            # Isso impede gerar Python inválido quando, por exemplo:
            #   OPERAÇAO, OPERACAOX, SE_RISKO etc.
            if ident.isupper() and ident not in KEYWORDS_MAP:
                raise LexerError(
                    f"Palavra-chave MineLang desconhecida '{ident}' em {start_l}:{start_c}. "
                    f"Verifique se o nome do comando está escrito corretamente."
                )

            emit("IDENT", ident, start_l, start_c)
            continue

        # Números (inteiros/floats simples)
        if ch.isdigit():
            start_l, start_c = line, col
            buf = [advance()]
            is_float = False
            while i < n and (peek().isdigit() or (peek() == "." and not is_float)):
                if peek() == ".":
                    is_float = True
                buf.append(advance())
            emit("NUMBER", "".join(buf), start_l, start_c)
            continue

        # Operadores compostos de 2 chars
        start_l, start_c = line, col
        two = ch + peek(1)
        if two in MULTI_CHAR_OPS:
            emit("OP", two, start_l, start_c)
            advance(); advance()
            continue

        # Símbolos simples
        if ch in "{}()[];.,:+-*/%<>=!&|^~":
            kind = {
                "{": "LBRACE",
                "}": "RBRACE",
                "(": "LPAREN",
                ")": "RPAREN",
                "[": "LBRACK",
                "]": "RBRACK",
                ";": "SEMI",
                ",": "COMMA",
                ".": "DOT",
            }.get(ch, "OP")
            emit(kind, ch, line, col)
            advance()
            continue

        raise LexerError(f"Caractere inválido '{ch}' em {line}:{col}")

    # Garante newline final para simplificar parsing
    tokens.append(Token("NEWLINE", "\n", line, col))
    return tokens

# -----------------------------
# Emitter + Parser (tradução e indentação)
# -----------------------------
class Emitter:
    def __init__(self):
        self.lines: List[str] = []
        self.current: List[str] = []
        self.indent = 0
        self.need_indent = True

    def _emit_indent_if_needed(self):
        if self.need_indent:
            self.current.append(" " * (self.indent * 4))
            self.need_indent = False

    def emit_text(self, text: str):
        self._emit_indent_if_needed()
        self.current.append(text)

    def emit_space(self):
        self._emit_indent_if_needed()
        # Evita múltiplos espaços consecutivos
        if not self.current or (self.current and not self.current[-1].endswith(" ")):
            self.current.append(" ")

    def newline(self):
        self.lines.append("".join(self.current).rstrip())
        self.current = []
        self.need_indent = True

    def open_block(self):
        self.indent += 1

    def close_block(self):
        if self.indent == 0:
            raise ParseError("Atenção, operador! Bloco fechado '}' sem ter sido aberto.")
        self.indent -= 1
        if self.current and "".join(self.current).strip():
            self.newline()

    def get_output(self) -> str:
        if self.current:
            self.newline()
        while self.lines and self.lines[-1] == "":
            self.lines.pop()
        return "\n".join(self.lines) + "\n"

def translate(tokens: List[Token]) -> str:
    out = Emitter()

    pending_header = False     # último token foi def/if/else/while (aguarda '{' para ':')
    just_closed_brace = False  # acabou de fechar '}' (pode vir SENAO_OPERADOR)
    i = 0
    n = len(tokens)

    def tok(k=0):
        return tokens[i + k] if i + k < n else None

    def emit_mapped_ident(value: str):
        nonlocal pending_header
        mapped = KEYWORDS_MAP.get(value, None)
        if mapped:
            out.emit_text(mapped)
            # espaço após certas keywords
            if mapped in NEED_SPACE_AFTER:
                out.emit_space()
            if mapped in HEADER_TOKENS:
                pending_header = True
        else:
            out.emit_text(value)

    while i < n:
        t = tok()
        if t is None:
            break

        if t.kind == "NEWLINE" or t.kind == "SEMI":
            out.newline()
            just_closed_brace = False
            i += 1
            continue

        if t.kind == "LBRACE":
            if pending_header:
                out.emit_text(":")
                pending_header = False
            out.newline()
            out.open_block()
            i += 1
            continue

        if t.kind == "RBRACE":
            out.close_block()
            just_closed_brace = True
            i += 1
            continue

        if t.kind in ("STRING", "NUMBER"):
            out.emit_text(t.value)
            just_closed_brace = False
            i += 1
            continue

        if t.kind == "IDENT":
            if t.value == "SENAO_OPERADOR" and just_closed_brace:
                emit_mapped_ident(t.value)   # -> else
                pending_header = True
                just_closed_brace = False
                i += 1
                continue
            emit_mapped_ident(t.value)
            just_closed_brace = False
            i += 1
            continue

        if t.kind == "OP":
            out.emit_text(t.value)
            just_closed_brace = False
            i += 1
            continue

        if t.kind in ("LPAREN", "RPAREN", "LBRACK", "RBRACK", "COMMA", "DOT"):
            out.emit_text(t.value)
            just_closed_brace = False
            i += 1
            continue

        raise ParseError(f"Token inesperado {t.kind} '{t.value}' em {t.line}:{t.col}")

    result = out.get_output()

    if out.indent != 0:
        raise ParseError("Atenção, operador! Bloco aberto não foi desarmado: falta '}'.")

    return result

# -----------------------------
# CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Tradutor MineLang → Python")
    parser.add_argument("entrada", help="Arquivo .mina de entrada")
    parser.add_argument("-o", "--output", help="Arquivo .py de saída (padrão: mesmo nome com .py)")
    args = parser.parse_args()

    try:
        with open(args.entrada, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"Erro ao ler '{args.entrada}': {e}", file=sys.stderr)
        sys.exit(1)

    try:
        tokens = lex(src)
        py = translate(tokens)
    except (LexerError, ParseError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    outpath = args.output
    if not outpath:
        if args.entrada.lower().endswitAh(".mina"):
            outpath = args.entrada[:-5] + ".py"
        else:
            outpath = args.entrada + ".py"

    try:
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(py)
    except OSError as e:
        print(f"Erro ao escrever '{outpath}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: gerado '{outpath}'")

if __name__ == "__main__":
    main()
