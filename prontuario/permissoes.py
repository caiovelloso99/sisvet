from clinicas.models import Vinculo

# Papéis que podem ler e escrever conteúdo clínico (prontuário e vacinas).
# Recepção e financeiro não acessam dados clínicos (LGPD: minimização de dados).
PAPEIS_CLINICOS = (Vinculo.Papel.VETERINARIO, Vinculo.Papel.DONO)


def pode_acessar_clinico(user):
    vinculo = getattr(user, "vinculo", None) if user.is_authenticated else None
    return vinculo is not None and vinculo.papel in PAPEIS_CLINICOS
