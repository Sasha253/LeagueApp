from django.contrib import admin

from .models import Club, Night


class NightInline(admin.TabularInline):
    model = Night
    extra = 0


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]
    inlines = [NightInline]
