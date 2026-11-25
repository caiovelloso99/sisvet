# SisVet

Sistema web de gestão para clínicas veterinárias: cadastros de tutores e pets, agenda, prontuário com assinatura, exames e anexos, controle de vacinas. Multi-clínica, com dados isolados por clínica.

## Requisitos

- Python 3.14
- PostgreSQL 14 ou superior (para produção ou testes completos). Em desenvolvimento, o SQLite funciona sem instalação.

## Instalação (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Edite o `.env`: troque `DJANGO_SECRET_KEY` e escolha o banco (`DB_ENGINE=sqlite` ou `postgres`).

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Acesse `http://localhost:8000/login/`. Para que um usuário veja as telas de tutores, agenda e prontuário, ele precisa de um vínculo com uma clínica (criado em `/admin/`, seção **Vínculos**).

## Testes

```powershell
.\.venv\Scripts\python.exe manage.py test
```

## Estrutura

- `config/`: configurações, URLs e WSGI
- `clinicas/`: clínica, unidade, vínculo usuário-clínica e a base de isolamento por clínica
- `tutores/`: tutores e pets
- `agenda/`: agendamentos com checagem de conflito de horário
- `prontuario/`: atendimentos (com assinatura), exames, anexos e vacinas
- `templates/`: telas em HTML, sem dependência de frontend

## Regras de negócio importantes

- Todo dado pertence a uma clínica, e as consultas filtram pela clínica do usuário.
- Conteúdo clínico (prontuário, exames, vacinas, anexos) só é acessado por veterinário e dono.
- Atendimentos assinados, exames e anexos não podem ser alterados nem apagados.
- Anexos são guardados em `media_privado/`, fora do site, e entregues só pela tela de download com checagem de permissão.

Veja `CLAUDE.md` para as convenções do projeto.
