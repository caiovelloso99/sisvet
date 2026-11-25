from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from clinicas.admin import clinica_do_usuario

from .forms import PetForm, TutorForm
from .models import Pet, Tutor


class ClinicaMixin(LoginRequiredMixin):
    """Restringe as views à clínica do usuário logado."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and clinica_do_usuario(request.user) is None:
            raise PermissionDenied("Seu usuário não está vinculado a nenhuma clínica.")
        return super().dispatch(request, *args, **kwargs)

    @property
    def clinica(self):
        return clinica_do_usuario(self.request.user)

    def get_queryset(self):
        return super().get_queryset().filter(clinica=self.clinica)


class TutorListView(ClinicaMixin, ListView):
    model = Tutor
    template_name = "tutores/tutor_list.html"
    context_object_name = "tutores"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(nome__icontains=q)
                | Q(telefone__icontains=q)
                | Q(cpf__icontains=q)
                | Q(email__icontains=q)
            )
        return qs.order_by("nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        return context


class TutorDetailView(ClinicaMixin, DetailView):
    model = Tutor
    template_name = "tutores/tutor_detail.html"
    context_object_name = "tutor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pets"] = self.object.pets.order_by("nome")
        return context


class TutorCreateView(ClinicaMixin, CreateView):
    model = Tutor
    form_class = TutorForm
    template_name = "tutores/tutor_form.html"

    def form_valid(self, form):
        form.instance.clinica = self.clinica
        messages.success(self.request, "Tutor cadastrado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tutores:tutor_detail", args=[self.object.pk])


class TutorUpdateView(ClinicaMixin, UpdateView):
    model = Tutor
    form_class = TutorForm
    template_name = "tutores/tutor_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Tutor atualizado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tutores:tutor_detail", args=[self.object.pk])


class PetCreateView(ClinicaMixin, CreateView):
    model = Pet
    form_class = PetForm
    template_name = "tutores/pet_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["clinica"] = self.clinica
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        tutor_id = self.request.GET.get("tutor")
        if tutor_id:
            initial["tutor"] = get_object_or_404(Tutor, pk=tutor_id, clinica=self.clinica)
        return initial

    def form_valid(self, form):
        form.instance.clinica = self.clinica
        messages.success(self.request, "Pet cadastrado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tutores:tutor_detail", args=[self.object.tutor_id])


class PetUpdateView(ClinicaMixin, UpdateView):
    model = Pet
    form_class = PetForm
    template_name = "tutores/pet_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["clinica"] = self.clinica
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Pet atualizado com sucesso.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tutores:tutor_detail", args=[self.object.tutor_id])
