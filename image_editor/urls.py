from django.urls import path
from . import views

app_name = 'image_editor'

urlpatterns = [
    path('', views.editor_home, name='home'),
    path('<int:image_id>/', views.edit_image, name='edit_image'),
    path('<int:image_id>/rotate/', views.rotate_image, name='rotate_image'),
    path('<int:image_id>/crop/', views.crop_image, name='crop_image'),
    path('<int:image_id>/download/', views.download_image, name='download_image'),
    path('update/<int:image_id>/', views.update_image, name='update_image'),
    
    # Interactive Image Coordinate Mapper
    path('interactive-mapper/', views.interactive_image_mapper, name='interactive_mapper'),
    path('api/interactive/test/', views.test_interactive_setup, name='test_interactive_setup'),
    path('api/interactive/upload/', views.upload_interactive_image, name='upload_interactive_image'),
    path('api/interactive/<int:image_id>/regions/', views.save_interactive_regions, name='save_interactive_regions'),
    path('api/interactive/<int:image_id>/', views.get_interactive_image, name='get_interactive_image'),
    path('api/interactive/', views.api_interactive_images, name='api_interactive_images'),
    path('api/interactive/<int:image_id>/delete/', views.delete_interactive_image, name='delete_interactive_image'),
] 