from django.contrib import admin

# Register your models here.
from app.models import Simulation, Update, Tagged, ExtraMetrics

admin.site.register(Simulation)
admin.site.register(Update)
admin.site.register(Tagged)
admin.site.register(ExtraMetrics)


