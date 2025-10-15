%{
#include <stdio.h>
%}
%option noyywrap

%%

"int"                   { printf("TOKEN(KEYWORD,\"int\")\n"); }
"return"                { printf("TOKEN(KEYWORD,\"return\")\n"); }
[a-zA-Z_][a-zA-Z0-9_]*  { printf("TOKEN(IDENTIFIER,\"%s\")\n", yytext); }
[0-9]+                  { printf("TOKEN(NUMBER,\"%s\")\n", yytext); }
[+\-*/=]                { printf("TOKEN(OPERATOR,\"%s\")\n", yytext); }
[{}\()\[\],;]           { printf("TOKEN(SYMBOL,\"%s\")\n", yytext); }
[ \t\r\n]+              { /* ignora brancos */ }
.                       { printf("TOKEN(UNKNOWN,\"%s\")\n", yytext); }

%%

int main(void) {
    yylex();
    return 0;
}
