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
    if not text:
        return None
    text_lower = text.lower()
    
    # ================== KEYWORD MAP (This is used first) ==================
    keyword_map = {
        "kiss": "dick-kiss",
        "kissing": "dick-kiss",
        "chu": "dick-kiss",
        "キス": "dick-kiss",
        "ちゅっ": "dick-kiss",
        "dick kiss": "dick-kiss",
        "kiss dick": "dick-kiss",
        "kiss my dick": "dick-kiss",
        "cock kiss": "dick-kiss",
        "suck dick": "dick-kiss",
        "blowjob": "dick-kiss",
        "dick": "dick-kiss",
        "cock": "dick-kiss",
        "チンポ": "dick-kiss",
        
        "picture": "dick-kiss",
        "photo": "dick-kiss",
        "pic": "dick-kiss",
        "画像": "dick-kiss",
        "送って": "dick-kiss",
        "send": "dick-kiss",
        
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
    }
    # =====================================================================

    # Check keyword map first (most important)
    for keyword, folder_name in keyword_map.items():
        if keyword in text_lower:
            return folder_name

    # Fallback: check actual folder names
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
