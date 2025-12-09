from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse

from .forms import ImageUploadForm
from .models import EditedImage, InteractiveImage, InteractiveRegion
from shop.utils import safe_open_image

from PIL import Image
import os
import io
import base64
import json
import warnings

# Suppress ICC profile warnings
warnings.filterwarnings('ignore', category=UserWarning, module='PIL')

def editor_home(request):
    """Home view for image editor with upload form."""
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save()
            return redirect('image_editor:edit_image', image_id=image.id)
    else:
        form = ImageUploadForm()
    
    return render(request, 'image_editor/home.html', {'form': form})

def edit_image(request, image_id):
    """View for editing an image."""
    image_obj = get_object_or_404(EditedImage, id=image_id)
    
    # Use the edited image if it exists, otherwise use the original
    image_to_display = image_obj.edited_image if image_obj.edited_image else image_obj.original_image
    
    context = {
        'image': image_obj,
        'image_url': image_to_display.url,
    }
    
    return render(request, 'image_editor/edit.html', context)

@csrf_exempt
def rotate_image(request, image_id):
    """API endpoint to rotate an image."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    image_obj = get_object_or_404(EditedImage, id=image_id)
    
    try:
        data = json.loads(request.body)
        direction = data.get('direction', 'right')
        
        if direction not in ['left', 'right']:
            return JsonResponse({'error': 'Invalid rotation direction. Use "left" or "right".'}, status=400)
        
        # Determine which image to rotate (edited if exists, otherwise original)
        source_image = image_obj.edited_image if image_obj.edited_image else image_obj.original_image
        
        if not source_image:
            return JsonResponse({'error': 'No image found to rotate'}, status=404)
        
        # Open the image with PIL
        img = safe_open_image(source_image.path)
        
        # Rotate 90 degrees in specified direction
        if direction == 'left':
            rotated_img = img.rotate(90, expand=True)
        else:  # default to right rotation
            rotated_img = img.rotate(-90, expand=True)
        
        # Save the rotated image
        output = io.BytesIO()
        img_format = source_image.name.split('.')[-1].upper()
        if img_format == 'JPG':
            img_format = 'JPEG'
        elif img_format not in ['JPEG', 'PNG', 'WEBP']:
            img_format = 'JPEG'  # Default to JPEG for unsupported formats
        
        rotated_img.save(output, format=img_format, icc_profile=None)
        output.seek(0)
        
        # Generate a filename for the edited image
        filename = f"rotated_{os.path.basename(source_image.name)}"
        
        # Save the rotated image without deleting the original
        image_obj.edited_image.save(filename, ContentFile(output.read()), save=True)
        
        return JsonResponse({
            'success': True,
            'imageUrl': image_obj.edited_image.url
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except IOError:
        return JsonResponse({'error': 'Cannot process the image file'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def crop_image(request, image_id):
    """API endpoint to crop an image."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    image_obj = get_object_or_404(EditedImage, id=image_id)
    
    try:
        data = json.loads(request.body)
        x = int(float(data.get('x', 0)))
        y = int(float(data.get('y', 0)))
        width = int(float(data.get('width', 0)))
        height = int(float(data.get('height', 0)))
        
        # Input validation
        if width <= 0 or height <= 0:
            return JsonResponse({'error': 'Invalid crop dimensions: width and height must be positive'}, status=400)
        
        # Determine which image to crop (edited if exists, otherwise original)
        source_image = image_obj.edited_image if image_obj.edited_image else image_obj.original_image
        
        # Open the image with PIL
        img = safe_open_image(source_image.path)
        
        img_width, img_height = img.size
        
        # Ensure crop coordinates are within image boundaries
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + width > img_width:
            width = img_width - x
        if y + height > img_height:
            height = img_height - y
            
        # Final validation after adjustments
        if width <= 10 or height <= 10:
            return JsonResponse({
                'error': 'Crop area too small after adjustment to image boundaries'
            }, status=400)
        
        # Perform the crop
        cropped_img = img.crop((x, y, x + width, y + height))
        
        # Save the cropped image
        output = io.BytesIO()
        img_format = source_image.name.split('.')[-1].upper()
        if img_format == 'JPG':
            img_format = 'JPEG'
        
        cropped_img.save(output, format=img_format, icc_profile=None)
        output.seek(0)
        
        # Generate a filename for the edited image
        filename = f"cropped_{os.path.basename(source_image.name)}"
        
        # Important: Don't delete the old file before saving the new one
        # Just create a new file and update the edited_image field
        image_obj.edited_image.save(filename, ContentFile(output.read()), save=True)
        
        return JsonResponse({
            'success': True,
            'imageUrl': image_obj.edited_image.url
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Invalid value in crop data: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def download_image(request, image_id):
    """View to download the edited image."""
    image_obj = get_object_or_404(EditedImage, id=image_id)
    
    # Determine which image to download (edited if exists, otherwise original)
    source_image = image_obj.edited_image if image_obj.edited_image else image_obj.original_image
    
    if not source_image:
        return HttpResponse("No image available for download", status=404)
    
    # Open the file
    with open(source_image.path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='image/jpeg')  # Adjust content type as needed
        
    # Set filename in HTTP header
    filename = os.path.basename(source_image.name)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@csrf_exempt
def update_image(request, image_id):
    """API endpoint to update an existing image."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        image_obj = get_object_or_404(EditedImage, id=image_id)
        
        # Get the new image from the request
        new_image = request.FILES.get('image')
        if not new_image:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        # Delete the old image file if it exists
        if image_obj.edited_image:
            try:
                os.remove(image_obj.edited_image.path)
            except:
                pass  # Ignore if file doesn't exist
        
        # Save the new image with the same filename as the original
        original_filename = os.path.basename(image_obj.original_image.name)
        image_obj.edited_image.save(original_filename, new_image, save=True)
        
        return JsonResponse({
            'success': True,
            'imageUrl': image_obj.edited_image.url
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Interactive Image Coordinate Mapper Views

def test_interactive_setup(request):
    """Test endpoint to verify setup is correct."""
    try:
        from .models import InteractiveImage, InteractiveRegion
        
        # Check if models are accessible
        image_count = InteractiveImage.objects.count()
        region_count = InteractiveRegion.objects.count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Interactive mapper is set up correctly!',
            'models_accessible': True,
            'image_count': image_count,
            'region_count': region_count,
            'migrations_applied': True
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': 'Setup incomplete. Migrations may not have run.',
            'error': str(e),
            'models_accessible': False,
            'migrations_applied': False,
            'fix': 'Run: python manage.py makemigrations image_editor && python manage.py migrate image_editor'
        }, status=500)

def interactive_image_mapper(request):
    """Main view for the interactive image coordinate mapper."""
    try:
        images = InteractiveImage.objects.all()[:20]  # Show recent 20 images
    except Exception as e:
        # If migrations haven't run yet, return empty list
        images = []
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"InteractiveImage model not available: {e}")
    
    return render(request, 'image_editor/interactive_mapper.html', {
        'images': images
    })


@csrf_exempt
def upload_interactive_image(request):
    """API endpoint to upload an image for coordinate mapping."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        image_file = request.FILES.get('image')
        name = request.POST.get('name', '').strip()
        
        if not image_file:
            return JsonResponse({'error': 'No image file provided'}, status=400)
        
        # Create InteractiveImage instance
        interactive_image = InteractiveImage.objects.create(
            name=name or None,
            image=image_file
        )
        
        return JsonResponse({
            'success': True,
            'imageId': interactive_image.id,
            'imageUrl': interactive_image.image.url,
            'name': interactive_image.name or f'Image {interactive_image.id}'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def save_interactive_regions(request, image_id):
    """API endpoint to save coordinate regions for an interactive image."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        interactive_image = get_object_or_404(InteractiveImage, id=image_id)
        data = json.loads(request.body)
        regions_data = data.get('regions', [])
        
        if not regions_data:
            return JsonResponse({'error': 'No regions provided'}, status=400)
        
        # Delete existing regions
        InteractiveRegion.objects.filter(interactive_image=interactive_image).delete()
        
        # Create new regions
        created_regions = []
        for idx, region_data in enumerate(regions_data):
            region = InteractiveRegion.objects.create(
                interactive_image=interactive_image,
                region_id=region_data.get('id', f'region_{idx}'),
                label=region_data.get('label', region_data.get('id', f'Region {idx}')),
                x_percent=float(region_data.get('xPercent', 0)),
                y_percent=float(region_data.get('yPercent', 0)),
                width_percent=float(region_data.get('widthPercent')) if region_data.get('widthPercent') else None,
                height_percent=float(region_data.get('heightPercent')) if region_data.get('heightPercent') else None,
                color=region_data.get('color', '#3B82F6'),
                icon=region_data.get('icon', ''),
                order=idx
            )
            created_regions.append({
                'id': region.region_id,
                'label': region.label,
                'xPercent': float(region.x_percent),
                'yPercent': float(region.y_percent),
                'widthPercent': float(region.width_percent) if region.width_percent else None,
                'heightPercent': float(region.height_percent) if region.height_percent else None,
                'color': region.color,
                'icon': region.icon
            })
        
        return JsonResponse({
            'success': True,
            'regions': created_regions,
            'count': len(created_regions)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_interactive_image(request, image_id):
    """API endpoint to get interactive image with its regions."""
    try:
        interactive_image = get_object_or_404(InteractiveImage, id=image_id)
        regions = interactive_image.regions.all()
        
        regions_data = [{
            'id': region.region_id,
            'label': region.label,
            'xPercent': float(region.x_percent),
            'yPercent': float(region.y_percent),
            'widthPercent': float(region.width_percent) if region.width_percent else None,
            'heightPercent': float(region.height_percent) if region.height_percent else None,
            'color': region.color,
            'icon': region.icon,
            'order': region.order
        } for region in regions]
        
        return JsonResponse({
            'id': interactive_image.id,
            'name': interactive_image.name,
            'imageUrl': interactive_image.image.url,
            'regions': regions_data,
            'createdAt': interactive_image.created_at.isoformat()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def api_interactive_images(request):
    """API endpoint to list all interactive images."""
    images = InteractiveImage.objects.all().order_by('-created_at')
    
    images_data = [{
        'id': img.id,
        'name': img.name or f'Image {img.id}',
        'imageUrl': img.image.url,
        'regionCount': img.regions.count(),
        'createdAt': img.created_at.isoformat()
    } for img in images]
    
    return JsonResponse({
        'images': images_data,
        'count': len(images_data)
    })


@csrf_exempt
def delete_interactive_image(request, image_id):
    """API endpoint to delete an interactive image."""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Only DELETE method is allowed'}, status=405)
    
    try:
        interactive_image = get_object_or_404(InteractiveImage, id=image_id)
        interactive_image.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Image deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
