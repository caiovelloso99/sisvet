from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from agenda.models import Agendamento
from clinicas.admin import clinica_do_usuario
from tutores.models import Pet

from .arquivos import nome_original_seguro
from .forms import AnexoForm, AtendimentoForm, ExameForm, VacinaForm
from .models import Anexo, Atendimento, AtendimentoBloqueado, Exame, Vacina
from .permissoes import pode_acessar_clinico


class ClinicoMixin(LoginRequiredMixin):
    """Somente usuários com papel clínico (veterinário ou dono) acessam o prontuário."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not pode_acessar_clinico(request.user):
            raise PermissionDenied("Seu papel não tem acesso ao prontuário.")
        return super().dispatch(request, *args, **kwargs)

    @property
    def clinica(self):
        return clinica_do_usuario(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["clinica"] = self.clinica
        return kwargs


class PetProntuarioView(ClinicoMixin, DetailView):
    model = Pet
    template_name = "prontuario/pet_prontuario.html"
    context_object_name = "pet"

    def get_queryset(self):
        return Pet.objects.filter(clinica=self.clinica).select_related("tutor")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["atendimentos"] = self.object.atendimentos.select_related("veterinario")
        context["vacinas"] = self.object.vacinas.select_related("veterinario")
        context["exames"] = self.object.exames.select_related("veterinario")
        return context


class AtendimentoDetailView(ClinicoMixin, DetailView):
    model = Atendimento
    template_name = "prontuario/atendimento_detail.html"
    context_object_name = "atendimento"

    def get_queryset(self):
        return Atendimento.objects.filter(clinica=self.clinica).select_related("pet", "pet__tutor", "veterinario")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exames"] = self.object.exames.all()
        context["anexos"] = self.object.anexos.all()
        return context


class AtendimentoCreateView(ClinicoMixin, CreateView):
    model = Atendimento
    form_class = AtendimentoForm
    template_name = "prontuario/atendimento_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["data_hora"] = f"{timezone.localtime():%Y-%m-%dT%H:%M}"
        pet_id = self.request.GET.get("pet")
        if pet_id:
            initial["pet"] = get_object_or_404(Pet, pk=pet_id, clinica=self.clinica)
        agendamento_id = self.request.GET.get("agendamento")
        if agendamento_id:
            ag = get_object_or_404(Agendamento, pk=agendamento_id, clinica=self.clinica)
            initial["agendamento"] = ag
            initial["pet"] = ag.pet
        return initial

    def form_valid(self, form):
        form.instance.clinica = self.clinica
        form.instance.veterinario = self.request.user
        messages.success(self.request, "Atendimento registrado. Revise e assine quando concluir.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("prontuario:atendimento_detail", args=[self.object.pk])


class AtendimentoUpdateView(ClinicoMixin, UpdateView):
    model = Atendimento
    form_class = AtendimentoForm
    template_name = "prontuario/atendimento_form.html"

    def get_queryset(self):
        return Atendimento.objects.filter(clinica=self.clinica)

    def get(self, request, *args, **kwargs):
        if self.get_object().assinado:
            messages.error(request, "Atendimento assinado não pode ser alterado.")
            return redirect("prontuario:atendimento_detail", pk=self.kwargs["pk"])
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.get_object().assinado:
            messages.error(request, "Atendimento assinado não pode ser alterado.")
            return redirect("prontuario:atendimento_detail", pk=self.kwargs["pk"])
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except AtendimentoBloqueado as erro:
            messages.error(self.request, str(erro))
            return redirect("prontuario:atendimento_detail", pk=self.object.pk)
        messages.success(self.request, "Atendimento atualizado.")
        return response

    def get_success_url(self):
        return reverse("prontuario:atendimento_detail", args=[self.object.pk])


class AtendimentoAssinarView(ClinicoMixin, View):
    """Assina o atendimento: a partir daí o registro fica somente leitura."""

    def post(self, request, pk):
        atendimento = get_object_or_404(Atendimento, pk=pk, clinica=self.clinica)
        try:
            atendimento.assinar(request.user)
        except (AtendimentoBloqueado, ValidationError) as erro:
            messages.error(request, " ".join(getattr(erro, "messages", [str(erro)])))
        else:
            messages.success(request, "Atendimento assinado. Ele não poderá mais ser alterado.")
        return redirect("prontuario:atendimento_detail", pk=pk)


class ExameCreateView(ClinicoMixin, CreateView):
    model = Exame
    form_class = ExameForm
    template_name = "prontuario/exame_form.html"

    def get_initial(self):
        initial = super().get_initial()
        pet_id = self.request.GET.get("pet")
        if pet_id:
            initial["pet"] = get_object_or_404(Pet, pk=pet_id, clinica=self.clinica)
        atendimento_id = self.request.GET.get("atendimento")
        if atendimento_id:
            at = get_object_or_404(Atendimento, pk=atendimento_id, clinica=self.clinica)
            initial["atendimento"] = at
            initial["pet"] = at.pet
        return initial

    def form_valid(self, form):
        form.instance.clinica = self.clinica
        form.instance.veterinario = self.request.user
        messages.success(self.request, "Exame registrado. Agora você pode anexar o laudo.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("prontuario:exame_detail", args=[self.object.pk])


class ExameDetailView(ClinicoMixin, DetailView):
    model = Exame
    template_name = "prontuario/exame_detail.html"
    context_object_name = "exame"

    def get_queryset(self):
        return Exame.objects.filter(clinica=self.clinica).select_related("pet", "pet__tutor", "veterinario")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["anexos"] = self.object.anexos.all()
        return context


class AnexoCreateView(ClinicoMixin, CreateView):
    """Envia um arquivo ligado a um exame (?exame=) ou direto ao pet (?pet=)."""

    model = Anexo
    form_class = AnexoForm
    template_name = "prontuario/anexo_form.html"

    def _alvo(self):
        if not hasattr(self, "_alvo_cache"):
            exame_id = self.request.GET.get("exame") or self.request.POST.get("exame_id")
            pet_id = self.request.GET.get("pet") or self.request.POST.get("pet_id")
            if exame_id:
                exame = get_object_or_404(Exame, pk=exame_id, clinica=self.clinica)
                self._alvo_cache = (exame.pet, exame)
            elif pet_id:
                self._alvo_cache = (get_object_or_404(Pet, pk=pet_id, clinica=self.clinica), None)
            else:
                raise Http404("Informe o exame ou o pet do anexo.")
        return self._alvo_cache

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pet, exame = self._alvo()
        context.update({"pet": pet, "exame": exame})
        return context

    def form_valid(self, form):
        pet, exame = self._alvo()
        arquivo = form.cleaned_data["arquivo"]
        anexo = form.save(commit=False)
        anexo.clinica = self.clinica
        anexo.pet = pet
        anexo.exame = exame
        anexo.nome_original = nome_original_seguro(arquivo.name)
        anexo.tipo_mime = form.mime_type
        anexo.tamanho_bytes = arquivo.size
        anexo.enviado_por = self.request.user
        anexo.save()
        messages.success(self.request, "Arquivo anexado com sucesso.")
        self.object = anexo
        return redirect(self.get_success_url())

    def get_success_url(self):
        if self.object.exame_id:
            return reverse("prontuario:exame_detail", args=[self.object.exame_id])
        return reverse("prontuario:pet_prontuario", args=[self.object.pet_id])


class AnexoDownloadView(ClinicoMixin, View):
    """Entrega o arquivo somente após checar papel clínico e clínica do usuário."""

    def get(self, request, pk):
        anexo = get_object_or_404(Anexo, pk=pk, clinica=self.clinica)
        abrir = request.GET.get("abrir") == "1"
        arquivo = anexo.arquivo.open("rb")
        resposta = FileResponse(arquivo, content_type=anexo.tipo_mime)
        disposicao = "inline" if abrir else "attachment"
        resposta["Content-Disposition"] = f'{disposicao}; filename="{anexo.nome_original}"'
        resposta["X-Content-Type-Options"] = "nosniff"
        resposta["Cache-Control"] = "private, no-store"
        return resposta


class VacinaCreateView(ClinicoMixin, CreateView):
    model = Vacina
    form_class = VacinaForm
    template_name = "prontuario/vacina_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["data_aplicacao"] = timezone.localdate()
        pet_id = self.request.GET.get("pet")
        if pet_id:
            initial["pet"] = get_object_or_404(Pet, pk=pet_id, clinica=self.clinica)
        return initial

    def form_valid(self, form):
        form.instance.clinica = self.clinica
        form.instance.veterinario = self.request.user
        messages.success(self.request, "Vacina registrada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("prontuario:pet_prontuario", args=[self.object.pet_id])


class VacinasAlertasView(ClinicoMixin, TemplateView):
    """Vacinas em atraso ou com próxima dose nos próximos 30 dias."""

    template_name = "prontuario/vacinas_alertas.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=30)
        vacinas = (
            Vacina.objects.filter(clinica=self.clinica, proxima_dose__isnull=False, proxima_dose__lte=limite)
            .select_related("pet", "pet__tutor")
            .order_by("proxima_dose")
        )
        context["hoje"] = hoje
        context["atrasadas"] = [v for v in vacinas if v.proxima_dose < hoje]
        context["proximas"] = [v for v in vacinas if v.proxima_dose >= hoje]
        return context
