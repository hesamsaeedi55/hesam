from django.db import models
import os
from django.conf import settings
from django.utils import timezone

# Create your models here.

class EditedImage(models.Model):
    """Model to store uploaded and edited images."""
    original_image = models.ImageField(upload_to='edited_images/originals/')
    edited_image = models.ImageField(upload_to='edited_images/edited/', blank=True, null=True)
    upload_date = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Image {self.id} - {os.path.basename(self.original_image.name)}"
    
    def delete(self, *args, **kwargs):
        """
        Override delete to handle image file deletion carefully.
        We ensure the image file exists before trying to delete it.
        """
        try:
            # Delete the original image file if it exists
            if self.original_image and hasattr(self.original_image, 'path'):
                if os.path.isfile(self.original_image.path):
                    os.remove(self.original_image.path)
            
            # Delete the edited image file if it exists
            if self.edited_image and hasattr(self.edited_image, 'path'):
                if os.path.isfile(self.edited_image.path):
                    os.remove(self.edited_image.path)
        except Exception as e:
            print(f"Error deleting image files: {e}")
                
        super().delete(*args, **kwargs)


class InteractiveImage(models.Model):
    """Model to store images with interactive coordinate regions."""
    name = models.CharField(max_length=200, blank=True, help_text="Optional name for this image")
    image = models.ImageField(upload_to='interactive_images/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name or f"Interactive Image {self.id}"
    
    def delete(self, *args, **kwargs):
        """Delete image file when model is deleted."""
        try:
            if self.image and hasattr(self.image, 'path'):
                if os.path.isfile(self.image.path):
                    os.remove(self.image.path)
        except Exception as e:
            print(f"Error deleting image file: {e}")
        super().delete(*args, **kwargs)


class InteractiveRegion(models.Model):
    """Model to store coordinate regions for interactive images."""
    interactive_image = models.ForeignKey(
        InteractiveImage, 
        on_delete=models.CASCADE, 
        related_name='regions'
    )
    region_id = models.CharField(max_length=100, help_text="Unique identifier (e.g., 'watch', 'suit', 'boots')")
    label = models.CharField(max_length=200, help_text="Display name (e.g., 'Watch', 'Suit')")
    x_percent = models.DecimalField(
        max_digits=6, 
        decimal_places=4, 
        help_text="X coordinate as percentage (0.0 to 1.0)"
    )
    y_percent = models.DecimalField(
        max_digits=6, 
        decimal_places=4, 
        help_text="Y coordinate as percentage (0.0 to 1.0)"
    )
    width_percent = models.DecimalField(
        max_digits=6, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Width as percentage (optional, for region size)"
    )
    height_percent = models.DecimalField(
        max_digits=6, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Height as percentage (optional, for region size)"
    )
    color = models.CharField(
        max_length=7, 
        default='#3B82F6',
        help_text="Hex color code for the highlight (e.g., #3B82F6)"
    )
    icon = models.CharField(
        max_length=50, 
        blank=True,
        help_text="SF Symbol name or icon identifier (optional)"
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    
    class Meta:
        ordering = ['order', 'region_id']
        unique_together = [['interactive_image', 'region_id']]
    
    def __str__(self):
        return f"{self.label} on {self.interactive_image}"
