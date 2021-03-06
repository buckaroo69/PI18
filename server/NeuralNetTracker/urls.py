"""NeuralNetTracker URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from app import views
from django.contrib.auth import views as auth_views
from app.forms import CustomAuthenticationForm

urlpatterns = [
    path('', views.index, name="Frontpage"),
    path('simulations/', views.simulation_list, name="SimulationList"),
    path('simulations/content/', views.simulation_list_content, name="SimulationListContent"),
    path('simulations/create/', views.simulation_create, name="SimulationCreate"),
    path('simulations/command/<int:id>/<str:command>', views.simulation_command, name="SimulationCommand"),
    path('simulations/<int:id>/', views.simulation_info, name="SimulationInfo"),
    path('simulations/<int:id>/content1/', views.simulation_info_content1, name="SimulationInfoContent1"),
    path('simulations/<int:id>/content2/', views.simulation_info_content2, name="SimulationInfoContent2"),
    path('simulations/<int:id>/context/', views.simulation_info_context, name="SimulationInfoContext"),
    path('accounts/register/', views.signup, name="Register"),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html', authentication_form=CustomAuthenticationForm), name="Login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="/"), name="Logout"),
    path('users/', views.users, name="Users"),
    path('users/<str:id>/', views.userinfo, name="UserInfo"),
]
