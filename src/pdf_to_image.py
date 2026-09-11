#!/usr/bin/env python3
"""
PDF to PNG image converter for OCR training.
Converts PDF syllabus files into high-resolution PNG images.
Provides options for OpenCV-based image preprocessing to enhance OCR accuracy.
"""

import os
import sys
import argparse
from pathlib import Path
from PIL import Image
import numpy as np

# Check and import required libraries with user-friendly warnings
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError
except ImportError:
    print("Error: 'pdf2image' is not installed, which is required for PDF conversion.")
    print("Please install it using: pip install pdf2image")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    # Elegant fallback if tqdm is not installed
    def tqdm(iterable, **kwargs):
        total = len(iterable) if hasattr(iterable, '__len__') else None
        print(f"Processing {kwargs.get('desc', 'items')}...")
        for i, item in enumerate(iterable, 1):
            yield item
            if total:
                print(f"Progress: {i}/{total}")


def preprocess_image(pil_img, contrast_limit=2.0, tile_size=8, binarize=False):
    """
    Applies OpenCV preprocessing to optimize the image for document OCR.
    
    1. Converts to grayscale.
    2. Applies CLAHE for local contrast enhancement (balances uneven lighting).
    3. Uses Bilateral Filter to denoise while keeping character boundaries sharp.
    4. Optionally applies adaptive Gaussian thresholding for binarization.
    """
    if cv2 is None:
        return pil_img

    # Convert Pillow image to OpenCV BGR format
    np_img = np.array(pil_img)
    if len(np_img.shape) == 3:
        if np_img.shape[2] == 3:
            cv_img = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
        elif np_img.shape[2] == 4:
            cv_img = cv2.cvtColor(np_img, cv2.COLOR_RGBA2BGR)
    else:
        cv_img = cv_img

    # Step 1: Grayscale conversion
    if len(cv_img.shape) == 3:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv_img

    # Step 2: CLAHE for adaptive contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=contrast_limit, tileGridSize=(tile_size, tile_size))
    enhanced = clahe.apply(gray)

    # Step 3: Bilateral Filter for edge-preserving smoothing (reduces scan noise)
    denoised = cv2.bilateralFilter(enhanced, d=9, sigmaColor=75, sigmaSpace=75)

    # Step 4: Optional Adaptive Gaussian Thresholding (Binarization)
    if binarize:
        processed = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
    else:
        processed = denoised

    # Convert back to PIL Image
    return Image.fromarray(processed)


def process_pdfs(input_dir, output_dir, dpi, page_mode, preprocess, binarize, poppler_path):
    """
    Scans input directory for PDF files, converts them, and saves to output directory.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Locate all PDF files recursively
    pdf_files = sorted(list(input_path.rglob("*.pdf")) + list(input_path.rglob("*.PDF")))
    
    if not pdf_files:
        print(f"No PDF files found in '{input_dir}'.")
        return

    print(f"Found {len(pdf_files)} PDF files to process.")
    
    success_count = 0
    total_images_saved = 0
    
    # Process each PDF file
    for pdf_path in tqdm(pdf_files, desc="Converting PDFs"):
        try:
            # Setup poppler path if provided, else use default path resolution
            p_path = poppler_path if poppler_path else None
            
            # Load PDF pages
            if page_mode == "first":
                pages = convert_from_path(
                    str(pdf_path), 
                    dpi=dpi, 
                    first_page=1, 
                    last_page=1, 
                    poppler_path=p_path
                )
            else:
                pages = convert_from_path(
                    str(pdf_path), 
                    dpi=dpi, 
                    poppler_path=p_path
                )
            
            # Convert and save each loaded page
            for idx, page in enumerate(pages, 1):
                page_num = idx
                
                if preprocess:
                    page = preprocess_image(page, binarize=binarize)
                
                # Format output filename: [pdf_name]_page_[page_num].png
                file_stem = pdf_path.stem
                output_filename = f"{file_stem}_page_{page_num:03d}.png"
                output_file_path = output_path / output_filename
                
                page.save(output_file_path, "PNG")
                total_images_saved += 1
                
            success_count += 1
            
        except PDFInfoNotInstalledError:
            print("\nError: Poppler is not installed or not in system PATH.")
            print("On Windows, you can install poppler using conda:")
            print("  conda install -c conda-forge poppler")
            print("Or download from a source and use the --poppler-path argument.")
            sys.exit(1)
        except (PDFPageCountError, PDFSyntaxError) as e:
            print(f"\nFailed to process '{pdf_path.name}': Corrupted file or invalid format. ({e})")
        except Exception as e:
            print(f"\nUnexpected error processing '{pdf_path.name}': {e}")

    print(f"\nSuccessfully processed {success_count}/{len(pdf_files)} PDFs.")
    print(f"Saved {total_images_saved} images to '{output_dir}'.")


def main():
    parser = argparse.ArgumentParser(
        description="Convert syllabus PDFs to PNGs for OCR training with preprocessing options."
    )
    parser.add_argument(
        "-i", "--input-dir", 
        default="data", 
        help="Directory containing input PDF files (searched recursively). Default: 'data'"
    )
    parser.add_argument(
        "-o", "--output-dir", 
        default="data/raw_images", 
        help="Directory to save the converted PNG images. Default: 'data/raw_images'"
    )
    parser.add_argument(
        "--dpi", 
        type=int, 
        default=300, 
        help="Resolution DPI for PDF rasterization. Default: 300"
    )
    parser.add_argument(
        "--pages", 
        choices=["first", "all"], 
        default="all", 
        help="Convert only the 'first' page or 'all' pages of each PDF. Default: 'all'"
    )
    parser.add_argument(
        "--preprocess", 
        action="store_true", 
        help="Enable OpenCV image preprocessing (Grayscale + CLAHE contrast + Bilateral filtering)."
    )
    parser.add_argument(
        "--binarize", 
        action="store_true", 
        help="Binarize output image using adaptive thresholding (requires --preprocess)."
    )
    parser.add_argument(
        "--poppler-path", 
        default=os.environ.get("POPPLER_PATH"), 
        help="Explicit path to Poppler bin/ directory (especially on Windows)."
    )

    args = parser.parse_args()
    
    # Inform user about OpenCV state
    if args.preprocess and cv2 is None:
        print("Warning: Preprocessing requested, but 'opencv-python' (cv2) is not installed.")
        print("Preprocessing will be skipped. Install it with: pip install opencv-python-headless")
        args.preprocess = False

    process_pdfs(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        dpi=args.dpi,
        page_mode=args.pages,
        preprocess=args.preprocess,
        binarize=args.binarize,
        poppler_path=args.poppler_path
    )


if __name__ == "__main__":
    main()
