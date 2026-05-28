import random
from pathlib import Path
from aiogram.types import FSInputFile

IMAGE_FOLDERS = {
    "selfie": "images/selfie",
    "beach": "images/beach",
    "outdoor": "images/outdoor",
}

# Keywords that map to each category
IMAGE_KEYWORDS = {
    "selfie": ["selfie", "photo", "pic", "picture", "your photo"],
    "beach": ["beach", "sea", "ocean", "water"],
    "outdoor": ["outdoor", "outside", "walk", "park", "garden"],
}


def detect_image_request(text: str):
    """Check if message is asking for an image. Returns category or None."""
    text_lower = text.lower()
    for category, keywords in IMAGE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category
    return None


def get_random_image(category: str):
    """Return a random FSInputFile from the given category folder, or None."""
    folder_path = IMAGE_FOLDERS.get(category)
    if not folder_path:
        return None

    folder = Path(folder_path)
    if not folder.exists():
        return None

    images = [
        f for f in folder.iterdir()
        if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]

    if not images:
        return None

    return FSInputFile(str(random.choice(images)))
