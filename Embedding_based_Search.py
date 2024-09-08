
import os
import pytesseract
from pdf2image import convert_from_path
from sentence_transformers import SentenceTransformer, util

def scan_pdfs(directory):
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files

def extract_text_from_pdf(file_path, page_limit=2):
    try:
        images = convert_from_path(file_path)
        text = ''
        for i, image in enumerate(images[:page_limit]):
            text += pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return None

def search_document(query):
    query_embedding = model.encode(query, convert_to_tensor=True)
    closest_match = None
    highest_score = -1

    for file, embedding in embeddings.items():
        score = util.pytorch_cos_sim(query_embedding, embedding).item()
        if score > highest_score:
            highest_score = score
            closest_match = file

    return closest_match, highest_score

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Model loaded successfully!")

directory_to_scan = r"Path(or)disk"  # provide the path or disk you are searching
pdf_files = scan_pdfs(directory_to_scan)

extracted_texts = {}
for pdf_file in pdf_files:
    extracted_texts[pdf_file] = extract_text_from_pdf(pdf_file)
  
embeddings = {}
for file, text in extracted_texts.items():
    embeddings[file] = model.encode(text, convert_to_tensor=True)

query = "query" #where is my assignment / Can you please find my name document
result, score = search_document(query)
print(f"Best match: {result} (Score: {score})") 
