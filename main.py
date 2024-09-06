import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import re
import os 
from fastapi.middleware.cors import CORSMiddleware
from pdf2image import convert_from_path
import cv2
import pytesseract
import numpy as np
import time
app = FastAPI()
# pytesseract.pytesseract.tesseract_cmd = "D:\\256SSD\\Tesseract-OCR\\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = os.getenv('TESSERACT_CMD', '/usr/bin/tesseract')



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to your client's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




def extract_text_with_positions(pdf_path):
    print("iNside positions")
    doc = fitz.open(pdf_path)
    text_positions = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:  # Use "dict" to get detailed information
            if block['type'] == 0:  # Text blocks
                for line in block['lines']:
                    for span in line['spans']:
                        text_positions.append({
                            'text': span['text'].strip(),
                            'bbox': span['bbox'],  # (x0, y0, x1, y1)
                            'font': span['font'],  # Font name
                            'size': span['size'],  # Font size
                            'color': span['color'],  # Font color in integer format
                            'flags': span['flags'],  # Font styles (e.g., bold, italic)
                        })
    doc.close()
    return text_positions

def extract_text_from_positions(text_positions):
    text = ""
    for i in text_positions:
        text+=i["text"]+" "
    return text

def deskew(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(gray > 0))
    angle = cv2.minAreaRect(coords)[-1]
    
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return rotated


def extract_text_from_image(image):
    print("inside extraction")
    text = pytesseract.image_to_string(image)
    print("text ",text)
    return text






@app.post("/upload_pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    
    # Extract the file extension
    file_extension = os.path.splitext(file.filename)[1]
    
    # Create the new file name with timestamp
    new_filename = f"{os.path.splitext(file.filename)[0]}_{timestamp}{file_extension}"
    
    pdf_path = f"./{new_filename}"
    print("new request came ",pdf_path)
    try:
        # Save the uploaded file
        with open(pdf_path, "wb") as f:
            f.write(await file.read())
        print("pdf opened")
        pages = convert_from_path(pdf_path)
        print("pdf pagees done")

        extracted_text = []
        aggregated_text = ""
        for page in pages:
            print("Page reading")
            # Step 2: Preprocess the image (deskew)
            preprocessed_image = deskew(np.array(page))
            print("Page deskew")

            # Step 3: Extract text using OCR
            
            text = extract_text_from_image(preprocessed_image)
            print("text extracted")
            aggregated_text += text
            extracted_text.append(text)

        return JSONResponse(content={"text": aggregated_text})

    except Exception as e:
        print("got execption ",e )
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return JSONResponse(content={"error": str(e)}, status_code=500)

    finally :
        if os.path.exists(pdf_path):
            os.remove(pdf_path)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    