from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services import STORE_URL, recommend_perfumes


def home(request: HttpRequest):
    return render(request, "recommender/luxury_quiz.html", {"store_url": STORE_URL})


def fragrance_discovery(request: HttpRequest):
    return render(request, "recommender/luxury_quiz.html", {"store_url": STORE_URL})


def build_api_response(*, recommendations=None, profile=None, message="", status=200, errors=None):
    payload = {
        "store_url": STORE_URL,
        "message": message,
    }

    if profile is not None:
        payload["profile"] = profile
    if recommendations is not None:
        payload["recommendations"] = recommendations
    if errors is not None:
        payload["errors"] = errors

    return JsonResponse(payload, status=status)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def recommend(request: HttpRequest):
    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type:
            try:
                payload = json.loads(request.body or "{}")
            except json.JSONDecodeError:
                return build_api_response(
                    message="Request body must be valid JSON.",
                    errors=["invalid_json"],
                    status=400,
                )
        else:
            payload = request.POST.dict()
    else:
        payload = request.GET.dict()

    results = recommend_perfumes(payload)
    return build_api_response(
        recommendations=results["recommendations"],
        profile=results["profile"],
        message=results["message"],
        status=results["status"],
        errors=results["errors"],
    )
