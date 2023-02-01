from django.contrib import admin

# from django.contrib.admin import ModelAdmin
from .models import Model, Project, File, Training_Job, Training_Job_Monitoring


admin.site.register(Project)
admin.site.register(File)
admin.site.register(Training_Job)
admin.site.register(Training_Job_Monitoring)
admin.site.register(Model)
