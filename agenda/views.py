from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, TemplateView, UpdateView

from clinicas.admin import clinica_do_usuario

from .forms import AgendamentoForm
from .models import Agendamento


class ClinicaMixin(LoginRequiredMixin):
    """Restringe as views à clínica do usuário logado."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and clinica_do_usuario(request.user) is None:
            raise PermissionDenied("Seu usuário não está vinculado a nenhuma clínica.")
        return super().dispatch(request, *args, **kwargs)

    @property
    def clinica(self):
        return clinica_do_usuario(self.request.user)


def _data_da_requisicao(request):
    """Lê ?data=AAAA-MM-DD; sem parâmetro (ou inválido), usa hoje."""
    texto = request.GET.get("data")
    if texto:
        try:
            return datetime.strptime(texto, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.localdate()


class AgendaDiaView(ClinicaMixin, TemplateView):
    template_name = "agenda/dia.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dia = _data_da_requisicao(self.request)
        inicio_dia = timezone.make_aware(datetime.combine(dia, time.min))
        fim_dia = inicio_dia + timedelta(days=1)
        agendamentos = (
            Agendamento.objects.filter(clinica=self.clinica, inicio__gte=inicio_dia, inicio__lt=fim_dia)
            .select_related("pet", "pet__tutor", "veterinario", "unidade")
            .order_by("inicio")
        )
        context.update(
            {
                "dia": dia,
                "dia_anterior": dia - timedelta(days=1),
                "dia_seguinte": dia + timedelta(days=1),
                "hoje": timezone.localdate(),
                "agendamentos": agendamentos,
                "status_choices": Agendamento.Status.choices,
            }
        )
        return context


class AgendamentoQuerysetMixin(ClinicaMixin):
    def get_queryset(self):
        return Agendamento.objects.filter(clinica=self.clinica)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["clinica"] = self.clinica
        return kwargs


class AgendamentoCreateView(AgendamentoQuerysetMixin, CreateView):
    model = Agendamento
    form_class = AgendamentoForm
    template_name = "agenda/agendamento_form.html"

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("data"):
            initial["inicio"] = f"{_data_da_requisicao(self.request):%Y-%m-%d}T08:00"
        return initial

    def form_valid(self, form):
        form.instance.clinica = self.clinica
        messages.success(self.request, "Agendamento criado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("agenda:dia") + f"?data={timezone.localtime(self.object.inicio):%Y-%m-%d}"


class AgendamentoUpdateView(AgendamentoQuerysetMixin, UpdateView):
    model = Agendamento
    form_class = AgendamentoForm
    template_name = "agenda/agendamento_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Agendamento atualizado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("agenda:dia") + f"?data={timezone.localtime(self.object.inicio):%Y-%m-%d}"


class AgendamentoStatusView(ClinicaMixin, View):
    """Muda a situação de um agendamento (confirmar, iniciar, concluir, faltou, cancelar)."""

    def post(self, request, pk):
        agendamento = get_object_or_404(Agendamento, pk=pk, clinica=self.clinica)
        novo = request.POST.get("status")
        validos = dict(Agendamento.Status.choices)
        if novo not in validos:
            messages.error(request, "Situação inválida.")
        else:
            agendamento.status = novo
            try:
                # Reativar um horário cancelado também precisa checar conflito
                agendamento.clean()
            except ValidationError as erro:
                messages.error(request, " ".join(erro.messages))
            else:
                agendamento.save(update_fields=["status"])
                messages.success(request, f"Situação alterada para {validos[novo]}.")
        return redirect(reverse("agenda:dia") + f"?data={timezone.localtime(agendamento.inicio):%Y-%m-%d}")
