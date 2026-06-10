import random
from pathlib import Path
from aiogram.types import FSInputFile

IMAGES_ROOT = Path("images")

def get_available_categories():
    """Automatically detect all subfolders inside images/"""
    if not IMAGES_ROOT.exists():
        return []
    return [f.name for f in IMAGES_ROOT.iterdir() if f.is_dir()]

def detect_image_request(text: str):
    """Check if message mentions any available image category."""
    text_lower = text.lower()
    
    # ================== KEYWORD MAP ==================
    keyword_map = {
        "kiss": "kiss",
        "kissing": "kiss",
        "chu": "kiss",
        "キス": "kiss",
        "ちゅっ": "kiss",
        "lip kiss": "lip-kiss",
        "lips kiss": "lip-kiss",
        "kiss on lips": "lip-kiss",
        
        "dick kiss": "dick-kiss",
        "kiss on dick": "dick-kiss",
        "kiss my dick": "dick-kiss",
        "cock kiss": "dick-kiss",
        "suck dick": "dick-kiss",
        "blowjob": "dick-kiss",
        "dick": "dick-kiss",
        "cock": "dick-kiss",
        "チンポ": "dick-kiss",
        
        "boobs": "boobs",
        "breast": "boobs",
        "tits": "boobs",
        "tit": "boobs",
        "cleavage": "boobs",
        
        "hug": "hug",
        "hugging": "hug",
        "embrace": "hug",
        
        "lick": "lick",
        "licking": "lick",
        "tongue": "lick",
        
        "fuck": "fuck",
        "fucking": "fuck",
        "sex": "fuck",
        
        "suck": "suck",
        "sucking": "suck",
        
        "doggy": "doggy",
        "doggy style": "doggy",
        "from behind": "doggy",
        
        "cum": "cum",
        "creampie": "cum",
        "facial": "cum",
        
        "nude": "nude",
        "naked": "nude",
        "full nude": "nude",
        "picture": "nude",
        "photo": "nude",
        "pic": "nude",
        "画像": "nude",
        "送って": "nude",
    }
    # ================================================

    # Check keyword map first
    for keyword, folder_name in keyword_map.items():
        if keyword in text_lower:
            return folder_name

    # Fallback to automatic folder name detection
    for category in get_available_categories():
        if category in text_lower:
            return category
            
    return None

def get_random_image(category: str):
    """Return a random image from the given category folder, or None."""
    folder = IMAGES_ROOT / category
    if not folder.exists():
        return None
    images = [
        f for f in folder.iterdir()
        if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]
    if not images:
        return None
    return FSInputFile(str(random.choice(images)))
