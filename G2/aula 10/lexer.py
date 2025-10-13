"""
    - Palavras-chave: function -> classe 'definição de função'
    - Identificadores: com ($[A-Za-z_]\w*) e sem ($-less) prefixo $
    - Delimitadores: { } ( )
    - Separadores: , ;
    - Atribuição: =
    - Operadores matemáticos: + - * /
    - Literais numéricos: inteiros/decimais
    - Strings: simples e duplas, com escape de barra invertida
    - Comentários: //... e /* ... */
    - Espaços: ignorados, mas atualizam posição
"""

import argparse
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class Token:
    linha: int
    coluna: int
    classe: str
    lexema: str

class Lexer:
    

    # Compila os padrões uma única vez
    _re_ws = re.compile(r"\s+", re.MULTILINE)
    _re_comment_line = re.compile(r"//[^\n]*")
    _re_comment_block = re.compile(r"/\*[\s\S]*?\*/")

    # Strings com escapes
    _re_string_s = re.compile(r"'([^'\\]|\\.)*'")
    _re_string_d = re.compile(r'"([^"\\]|\\.)*"')

    # Palavras-chave (por enquanto, apenas 'function' mapeada como definição de função)
    _re_kw_function = re.compile(r"\bfunction\b")

    # Identificadores
    _re_ident_dollar = re.compile(r"\$[A-Za-z_]\w*")
    _re_ident_plain = re.compile(r"[A-Za-z_]\w*")

    # Números (inteiros/decimais)
    _re_number = re.compile(r"\d+(?:\.\d+)?")

    # Delimitadores e separadores
    _re_delimiter = re.compile(r"[{}\(\)]")
    _re_separator = re.compile(r"[;,]")

    # Operadores
    _re_assign = re.compile(r"=")             # atribuição simples
    _re_math = re.compile(r"[+\-*/]")         # operadores matemáticos

    def __init__(self, include_comments: bool = False, errors_as_tokens: bool = False, strict: bool = False, show_col: bool = False):
        self.include_comments = include_comments
        self.errors_as_tokens = errors_as_tokens
        self.strict = strict
        self.show_col = show_col

    def tokenize(self, text: str) -> List[Token]:
        tokens: List[Token] = []
        i = 0
        linha = 1
        coluna = 1
        n = len(text)

        # Ordem dos padrões é crítica (maximal munch / evitar ambiguidades)
        patterns: List[Tuple[re.Pattern, Optional[str]]] = [
            # Comentários (antes de strings/ids). Se include_comments=False, tratamos como 'ignorar'
            (self._re_comment_block, "comentário"),
            (self._re_comment_line,  "comentário"),

            # Strings
            (self._re_string_s, "string"),
            (self._re_string_d, "string"),

            # Palavras-chave específicas
            (self._re_kw_function, "definição de função"),

            # Identificadores
            (self._re_ident_dollar, "identificador"),
            (self._re_ident_plain,  "identificador"),

            # Números
            (self._re_number, "literal numérico"),

            # Delimitadores / separadores
            (self._re_delimiter, "delimitador"),
            (self._re_separator, "separador"),

            # Operadores
            (self._re_assign, "atribuição"),
            (self._re_math, "operador matemático"),
        ]

        while i < n:
            # Espaços/brancos (sempre ignorados, mas atualizam linha/coluna)
            m = self._re_ws.match(text, i)
            if m:
                consumed = m.group(0)
                nl = consumed.count("\n")
                if nl:
                    linha += nl
                    # coluna = 1 na linha seguinte + comprimento após a última quebra
                    pos_ult = consumed.rfind("\n")
                    coluna = len(consumed) - (pos_ult + 1) + 1
                else:
                    coluna += len(consumed)
                i = m.end()
                if i >= n:
                    break

            # Comentários e demais padrões
            matched = False
            for regex, classe in patterns:
                m = regex.match(text, i)
                if not m:
                    continue

                lexema = m.group(0)
                start_linha, start_coluna = linha, coluna

                # Comentários: incluir ou ignorar
                if classe == "comentário" and not self.include_comments:
                    # Apenas atualizar posição
                    nl = lexema.count("\n")
                    if nl:
                        linha += nl
                        pos_ult = lexema.rfind("\n")
                        coluna = len(lexema) - (pos_ult + 1) + 1
                    else:
                        coluna += len(lexema)
                    i = m.end()
                    matched = True
                    break

                tokens.append(Token(start_linha, start_coluna, classe, lexema))

                # Atualiza posição
                nl = lexema.count("\n")
                if nl:
                    linha += nl
                    pos_ult = lexema.rfind("\n")
                    coluna = len(lexema) - (pos_ult + 1) + 1
                else:
                    coluna += len(lexema)

                i = m.end()
                matched = True
                break

            if matched:
                continue

            # Nenhum padrão casou — erro léxico
            ch = text[i]
            if self.errors_as_tokens:
                tokens.append(Token(linha, coluna, "erro", ch))
                if ch == "\n":
                    linha += 1
                    coluna = 1
                else:
                    coluna += 1
                i += 1
                continue

            if self.strict:
                # Mensagem objetiva e verificável: posição e caractere
                raise ValueError(f"Erro léxico na linha {linha}, coluna {coluna}: caractere inesperado {repr(ch)}")

            # Comportamento padrão: pular caractere inválido e continuar
            if ch == "\n":
                linha += 1
                coluna = 1
            else:
                coluna += 1
            i += 1

        return tokens

def imprimir_tokens(tokens: List[Token], show_col: bool = False) -> None:
    for t in tokens:
        if show_col:
            print(f"Posição linha {t.linha}, coluna {t.coluna}: classe {t.classe}, lexema {t.lexema}")
        else:
            print(f"Posição linha {t.linha}: classe {t.classe}, lexema {t.lexema}")

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analisador léxico simples (imprime tokens no terminal)."
    )
    parser.add_argument("arquivo", help="Caminho do arquivo-fonte de entrada (UTF-8).")
    parser.add_argument("--show-col", action="store_true", help="Exibe coluna junto com a linha.")
    parser.add_argument("--include-comments", action="store_true", help="Inclui comentários como tokens.")
    parser.add_argument("--errors-as-tokens", action="store_true", help="Emite tokens de classe 'erro' para caracteres inválidos.")
    parser.add_argument("--strict", action="store_true", help="Interrompe ao encontrar erro léxico (ignora --errors-as-tokens).")

    args = parser.parse_args(argv)

    try:
        with open(args.arquivo, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"Falha ao abrir arquivo: {e}", file=sys.stderr)
        return 2

    lexer = Lexer(
        include_comments=args.include_comments,
        errors_as_tokens=args.errors_as_tokens,
        strict=args.strict,
        show_col=args.show_col,
    )

    try:
        tokens = lexer.tokenize(text)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    imprimir_tokens(tokens, show_col=args.show_col)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
