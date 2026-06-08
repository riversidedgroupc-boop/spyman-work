"""Image patch embedding extraction for similar defect retrieval.

Uses lightweight features first: RGB histogram + grayscale histogram.
Optional: HOG, CLIP, DINOv2 embeddings when dependencies are available.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


EMBEDDING_CROP_SIZE = (64, 64)


def extract_crop(image_path: str, bbox: list[float]) -> Image.Image:
    """Crop the defect region from an image given a bounding box."""
    img = Image.open(image_path).convert("RGB")
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(img.width, x2)
    y2 = min(img.height, y2)
    if x2 <= x1 or y2 <= y1:
        return img
    return img.crop((x1, y1, x2, y2))


def compute_rgb_histogram(crop: Image.Image, bins: int = 16) -> np.ndarray:
    """Compute concatenated RGB histogram for a crop."""
    arr = np.array(crop)
    hist = []
    for channel in range(3):
        h, _ = np.histogram(arr[:, :, channel], bins=bins, range=(0, 256))
        hist.append(h.astype(np.float64) / max(h.sum(), 1))
    return np.concatenate(hist)


def compute_grayscale_histogram(crop: Image.Image, bins: int = 32) -> np.ndarray:
    """Compute grayscale histogram for a crop."""
    gray = np.array(crop.convert("L"))
    h, _ = np.histogram(gray, bins=bins, range=(0, 256))
    return h.astype(np.float64) / max(h.sum(), 1)


def compute_basic_embedding(crop: Image.Image) -> np.ndarray:
    """Compute a simple embedding from RGB + grayscale histograms."""
    rgb = compute_rgb_histogram(crop, bins=16)
    gray = compute_grayscale_histogram(crop, bins=32)
    return np.concatenate([rgb, gray])


def compute_hog_embedding(crop: Image.Image) -> np.ndarray | None:
    """Compute HOG embedding if available (requires scikit-image or OpenCV)."""
    try:
        import cv2
        import numpy as np

        gray = np.array(crop.convert("L"))
        gray = cv2.resize(gray, EMBEDDING_CROP_SIZE)

        from cv2 import HOGDescriptor
        hog = HOGDescriptor(EMBEDDING_CROP_SIZE, (16, 16), (8, 8), (8, 8), 9)
        h = hog.compute(gray)
        return h.flatten().astype(np.float64)
    except ImportError:
        return None


def compute_clip_embedding(crop: Image.Image) -> np.ndarray | None:
    """Compute CLIP image embedding if available."""
    try:
        import torch
        import clip

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, preprocess = clip.load("ViT-B/32", device=device)
        img_tensor = preprocess(crop).unsqueeze(0).to(device)
        with torch.no_grad():
            features = model.encode_image(img_tensor)
        return features.cpu().numpy().flatten().astype(np.float64)
    except ImportError:
        return None


def compute_dinov2_embedding(crop: Image.Image) -> np.ndarray | None:
    """Compute DINOv2 embedding if available."""
    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")
        model = model.to(device).eval()

        import torchvision.transforms as T

        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        img_tensor = transform(crop).unsqueeze(0).to(device)
        with torch.no_grad():
            features = model(img_tensor)
        return features.cpu().numpy().flatten().astype(np.float64)
    except Exception:
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two vectors."""
    return float(np.linalg.norm(a - b))
