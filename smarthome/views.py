from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse


def index(request):
    return HttpResponse("Xin chào. Bạn đã đến trang Smart Home Backend")