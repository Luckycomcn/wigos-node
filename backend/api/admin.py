# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import WIGOSNodeUser


class WIGOSNodeUserAdmin(UserAdmin):
    # Order fields displayed in the admin list view
    list_display = ('email', 'username', 'is_staff', 'is_active')
    # Filter users based on staff or active status
    list_filter = ('is_staff', 'is_active')
    # Order items in the admin view by email
    ordering = ('email',)

# # Register the model and the admin class together
admin.site.register(WIGOSNodeUser, WIGOSNodeUserAdmin)
