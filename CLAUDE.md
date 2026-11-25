# SisVet: sistema de gestão para clínicas veterinárias

Sistema web multi-clínica (SaaS) com agenda, prontuário, vacinas, financeiro, caixa, estoque e DRE por unidade. Público: clínicas veterinárias pequenas e médias no Brasil.

## Stack

- Python 3.14 e Django 6.0 (versão fixada em `requirements.txt`)
- Banco: SQLite em desenvolvimento; PostgreSQL em produção (`DB_ENGINE=postgres`)
- Idioma do código: nomes de modelos, campos e apps em português (domínio). Mensagens para o usuário em pt-BR.
- Fuso horário: `America/Sao_Paulo`

## Comandos

Use sempre o Python do ambiente virtual:

- Ativar: `.venv\Scripts\activate`
- Instalar dependências: `pip install -r requirements.txt`
- Migrar banco: `python manage.py migrate`
- Gerar migrações: `python manage.py makemigrations`
- Rodar servidor: `python manage.py runserver`
- Testes: `python manage.py test`
- Verificação: `python manage.py check`

## Estrutura

- `config/`: settings, urls e wsgi
- `clinicas/`: Clinica, Unidade, Vinculo (usuário ↔ clínica com papel) e a base `ClinicaModel`; também `TenantAdminMixin` e `clinica_do_usuario` em `admin.py`
- `tutores/`: Tutor e Pet
- `templates/` e `static/`: arquivos globais
- Planilhas e CSVs na raiz (validação com clínicas): não são parte do código

## Regras obrigatórias

1. **Isolamento por clínica (multi-tenant).** Todo modelo de negócio herda de `clinicas.models.ClinicaModel` (ou tem FK `clinica`). Nenhuma consulta pode retornar dados de outra clínica. Views e admin devem filtrar pela clínica do usuário logado. Toda regra nova de isolamento precisa de teste em `clinicas/tests.py`.
2. **Dados pessoais (LGPD).** Tutores e pets são dados pessoais. Não logar CPF, telefone ou e-mail em logs ou mensagens de erro. Não colocar dados reais em fixtures ou testes.
3. **Prontuário.** Registros clínicos não devem ser apagados fisicamente. Use inativação ou versionamento. Definir a regra de retenção com base nas normas do CFMV antes do piloto.
4. **Segredos.** Nunca commitar `.env`, senhas ou chaves. Use `.env.example` como modelo.
5. **Dinheiro.** Valores monetários usam `DecimalField`, nunca `float`.
6. **Migrações.** Sempre gerar e revisar migrações; não editar migrações já aplicadas.

## Convenções de código

- Mantenha apps pequenas e com responsabilidade clara.
- Prefira Class-Based Views do Django e formulários de `forms.py`.
- Textos de interface e `verbose_name` em português com acentuação correta.
- Testes ficam no `tests.py` de cada app, com `TestCase`.

## Próximos passos planejados

1. Telas próprias de cadastro de tutores e pets (fora do admin).
2. Agenda por veterinário.
3. Prontuário e vacinas.
4. Financeiro e fechamento de caixa.
5. Estoque e PDV.
6. Integrações: emissão fiscal, WhatsApp e pagamentos (fase 2).
